#!/usr/bin/env python3
"""DownloadPilot core logic."""
from __future__ import annotations

from .config import load_tool_data

import argparse
import csv
import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlparse

import requests
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from .utils import (
    console,
    format_bytes,
    make_table,
    print_error,
    print_info,
    print_success,
    print_tool_header,
    print_warning,
    prompt_confirm,
    prompt_menu,
    prompt_text,
    safe_filename,
)

CONTENT_DISPOSITION_RE = re.compile(
    r"""filename\*=(?:UTF-8'')?([^;\r\n]+)|filename=['"]?([^'";\r\n]+)['"]?""",
    re.IGNORECASE,
)

def _load_tool_data(filename: str) -> dict:
    """Thin alias: load this tool's own config via core/config.py."""
    return load_tool_data(filename)

SUPPORTED_HASH_ALGOS = ("md5", "sha1", "sha256")


@dataclass
class DownloadItem:
    id: str
    url: str
    output_dir: Path
    filename: Optional[str] = None
    expected_checksum: Optional[str] = None
    checksum_algorithm: str = "sha256"  # md5 | sha1 | sha256
    status: str = "pending"  # pending | active | paused | completed | skipped | failed
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed_bps: float = 0.0
    eta_seconds: Optional[float] = None
    attempts: int = 0
    saved_path: Optional[str] = None
    checksum_verified: Optional[bool] = None
    computed_checksum: Optional[str] = None
    error_message: str = ""
    _pause_event: threading.Event = field(default_factory=threading.Event, repr=False, compare=False)
    _cancel_event: threading.Event = field(default_factory=threading.Event, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Unpaused by default (set = running, clear = paused)
        self._pause_event.set()


TOOL_DATA = _load_tool_data("transfer_profile.json")
DEFAULT_HEADERS = {
    "User-Agent": TOOL_DATA.get("user_agent", "DownloadPilot/1.0"),
}
DEFAULT_CHUNK_SIZE = int(TOOL_DATA.get("chunk_size", 32768))
DEFAULT_DOWNLOAD_DIR = TOOL_DATA.get("default_download_dir", "downloads")
DEFAULT_WORKERS = int(TOOL_DATA.get("default_workers", 4))
DEFAULT_RETRIES = int(TOOL_DATA.get("default_retries", 3))
DEFAULT_TIMEOUT = int(TOOL_DATA.get("default_timeout", 20))
SUPPORTED_HASH_ALGOS = tuple(TOOL_DATA.get("supported_algorithms", ["md5", "sha1", "sha256"]))
HEX_LENGTH_MAP = {int(k): v for k, v in TOOL_DATA.get("hex_length_map", {"32": "md5", "40": "sha1", "64": "sha256"}).items()}


def detect_filename(url: str, headers: Optional[Dict[str, Any]] = None) -> str:
    """Detect appropriate filename from Content-Disposition header or URL path."""
    if headers:
        cd = headers.get("Content-Disposition") or headers.get("content-disposition")
        if cd:
            match = CONTENT_DISPOSITION_RE.search(str(cd))
            if match:
                raw_name = unquote(match.group(1) or match.group(2) or "").strip()
                if raw_name:
                    return safe_filename(os.path.basename(raw_name))

    parsed = urlparse(url)
    base = os.path.basename(unquote(parsed.path.rstrip("/")))
    if base and base != "/":
        return safe_filename(base)

    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
    return f"download_{url_hash}.bin"


def compute_file_checksum(file_path: Path | str, algorithm: str = "sha256") -> str:
    """Compute MD5, SHA-1, or SHA-256 digest of a file."""
    algo = algorithm.lower().replace("-", "")
    if algo not in SUPPORTED_HASH_ALGOS:
        raise ValueError(f"Unsupported checksum algorithm '{algorithm}'. Choose from: md5, sha1, sha256")
    h = hashlib.new(algo)
    with open(file_path, "rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower()


def verify_checksum(
    file_path: Path | str,
    expected_checksum: str,
    algorithm: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """Verify file checksum against expected digest.

    Supports 'algo:hexdigest' or auto-detects algorithm by hex length (32=md5, 40=sha1, 64=sha256).
    Returns (is_match, computed_hex, algorithm_used).
    """
    raw = expected_checksum.strip()
    if ":" in raw:
        prefix, digest = raw.split(":", 1)
        algo = prefix.strip().lower().replace("-", "")
        expected = digest.strip().lower()
    else:
        expected = raw.lower()
        if algorithm:
            algo = algorithm.lower().replace("-", "")
        elif len(expected) == 32:
            algo = "md5"
        elif len(expected) == 40:
            algo = "sha1"
        else:
            algo = "sha256"

    computed = compute_file_checksum(file_path, algorithm=algo)
    return (computed == expected, computed, algo)


class DownloadManager:
    """Manages a download queue with parallel workers, resume, pause/resume, retries, and checksums."""

    def __init__(
        self,
        output_dir: Path | str = DEFAULT_DOWNLOAD_DIR,
        max_workers: int = DEFAULT_WORKERS,
        max_retries: int = DEFAULT_RETRIES,
        retry_Delay: float = 0.5,
        timeout: int = DEFAULT_TIMEOUT,
        skip_duplicates: bool = True,
        resume_partial: bool = True,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max(1, int(max_workers))
        self.max_retries = max(0, int(max_retries))
        self.retry_delay = float(retry_Delay)
        self.timeout = int(timeout)
        self.skip_duplicates = skip_duplicates
        self.resume_partial = resume_partial
        self.chunk_size = max(1024, int(chunk_size))
        self.session = session or requests.Session()
        self.queue: List[DownloadItem] = []

    def add_url(
        self,
        url: str,
        filename: Optional[str] = None,
        expected_checksum: Optional[str] = None,
        checksum_algorithm: str = "sha256",
    ) -> DownloadItem:
        item_id = f"dl_{len(self.queue) + 1:03d}"
        item = DownloadItem(
            id=item_id,
            url=url.strip(),
            output_dir=self.output_dir,
            filename=filename,
            expected_checksum=expected_checksum,
            checksum_algorithm=checksum_algorithm,
        )
        self.queue.append(item)
        return item

    def pause_item(self, item_id: str) -> bool:
        for item in self.queue:
            if item.id == item_id:
                item._pause_event.clear()
                if item.status in ("active", "pending"):
                    item.status = "paused"
                return True
        return False

    def resume_item(self, item_id: str) -> bool:
        for item in self.queue:
            if item.id == item_id:
                item._pause_event.set()
                if item.status == "paused":
                    item.status = "pending"
                return True
        return False

    def _download_single(
        self,
        item: DownloadItem,
        progress: Optional[Progress] = None,
        task_id: Optional[Any] = None,
    ) -> DownloadItem:
        # Wait if item is paused before starting
        if not item._pause_event.is_set():
            item.status = "paused"
            item._pause_event.wait()

        item.status = "active"
        item.error_message = ""
        prelim_name = item.filename or detect_filename(item.url)
        final_dest = item.output_dir / prelim_name

        # 1. Duplicate download prevention: check if completed file already exists
        if self.skip_duplicates and final_dest.exists() and final_dest.stat().st_size > 0:
            if item.expected_checksum:
                ok, comp, algo = verify_checksum(final_dest, item.expected_checksum, item.checksum_algorithm)
                if ok:
                    item.status = "skipped"
                    item.saved_path = str(final_dest)
                    item.downloaded_bytes = final_dest.stat().st_size
                    item.total_bytes = item.downloaded_bytes
                    item.checksum_verified = True
                    item.computed_checksum = comp
                    item.error_message = "Already downloaded & checksum verified"
                    return item
            else:
                item.status = "skipped"
                item.saved_path = str(final_dest)
                item.downloaded_bytes = final_dest.stat().st_size
                item.total_bytes = item.downloaded_bytes
                item.error_message = "Duplicate file already exists in output directory"
                return item

        part_path = item.output_dir / f"{prelim_name}.part"

        for attempt in range(1, self.max_retries + 2):
            item.attempts = attempt
            try:
                existing_bytes = part_path.stat().st_size if (self.resume_partial and part_path.exists()) else 0
                req_headers = dict(DEFAULT_HEADERS)
                if existing_bytes > 0:
                    req_headers["Range"] = f"bytes={existing_bytes}-"

                with self.session.get(
                    item.url,
                    headers=req_headers,
                    stream=True,
                    timeout=self.timeout,
                    allow_redirects=True,
                ) as resp:
                    # Handle HTTP 416 Range Not Satisfiable by restarting fresh
                    if resp.status_code == 416 and existing_bytes > 0:
                        part_path.unlink(missing_ok=True)
                        existing_bytes = 0
                        req_headers.pop("Range", None)
                        resp = self.session.get(
                            item.url,
                            headers=req_headers,
                            stream=True,
                            timeout=self.timeout,
                            allow_redirects=True,
                        )

                    resp.raise_for_status()

                    # Update detected filename from response headers if not explicitly forced
                    if not item.filename:
                        detected = detect_filename(resp.url or item.url, dict(resp.headers))
                        if detected != prelim_name:
                            prelim_name = detected
                            final_dest = item.output_dir / prelim_name
                            if self.skip_duplicates and final_dest.exists() and final_dest.stat().st_size > 0 and not item.expected_checksum:
                                item.status = "skipped"
                                item.saved_path = str(final_dest)
                                item.downloaded_bytes = final_dest.stat().st_size
                                item.total_bytes = item.downloaded_bytes
                                item.error_message = "Duplicate file already exists"
                                return item

                    is_resumed = resp.status_code == 206 and existing_bytes > 0
                    content_len = int(resp.headers.get("Content-Length", 0) or 0)
                    if is_resumed:
                        item.total_bytes = existing_bytes + content_len if content_len else 0
                        item.downloaded_bytes = existing_bytes
                        file_mode = "ab"
                    else:
                        item.total_bytes = content_len
                        item.downloaded_bytes = 0
                        file_mode = "wb"

                    if progress is not None and task_id is not None:
                        progress.update(
                            task_id,
                            description=f"[cyan]{prelim_name[:32]}",
                            total=item.total_bytes or None,
                            completed=item.downloaded_bytes,
                        )

                    start_t = time.perf_counter()
                    bytes_since_start = 0

                    with open(part_path, file_mode) as fh:
                        for chunk in resp.iter_content(chunk_size=self.chunk_size):
                            if item._cancel_event.is_set():
                                raise RuntimeError("Download cancelled")
                            if not item._pause_event.is_set():
                                item.status = "paused"
                                item._pause_event.wait()
                                item.status = "active"
                            if not chunk:
                                continue
                            fh.write(chunk)
                            c_len = len(chunk)
                            item.downloaded_bytes += c_len
                            bytes_since_start += c_len
                            elapsed = max(1e-4, time.perf_counter() - start_t)
                            item.speed_bps = bytes_since_start / elapsed
                            if item.total_bytes > item.downloaded_bytes and item.speed_bps > 0:
                                item.eta_seconds = (item.total_bytes - item.downloaded_bytes) / item.speed_bps
                            else:
                                item.eta_seconds = 0.0

                            if progress is not None and task_id is not None:
                                progress.advance(task_id, c_len)

                # Move completed .part file to final destination
                part_path.replace(final_dest)
                item.saved_path = str(final_dest)
                if item.total_bytes == 0:
                    item.total_bytes = item.downloaded_bytes

                # Verify checksum if supplied
                if item.expected_checksum:
                    ok, computed, algo = verify_checksum(
                        final_dest,
                        item.expected_checksum,
                        item.checksum_algorithm,
                    )
                    item.checksum_verified = ok
                    item.computed_checksum = computed
                    item.checksum_algorithm = algo
                    if not ok:
                        item.status = "failed"
                        item.error_message = (
                            f"Checksum mismatch ({algo.upper()}): expected {item.expected_checksum}, got {computed}"
                        )
                        return item
                else:
                    item.computed_checksum = compute_file_checksum(final_dest, item.checksum_algorithm)

                item.status = "completed"
                item.error_message = ""
                return item

            except Exception as exc:
                item.error_message = str(exc)
                if attempt <= self.max_retries:
                    time.sleep(self.retry_delay * attempt)
                else:
                    item.status = "failed"

        return item

    def run_all(self, show_progress: bool = True, only_failed: bool = False) -> List[DownloadItem]:
        """Execute pending (or failed) downloads in the queue using parallel workers."""
        target_statuses = ("failed",) if only_failed else ("pending", "paused")
        for item in self.queue:
            if item.status in target_statuses:
                item._pause_event.set()
                item.status = "pending"

        to_process = [item for item in self.queue if item.status == "pending"]
        if not to_process:
            return self.queue

        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
                transient=False,
            ) as progress:
                with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                    futures = {}
                    for item in to_process:
                        tid = progress.add_task(f"[cyan]{item.url[:35]}", total=None)
                        futures[pool.submit(self._download_single, item, progress, tid)] = item
                    for fut in as_completed(futures):
                        fut.result()
        else:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = [pool.submit(self._download_single, item, None, None) for item in to_process]
                for fut in as_completed(futures):
                    fut.result()

        return self.queue

    def retry_failed(self, show_progress: bool = True) -> List[DownloadItem]:
        """Retry only unsuccessful downloads in the queue."""
        return self.run_all(show_progress=show_progress, only_failed=True)


def export_download_report(
    items: Sequence[DownloadItem],
    output_path: Path | str,
    fmt: Optional[str] = None,
) -> Path:
    """Export completed, skipped, and failed download details to JSON, CSV, or TXT."""
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    export_fmt = (fmt or out.suffix.lstrip(".") or "json").lower()

    serializable_items = []
    for item in items:
        serializable_items.append(
            {
                "id": item.id,
                "url": item.url,
                "status": item.status,
                "saved_path": item.saved_path,
                "downloaded_bytes": item.downloaded_bytes,
                "total_bytes": item.total_bytes,
                "speed_bps": round(item.speed_bps, 2),
                "attempts": item.attempts,
                "checksum_algorithm": item.checksum_algorithm,
                "expected_checksum": item.expected_checksum,
                "computed_checksum": item.computed_checksum,
                "checksum_verified": item.checksum_verified,
                "error_message": item.error_message,
            }
        )

    if export_fmt == "csv":
        with open(out, "w", newline="", encoding="utf-8") as fh:
            if serializable_items:
                writer = csv.DictWriter(fh, fieldnames=list(serializable_items[0].keys()))
                writer.writeheader()
                writer.writerows(serializable_items)
    elif export_fmt == "txt":
        lines = [
            f"DownloadPilot Report - Generated {datetime.now().isoformat(timespec='seconds')}",
            "=" * 80,
        ]
        for rec in serializable_items:
            lines.append(
                f"[{rec['status'].upper()}] {rec['url']} -> {rec['saved_path'] or '-'} "
                f"({format_bytes(rec['downloaded_bytes'])}, attempts={rec['attempts']}) {rec['error_message']}"
            )
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "summary": {
                "total": len(serializable_items),
                "completed": sum(1 for x in serializable_items if x["status"] == "completed"),
                "skipped": sum(1 for x in serializable_items if x["status"] == "skipped"),
                "failed": sum(1 for x in serializable_items if x["status"] == "failed"),
            },
            "downloads": serializable_items,
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def display_download_queue(items: Sequence[DownloadItem]) -> None:
    color_map = {
        "completed": "bold green",
        "skipped": "yellow",
        "failed": "bold red",
        "active": "cyan",
        "paused": "magenta",
        "pending": "white",
    }
    rows = []
    for item in items:
        st_style = color_map.get(item.status, "white")
        pct = (
            f"{(item.downloaded_bytes / item.total_bytes * 100.0):.1f}%"
            if item.total_bytes > 0
            else ("100%" if item.status in ("completed", "skipped") else "-")
        )
        speed_str = f"{format_bytes(item.speed_bps)}/s" if item.speed_bps > 0 else "-"
        chk_str = "-"
        if item.checksum_verified is True:
            chk_str = f"[green]OK ({item.checksum_algorithm.upper()})[/green]"
        elif item.checksum_verified is False:
            chk_str = "[bold red]MISMATCH[/bold red]"
        elif item.computed_checksum:
            chk_str = f"{item.computed_checksum[:12]}..."

        note = item.saved_path or item.error_message or "-"
        rows.append(
            (
                item.id,
                f"[{st_style}]{item.status.upper()}[/{st_style}]",
                f"{format_bytes(item.downloaded_bytes)} ({pct})",
                speed_str,
                str(item.attempts),
                chk_str,
                note,
            )
        )

    console.print()
    console.print(
        make_table(
            title="DownloadPilot - Queue & Transfer Summary",
            columns=[
                ("ID", "bold magenta"),
                ("Status", "white"),
                ("Progress", "cyan"),
                ("Speed", "green"),
                ("Tries", "yellow"),
                ("Checksum", "white"),
                ("Saved Path / Details", "dim white"),
            ],
            rows=rows,
        )
    )


def load_urls_from_file(file_path: Path | str) -> List[str]:
    p = Path(file_path).expanduser().resolve()
    urls: List[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if clean and not clean.startswith("#"):
            urls.append(clean)
    return urls

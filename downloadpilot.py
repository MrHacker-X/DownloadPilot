#!/usr/bin/env python3
"""
DownloadPilot - Advanced File Downloader.

Author  : MrHacker-X
Repo    : https://github.com/MrHacker-X/downloadpilot
Version : 1.0.0
"""
from __future__ import annotations

import argparse
import sys

from core.config import load_defaults
from core.engine import *  # noqa: F401,F403
from core.utils import *  # noqa: F401,F403

_defaults = load_defaults()
__version__ = str(_defaults.get("version", "1.0.0"))
TOOL_DESC = str(_defaults.get("description", "One or more direct HTTP/HTTPS URLs to download"))
TOOL_NAME = str(_defaults.get("name", "DownloadPilot"))


def register_subparser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "urls",
        nargs="*",
        help="One or more direct HTTP/HTTPS URLs to download",
    )
    parser.add_argument(
        "-f",
        "--url-file",
        help="Text file containing a list of URLs to download (one per line)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=DEFAULT_DOWNLOAD_DIR,
        help="Custom output directory for downloaded files (default: ./downloads)",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=4,
        help="Number of concurrent download workers (default: 4)",
    )
    parser.add_argument(
        "-r",
        "--retries",
        type=int,
        default=3,
        help="Automatic retry attempts on temporary network errors (default: 3)",
    )
    parser.add_argument(
        "-c",
        "--checksum",
        help="Expected checksum for verification (MD5, SHA-1, or SHA-256; optionally 'sha256:HEX')",
    )
    parser.add_argument(
        "--algo",
        choices=["md5", "sha1", "sha256"],
        default="sha256",
        help="Checksum algorithm (default: sha256)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Disable duplicate download prevention and re-download existing files",
    )
    parser.add_argument(
        "-e",
        "--export-report",
        help="Export download report to JSON, CSV, or TXT file path",
    )
    parser.set_defaults(func=run_cli)


def run_cli(args: argparse.Namespace) -> int:
    url_list: List[str] = list(getattr(args, "urls", None) or [])
    if getattr(args, "url_file", None):
        try:
            url_list.extend(load_urls_from_file(args.url_file))
        except Exception as exc:
            print_error(f"Could not read URL file: {exc}")
            return 1

    if not url_list:
        run_interactive()
        return 0

    print_tool_header("DownloadPilot", "Advanced File Downloader", icon="🚀")
    mgr = DownloadManager(
        output_dir=args.output_dir,
        max_workers=args.workers,
        max_retries=args.retries,
        skip_duplicates=not args.force,
    )

    for idx, u in enumerate(url_list):
        chk = args.checksum if (len(url_list) == 1 and idx == 0) else None
        mgr.add_url(u, expected_checksum=chk, checksum_algorithm=args.algo)

    mgr.run_all(show_progress=True)
    display_download_queue(mgr.queue)

    if args.export_report:
        saved = export_download_report(mgr.queue, args.export_report)
        print_success(f"Exported download report to {saved}")

    failed = sum(1 for x in mgr.queue if x.status == "failed")
    return 0 if failed == 0 else 1


def run_interactive() -> None:
    print_tool_header("DownloadPilot", "Advanced File Downloader", icon="🚀")
    mgr = DownloadManager(output_dir="downloads")
    while True:
        choice = prompt_menu(
            "Menu",
            [
                ("1", "Download single URL"),
                ("2", "Download multiple URLs"),
                ("3", "Enqueue URL"),
                ("4", "Manage queue"),
                ("5", "Retry failed"),
                ("6", "Verify checksum"),
                ("7", "Settings"),
                ("8", "Export report"),
                ("a", "About"),
            ],
        )
        if choice == "0":
            return
        if choice == "a":
            show_about_panel()
            console.input("[dim]Press Enter to return to the menu...[/dim]")
            continue

        try:
            if choice == "1":
                url = prompt_text("Enter direct file URL (HTTP/HTTPS)")
                chk = prompt_text("Expected checksum (MD5/SHA-1/SHA-256 or leave blank)", default="", required=False) or None
                mgr.add_url(url, expected_checksum=chk)
                mgr.run_all(show_progress=True)
                display_download_queue(mgr.queue)
            elif choice == "2":
                src_type = prompt_menu(
                    "Source",
                    [("1", "Inline URL list"), ("2", "Load from file")],
                    allow_back=False,
                )
                urls = (
                    [u.strip() for u in prompt_text("Enter URLs separated by commas").split(",") if u.strip()]
                    if src_type == "1"
                    else load_urls_from_file(prompt_text("Enter text file path"))
                )
                for u in urls:
                    mgr.add_url(u)
                mgr.run_all(show_progress=True)
                display_download_queue(mgr.queue)
            elif choice == "3":
                url = prompt_text("Enter URL to enqueue")
                chk = prompt_text("Expected checksum (optional)", default="", required=False) or None
                item = mgr.add_url(url, expected_checksum=chk)
                print_success(f"Added {item.id} ({item.url}) to queue as PENDING.")
            elif choice == "4":
                display_download_queue(mgr.queue)
                sub = prompt_menu(
                    "Queue",
                    [
                        ("1", "Start pending"),
                        ("2", "Pause by ID"),
                        ("3", "Resume by ID"),
                    ],
                )
                if sub == "1":
                    mgr.run_all(show_progress=True)
                    display_download_queue(mgr.queue)
                elif sub == "2":
                    iid = prompt_text("Enter item ID (e.g. dl_001)")
                    if mgr.pause_item(iid):
                        print_info(f"Paused {iid}.")
                    else:
                        print_error(f"Item {iid} not found.")
                elif sub == "3":
                    iid = prompt_text("Enter item ID (e.g. dl_001)")
                    if mgr.resume_item(iid):
                        print_info(f"Resumed {iid}.")
                    else:
                        print_error(f"Item {iid} not found.")
            elif choice == "5":
                mgr.retry_failed(show_progress=True)
                display_download_queue(mgr.queue)
            elif choice == "6":
                fpath = prompt_text("Enter local file path to verify")
                expected = prompt_text("Enter expected MD5, SHA-1, or SHA-256 checksum")
                ok, comp, algo = verify_checksum(fpath, expected)
                if ok:
                    print_success(f"Checksum MATCHED ({algo.upper()}): {comp}")
                else:
                    print_error(f"Checksum MISMATCH ({algo.upper()}): expected {expected}, computed {comp}")
            elif choice == "7":
                out_dir = prompt_text("Output directory", default=str(mgr.output_dir))
                workers_str = prompt_text("Concurrent workers", default=str(mgr.max_workers))
                mgr.output_dir = Path(out_dir).expanduser().resolve()
                mgr.output_dir.mkdir(parents=True, exist_ok=True)
                if workers_str.isdigit():
                    mgr.max_workers = max(1, int(workers_str))
                print_success(f"Updated output_dir={mgr.output_dir}, max_workers={mgr.max_workers}")
            elif choice == "8":
                out_file = prompt_text("Report file path (.json, .csv, or .txt)", default="download_report.json")
                saved = export_download_report(mgr.queue, out_file)
                print_success(f"Exported download report to {saved}")
        except Exception as exc:
            print_error(f"DownloadPilot error: {exc}")


# ----------------------------------------------------------------------------
# CLI main
# ----------------------------------------------------------------------------



def build_arg_parser() -> argparse.ArgumentParser:
    """Build the standalone CLI parser for downloadpilot."""
    parser = argparse.ArgumentParser(
        prog="downloadpilot",
        description=TOOL_DESC,
        epilog=(
            "GitHub: https://github.com/MrHacker-X/downloadpilot - "
            "Run without flags to launch the interactive terminal menu."
        ),
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=TOOL_NAME + " " + __version__,
    )
    parser.add_argument(
        "-a",
        "--about",
        action="store_true",
        help="Show the About screen - overview, key features, version, author and contacts - and exit",
    )
    register_subparser(parser)
    return parser


def main(argv=None) -> int:
    """Entry point: parse flags and dispatch, or launch the interactive menu."""
    try:
        if argv is None:
            argv = sys.argv[1:]
        if not argv:
            # Plain `python downloadpilot.py` opens the interactive terminal menu.
            run_interactive()
            return 0
        parser = build_arg_parser()
        args = parser.parse_args(argv)
        if getattr(args, "about", False):
            show_about_panel()
            return 0
        func = getattr(args, "func", run_cli)
        result = func(args)
        return int(result) if isinstance(result, (int, float)) else 0
    except (KeyboardInterrupt, EOFError):
        return handle_keyboard_interrupt()


if __name__ == "__main__":
    raise SystemExit(main())

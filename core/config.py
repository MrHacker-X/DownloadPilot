#!/usr/bin/env python3
"""DownloadPilot configuration constants (built-in, self-contained)."""
from __future__ import annotations

_CONFIGS: dict = {
    "defaults.json": {
        "tool": "downloadpilot",
        "name": "DownloadPilot",
        "subtitle": "Advanced File Downloader",
        "version": "1.0.0",
        "description": "One or more direct HTTP/HTTPS URLs to download",
        "homepage": "https://github.com/MrHacker-X/downloadpilot",
        "author": "MrHacker-X",
        "email": "contact@vritrasec.com",
        "website": "https://vritrasec.com",
        "network": "https://link.vritrasec.com",
        "about_overview": (
            "DownloadPilot is a resilient, concurrent file downloader: queue direct URLs with live progress, automatic retries and checksum verification, manage pause/resume on a pending queue, and export the whole session as a JSON, CSV or TXT report."
        ),
        "about_features": [
            "Single and multi-URL concurrent downloads",
            "Checksum verification (MD5, SHA-1, SHA-256)",
            "Pause / resume from a pending queue",
            "Duplicate-skip and force re-download modes",
            "Retry logic for flaky connections",
            "JSON / CSV / TXT session report export",
        ]
    },
    "transfer_profile.json": {
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 DownloadPilot/1.0",
        "chunk_size": 32768,
        "default_workers": 4,
        "default_retries": 3,
        "default_timeout": 20,
        "supported_algorithms": [
            "md5",
            "sha1",
            "sha256"
        ],
        "hex_length_map": {
            "32": "md5",
            "40": "sha1",
            "64": "sha256"
        }
    }
}


def load_tool_data(filename: str) -> dict:
    """Return the built-in configuration table stored under `filename`."""
    return dict(_CONFIGS.get(filename, {}))


def load_defaults() -> dict:
    """Return the tool identity / defaults configuration."""
    return dict(_CONFIGS.get("defaults.json", {}))

<div align="center">

# ⃤ D O W N L O A D P I L O T ⃤

### *Queue, resume, and verify downloads - one command.*

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![OS](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-blue?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Stars](https://img.shields.io/github/stars/MrHacker-X/downloadpilot?style=flat-square&color=orange)
![Forks](https://img.shields.io/github/forks/MrHacker-X/downloadpilot?style=flat-square&color=cyan)

</div>

---

## 📋 Table of Contents

- [🎯 Why DownloadPilot?](#-why-downloadpilot)
- [🧭 What It Does](#-what-it-does)
- [🚀 Quick Start](#-quick-start)
- [🖼️ Preview](#-preview)
- [📦 Installation](#-installation)
- [✨ Features](#-features)
- [⌨️ Usage](#%EF%B8%8F-usage)
- [⚙️ Configuration](#%EF%B8%8F-configuration)
- [🧰 Tech Stack](#-tech-stack)
- [⚠️ Disclaimer](#%EF%B8%8F-disclaimer)
- [🤝 Contributing](#-contributing)
- [📜 License](#-license)
- [👨‍💻 Developer](#-developer)

---

## 🎯 Why DownloadPilot?

> Downloading a batch of files with curl means lost progress on every Wi-Fi hiccup, and no proof any file actually arrived intact. **DownloadPilot fixes both in two commands**: queue multiple URLs, pause and resume them across sessions, and get a SHA-256-verified JSON report at the end.
>
> **It's built for flaky networks and long queues.** Bars show live progress per file, and state persists - close the tool mid-queue and pick it up where you left off.

---

## 🧭 What It Does

| # | Task | What it gives you |
|---|------|-------------------|
| 1️⃣ | Download single or batch | One URL or a queue of many, with live per-file progress bars |
| 2️⃣ | Pause & resume | Interrupt any transfer and resume it later from the exact byte offset |
| 3️⃣ | Verify integrity | SHA-256 checksums computed for every completed download |
| 4️⃣ | Export reports | A JSON/text report of the whole run: statuses, sizes, hashes, timings |
| 5️⃣ | Interactive or direct CLI | Same queueing through a friendly menu or a flag-driven command |

---

## 🚀 Quick Start

```bash
git clone https://github.com/MrHacker-X/downloadpilot.git
cd downloadpilot
pip install -r requirements.txt
python downloadpilot.py                 # interactive menu
```

---

## 🖼️ Preview

<div align="center">

![DownloadPilot Preview](https://i.ibb.co/xSPfmDQK/downloadpilot.png)

</div>

---

## 📦 Installation

```bash
# 1. clone
git clone https://github.com/MrHacker-X/downloadpilot.git
cd downloadpilot

# 2. install dependencies
pip install -r requirements.txt

# 3. run
python downloadpilot.py
```

### Supported Systems

| OS | Status | Notes |
|----|--------|-------|
| 🐧 Linux | ✅ Fully supported | Any distro with Python 3.8+ |
| 🪟 Windows | ✅ Fully supported | Python from python.org, then the steps above |
| 🍎 macOS | ✅ Fully supported | `brew install python`, then the steps above |
| 📱 Termux (Android) | ✅ Fully supported | `pkg install python`, then the steps above |

> 💡 Partial downloads never corrupt finished files - each transfer writes to `*.part` and is only renamed into place once the final byte lands.

---

## ✨ Features

| | Feature | Description |
|---|---------|-------------|
| ⬇️ | **Single & batch queues** | Queue many URLs in one run; each file is tracked independently |
| ⏸️ | **True resume** | Transfers resume at the exact byte offset via HTTP Range requests |
| 🔏 | **Atomic writes** | `*.part` staging means a crash never leaves a half-broken file |
| 🔐 | **SHA-256 verification** | Every completed file's checksum is computed and recorded |
| 📊 | **Live progress bars** | Per-file Rich progress showing bytes, speed, and ETA |
| 📄 | **JSON reports** | Export the whole run to JSON - statuses, sizes, hashes, timing - for CI or records |
| 🎛️ | **Two modes** | A guided interactive menu or a fully flag-driven direct CLI |
| 🩹 | **Fail-fast validation** | Bad URLs, missing files, or dead servers produce one clear message |

---

## ⌨️ Usage

```bash
python downloadpilot.py                 # interactive menu
python downloadpilot.py -h              # help
python downloadpilot.py -v              # version
```

### Direct CLI

```bash
# download a single file (with checksum verification)
python downloadpilot.py https://example.com/file.zip --checksum sha256:HEX

# download several files from a list, with retries, exporting a report
echo -e "https://a.com/x.zip\nhttps://b.com/y.tar.gz" > urls.txt
python downloadpilot.py -f urls.txt --workers 4 --retries 3 -e run_report.json
```

| Option | Values / Example | Meaning |
|--------|------------------|---------|
| `urls` | one or many (positional) | URLs to queue for download |
| `-f` / `--url-file` | a text file | One URL per line to queue in batch |
| `-o` / `--output-dir` | directory | Where files land (default `downloads/`) |
| `-w` / `--workers` | number | Concurrent download workers (default 4) |
| `-r` / `--retries` | number | Automatic retries on network errors (default 3) |
| `--checksum` | `sha256:HEX` | Verify the download against an expected checksum |
| `-e` / `--export-report` | a filename | Export the run report (extension decides the format) |
| `--force` | flag | Re-download files that already exist |

---

## ⚙️ Configuration

Transfer behavior lives in [`core/config.py`](core/config.py):

| Setting | Default | Effect |
|---------|---------|--------|
| Output root | `downloads/` | Where completed files and partials are kept |
| Partial extension | `.part` | Extension for in-flight transfers before rename |
| Chunk size | moderate | Bytes read per iteration - balances speed & progress updates |
| Request headers | browser-like User-Agent | Serves through basic bot-blocking servers |

---

## 🧰 Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.8+ |
| HTTP | `requests` (streaming downloads) + standard `hashlib` (SHA-256) |
| Progress | `rich` (live progress bars, tables, prompts) |
| State | Filesystem only - `*.part` files carry resume state, no external DB |

---

## ⚠️ Disclaimer

> ### Read this before using DownloadPilot.
>
> 1. **Download what you're allowed to.** Many files on the internet are copyrighted. Use DownloadPilot for files you own, are licensed to fetch, or that are explicitly offered for public download.
> 2. **Don't hammer servers.** Parallel-retrying a queue against one host is just a polite flood. Keep your queues polite and respect rate limits - DownloadPilot won't protect you from your own loop.
> 3. **Checksums are integrity, not truth.** A SHA-256 match proves the file arrived as the server sent it - it does not prove the file is safe. Scan downloads before opening them.
> 4. **No warranty.** DownloadPilot is provided "as is", with no warranty of any kind. The author is **not liable** for misuse, legal trouble, or damage from using this tool.

---

## 🤝 Contributing

Contributions are welcome!

```bash
# 1. fork it
# 2. create your branch
git checkout -b feature/amazing-feature
# 3. commit
git commit -m "Add amazing feature"
# 4. push
git push origin feature/amazing-feature
# 5. open a Pull Request
```

---

## 📜 License

DownloadPilot is the original project by MrHacker-X - see the [`LICENSE`](https://github.com/MrHacker-X/downloadpilot) file in the upstream repository for details.

---

## 👨‍💻 Developer

| | |
|---|---|
| **Dev** | MrHacker-X |
| **GitHub** | [github.com/MrHacker-X](https://github.com/MrHacker-X) |
| **Email** | [contact@vritrasec.com](mailto:contact@vritrasec.com) |
| **Website** | [vritrasec.com](https://vritrasec.com) |
| **Network** | [link.vritrasec.com](https://link.vritrasec.com) |

---

<div align="center">

### ⭐ Star the repo if DownloadPilot survived your flaky Wi-Fi ⭐

*Built by MrHacker-X - download responsibly, verify always.*

</div>

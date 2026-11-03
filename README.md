# YouXtractor

<div align="center">

![YouXtractor Banner](assets/app.png)

**High-Fidelity Audio Extractor & Mastering Suite**

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![C Standard](https://img.shields.io/badge/C-C99-00599C.svg)](https://en.cppreference.com/w/c)
[![C++ Standard](https://img.shields.io/badge/C%2B%2B-C%2B%2B20-00599C.svg)](https://en.cppreference.com/w/cpp)
[![Node.js](https://img.shields.io/badge/Node.js-v18%2B-339933.svg)](https://nodejs.org/)
[![GUI Framework](https://img.shields.io/badge/GUI-PyQt6-41CD52.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![Audio Engine](https://img.shields.io/badge/Engine-FFmpeg%208.0-007808.svg)](https://ffmpeg.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*A studio-grade desktop and CLI application to extract, clean, master, and inspect audio streams from YouTube videos and playlists.*

</div>

---

## Overview

Most YouTube audio tools deliver low-bitrate streams or introduce artificial upsampling that inflates file size without acoustic benefit. **YouXtractor** takes a transparent, studio-grade approach:
- Directly selects the highest-fidelity Opus (~160 kbps) or AAC stream from YouTube servers.
- Uses **FFmpeg 8.0** with **LAME VBR V0** encoding for perceptual transparency.
- Employs **EBU R128 Loudness Normalization** (-14 LUFS) to eliminate jarring volume jumps.
- Uses native **C99** and **C++20** modules for sub-millisecond string sanitization, MPEG sync-word inspection, and Goertzel frequency cutoff detection.
- Provides a fast, modern **PyQt6 dark studio interface** alongside a full-featured **CLI**.

---

## Polyglot Architecture

YouXtractor is designed with high-performance polyglot engineering, combining four languages where each excels:

| Language | Layer | Purpose |
| :--- | :--- | :--- |
| **Python 3.10+** | Orchestrator & UI | PyQt6 studio interface, async QThread workers, yt-dlp & FFmpeg pipeline orchestration. |
| **C99** | Native Engine (`title_cleaner.dll`) | Fast title sanitization (removing tags like `[Official Video]`), Goertzel filter DSP for cutoff shelf calculation, and container magic-byte verification. |
| **C++20** | Frame & Tag Inspector (`audio_probe.exe`) | Standalone binary parser for ID3v2 frames (`TIT2`, `TPE1`, `APIC` album artwork) and MPEG Layer III frame sync headers (real bitrate, sample rate, Xing/LAME detection). |
| **JavaScript / Node.js** | Stream Inspector (`stream_inspector.mjs`) | Sub-second oEmbed metadata extraction and stream structure verification without network bloat. |

---

## Key Features

- **Pristine Audio Presets**:
  - `MP3 VBR V0 (~245 kbps)`: Variable bitrate with highest LAME perceptual quality (Recommended).
  - `MP3 320 kbps (CBR)`: Maximum compatibility for legacy hardware players.
  - `MP3 192 kbps (CBR)`: Storage-efficient standard MP3.
  - `Original Audio (Opus / M4A)`: Direct stream-copy extraction with zero re-encoding loss.
  - `FLAC Lossless` & `WAV (16-bit PCM)`: High-fidelity uncompressed containers.
- **EBU R128 Loudness Normalization**: Target -14 LUFS / True Peak -1.0 dBTP for uniform listening volume across all tracks.
- **Smart Title Cleaner**: Native C99 title parser automatically removes YouTube artifacts (`[Official Music Video]`, `4K Remastered`, `HD`, etc.) and formats files as `Artist - Title.mp3`.
- **Integrated 2D Spectrogram Analyzer**: Visualizes frequency spectrum (0–22 kHz) and calculates high-frequency shelf cutoffs to verify true acoustic quality.
- **Batch Queue & Playlist Support**: Convert single URLs, compound links, full playlists, or batch-import hundreds of URLs from `.txt` files.
- **Docked Audio Player**: Built-in mini audio player with scrub bar, volume slider, spectrum modal shortcut, and Explorer reveal.

---

## Directory Layout

```
YouXtractor/
├── app.py                      # GUI entry point (PyQt6)
├── cli.py                      # Full-featured Command-Line Interface
├── build_exe.py                # PyInstaller packaging script
├── Launch_GUI.bat              # 1-click Windows GUI launcher
├── Launch_CLI.bat              # 1-click Windows CLI launcher
├── sample_batch_urls.txt       # Sample batch download URL list
├── requirements.txt            # Python package requirements
├── LICENSE                     # MIT License
├── CONTRIBUTING.md             # Developer contribution guide
│
├── assets/
│   ├── app.ico                 # Multi-resolution Windows application icon
│   └── app.png                 # High-resolution application artwork
│
├── core/
│   ├── converter.py            # Core conversion pipeline (yt-dlp + FFmpeg)
│   └── ffmpeg_setup.py         # Static and dynamic FFmpeg discovery
│
├── native/
│   ├── title_cleaner.c         # C99 source: metadata cleaner & Goertzel DSP
│   ├── title_cleaner.dll       # Compiled C99 dynamic library (MinGW GCC)
│   ├── audio_probe.cpp         # C++20 source: MPEG frame & ID3v2 scanner
│   ├── audio_probe.exe         # Compiled C++20 binary executable (MinGW G++)
│   ├── build_native.bat        # MinGW compilation script for C and C++
│   └── native_bridge.py        # Python ctypes interface with pure fallbacks
│
├── tools/
│   └── stream_inspector.mjs    # Node.js sub-second stream inspector
│
└── ui/
    ├── main_window.py          # PyQt6 Studio main window
    ├── components.py           # Reusable widgets (preview card, player, history)
    ├── spectrogram_dialog.py   # Audio frequency spectrogram visualizer
    └── styles.py               # Dark theme design system
```

---

## Installation & Setup

### Prerequisites

- **Windows 10 / 11** (64-bit)
- **Python 3.10+**
- *(Optional)* **MinGW-W64 (GCC / G++)**: If recompiling native C/C++ modules.
- *(Optional)* **Node.js v18+**: For fast oEmbed stream inspection.

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/youxtractor.git
cd youxtractor
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

*(FFmpeg is automatically handled via `static-ffmpeg` if not already on your system PATH).*

### 3. Launching YouXtractor

#### Graphical User Interface (GUI)
```bash
python app.py
```
*Or double-click `Launch_GUI.bat`.*

#### Command-Line Interface (CLI)
```bash
python cli.py --help
```
*Or double-click `Launch_CLI.bat`.*

---

## CLI Usage Examples

### 1. Convert Single Video to MP3 V0
```bash
python cli.py "https://www.youtube.com/watch?v=jNQXAC9IVRw"
```

### 2. Convert with EBU R128 Loudness Normalization
```bash
python cli.py "https://www.youtube.com/watch?v=jNQXAC9IVRw" --normalize
```

### 3. Convert Entire Playlist
```bash
python cli.py "https://www.youtube.com/playlist?list=PL..." --preset mp3_320
```

### 4. Process Batch Queue from Text File
```bash
python cli.py --batch sample_batch_urls.txt --normalize
```

### 5. Inspect Spectrogram & Cutoff of Any Audio File
```bash
python cli.py "C:\Path\To\track.mp3"
```

---

## Compiling Native Modules

Precompiled binaries (`title_cleaner.dll` and `audio_probe.exe`) are included. If you modify the C/C++ source code, recompile with:

```bash
cd native
build_native.bat
cd ..
```

---

## Building Standalone Executable

To compile a single, zero-dependency `YouXtractor.exe` with bundled FFmpeg, native C/C++ binaries, and embedded multi-resolution icon:

```bash
python build_exe.py
```

The resulting `YouXtractor.exe` will be generated in the root directory.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

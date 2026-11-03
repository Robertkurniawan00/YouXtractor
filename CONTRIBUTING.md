# Contributing to YouXtractor

Thank you for your interest in contributing to **YouXtractor**! We welcome contributions from developers, audio engineers, and UI/UX designers.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Features](#suggesting-features)
  - [Pull Requests](#pull-requests)
- [Development Setup](#development-setup)
- [Architecture Overview](#architecture-overview)
- [Style Guidelines](#style-guidelines)

---

## Code of Conduct
This project is dedicated to providing a respectful, harassment-free experience for everyone. Please be considerate and respectful in discussions, issue threads, and pull requests.

---

## How Can I Contribute?

### Reporting Bugs
Before filing an issue, please check existing issues to ensure the problem hasn't already been reported:
- Clearly describe the bug and steps to reproduce.
- Include OS version, Python version, and any relevant terminal/log output.
- Avoid posting copyrighted media links when possible.

### Suggesting Features
Enhancement proposals should be submitted via GitHub Issues:
- Explain why the feature would be beneficial.
- Provide examples of expected behavior or user interface mockups.

### Pull Requests
1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feature/my-cool-feature
   ```
2. Make your changes and test thoroughly (both GUI and CLI).
3. Ensure no dead code or unused imports are introduced.
4. Keep all comments, docstrings, and commits in **English**.
5. Submit your pull request with a descriptive summary of your changes.

---

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/youxtractor.git
   cd youxtractor
   ```

2. **Set up a virtual environment (optional but recommended):**
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Compile native C/C++ modules (requires MinGW-W64 / GCC):**
   ```bash
   cd native
   build_native.bat
   cd ..
   ```

5. **Run YouXtractor:**
   - GUI Mode:
     ```bash
     python app.py
     ```
   - CLI Mode:
     ```bash
     python cli.py --help
     ```

---

## Architecture Overview

YouXtractor is designed as a polyglot system:
- **Python 3.10+ / PyQt6**: GUI presentation, asynchronous thread workers, state management.
- **C99 Dynamic Library (`native/title_cleaner.c`)**: Fast algorithmic string sanitization, ID3 heuristic parsing, and Goertzel filter for cutoff shelf measurement.
- **C++20 Binary Utility (`native/audio_probe.cpp`)**: Zero-dependency binary container probe for MPEG audio frames and ID3v2 tags.
- **Node.js Inspector (`tools/stream_inspector.mjs`)**: High-speed stream probe leveraging Node.js fetch runtime.
- **FFmpeg 8.0 Engine**: Industry-standard audio resampling, LAME VBR encoding, and EBU R128 loudness normalization.

---

## Style Guidelines
- **Python**: Follow PEP 8 guidelines. Write clear docstrings for all classes and methods.
- **C/C++**: Modern C99 / C++20 conventions with robust bounds checking.
- **Language**: All code, documentation, tooltips, and commit messages must be in English.

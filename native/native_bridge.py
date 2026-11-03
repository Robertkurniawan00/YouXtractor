"""
Native C Bridge for YouXtractor
Loads and interfaces with the compiled C library (title_cleaner.dll).
Includes pure Python fallbacks for 100% cross-platform compatibility.
"""

import os
import sys
import json
import ctypes
import re
import math
import subprocess
import tempfile

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    DLL_PATH = os.path.join(sys._MEIPASS, "native", "title_cleaner.dll")
    PROBE_EXE = os.path.join(sys._MEIPASS, "native", "audio_probe.exe")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DLL_PATH = os.path.join(BASE_DIR, "title_cleaner.dll")
    PROBE_EXE = os.path.join(BASE_DIR, "audio_probe.exe")

_c_lib = None
_has_c_lib = False

if os.path.isfile(DLL_PATH):
    try:
        _c_lib = ctypes.CDLL(DLL_PATH)
        # 1. clean_title_native
        _c_lib.clean_title_native.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int
        ]
        _c_lib.clean_title_native.restype = ctypes.c_int

        # 2. verify_audio_header
        _c_lib.verify_audio_header.argtypes = [ctypes.c_char_p]
        _c_lib.verify_audio_header.restype = ctypes.c_int

        # 3. sanitize_filename_native
        _c_lib.sanitize_filename_native.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int
        ]
        _c_lib.sanitize_filename_native.restype = ctypes.c_int

        # 4. analyze_frequency_cutoff_native
        _c_lib.analyze_frequency_cutoff_native.argtypes = [
            ctypes.POINTER(ctypes.c_short),
            ctypes.c_int,
            ctypes.c_int
        ]
        _c_lib.analyze_frequency_cutoff_native.restype = ctypes.c_int

        _has_c_lib = True
    except Exception:
        _has_c_lib = False


def is_native_c_active() -> bool:
    """Returns True if the compiled C engine is loaded."""
    return _has_c_lib


def clean_youtube_title(raw_title: str, uploader: str = "") -> tuple[str, str]:
    """
    Cleans YouTube title clutter and separates Artist & Track Title.
    Executed via compiled C engine with Python regex fallback.
    """
    if _has_c_lib and _c_lib:
        buf_size = 1024
        out_art = ctypes.create_string_buffer(buf_size)
        out_tit = ctypes.create_string_buffer(buf_size)

        c_raw = raw_title.encode("utf-8", errors="ignore")
        c_upl = uploader.encode("utf-8", errors="ignore")

        res = _c_lib.clean_title_native(c_raw, c_upl, out_art, out_tit, buf_size)
        if res == 0:
            art = out_art.value.decode("utf-8", errors="ignore").strip()
            tit = out_tit.value.decode("utf-8", errors="ignore").strip()
            if tit:
                return art, tit

    # Fallback to Python implementation
    title = raw_title.strip()
    title = re.sub(r"^(?:\[(?:MV|PV|HD|4K|AUDIO|OFFICIAL)\]|\((?:MV|PV|HD|4K|AUDIO|OFFICIAL)\)|MV\s*:\s*)\s*", "", title, flags=re.IGNORECASE)

    tag_keywords = [
        r"Official\s+(?:Music\s+)?Video(?:\s+Remastered)?",
        r"Official\s+Audio",
        r"Official\s+Lyrics?(?:\s+Video)?",
        r"Video\s+Clip",
        r"Music\s+Video",
        r"Clip\s+Officiel",
        r"Lyrics?(?:\s+Video)?",
        r"Lirik(?:\s+Video)?",
        r"Visualizer(?:\s+Video)?",
        r"Audio",
        r"Remastered(?:\s+\d{4})?",
        r"Live(?:\s+at\s+[^)\]]+)?",
        r"4K(?:\s+Remastered)?",
        r"HD",
        r"HQ",
        r"Full\s+Audio",
        r"Official"
    ]
    for kw in tag_keywords:
        title = re.sub(rf"\s*[\(\[]{kw}[\)\]]", "", title, flags=re.IGNORECASE)
        title = re.sub(rf"\s*-\s*{kw}\s*$", "", title, flags=re.IGNORECASE)

    title = re.sub(r"\s*\|\s*.*$", "", title).strip()

    artist = uploader
    separators = [" - ", " – ", " — ", " : "]
    for sep in separators:
        if sep in title:
            parts = title.split(sep, 1)
            artist = parts[0].strip()
            title = parts[1].strip()
            break

    if artist:
        artist = re.sub(r"VEVO$", "", artist, flags=re.IGNORECASE).strip()
        artist = re.sub(r"\s*-\s*Topic$", "", artist, flags=re.IGNORECASE).strip()
        artist = re.sub(r"\s+Official(?:\s+Channel)?$", "", artist, flags=re.IGNORECASE).strip()

    return artist.strip("\"' "), title.strip("\"' ")


def verify_audio_format(filepath: str) -> str:
    """
    Performs fast binary header validation in C.
    Returns: 'mp3', 'opus', 'm4a', 'flac', 'wav', or 'unknown'.
    """
    if _has_c_lib and _c_lib and os.path.isfile(filepath):
        c_path = filepath.encode("utf-8", errors="ignore")
        code = _c_lib.verify_audio_header(c_path)
        format_map = {
            1: "mp3",
            2: "opus",
            3: "m4a",
            4: "flac",
            5: "wav"
        }
        return format_map.get(code, "unknown")

    # Python Fallback
    try:
        with open(filepath, "rb") as f:
            header = f.read(16)
        if header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0):
            return "mp3"
        elif header.startswith(b"OggS"):
            return "opus"
        elif len(header) >= 8 and header[4:8] == b"ftyp":
            return "m4a"
        elif header.startswith(b"fLaC"):
            return "flac"
        elif header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WAVE":
            return "wav"
    except Exception:
        pass
    return "unknown"


def sanitize_filename(filename: str) -> str:
    """Sanitizes filename for Windows filesystem using C engine."""
    if _has_c_lib and _c_lib:
        buf_size = 512
        out_clean = ctypes.create_string_buffer(buf_size)
        c_name = filename.encode("utf-8", errors="ignore")
        if _c_lib.sanitize_filename_native(c_name, out_clean, buf_size) == 0:
            res = out_clean.value.decode("utf-8", errors="ignore").strip()
            if res:
                return res

    # Python fallback
    clean = re.sub(r'[\\/*?:"<>|]', "", filename).strip()
    return clean


def analyze_pcm_cutoff(pcm_bytes: bytes, sample_rate: int = 44100) -> int:
    """
    Computes upper frequency cutoff shelf using C Goertzel filter.
    Returns cutoff in Hz (e.g. 16000, 18500, 20500, 22000).
    """
    num_samples = len(pcm_bytes) // 2
    if num_samples < 1024:
        return 0

    if _has_c_lib and _c_lib:
        short_array_type = ctypes.c_short * num_samples
        short_array = short_array_type.from_buffer_copy(pcm_bytes)
        cutoff = _c_lib.analyze_frequency_cutoff_native(short_array, num_samples, sample_rate)
        if cutoff > 0:
            return cutoff

    # Python Fallback (Goertzel block-based)
    try:
        import struct
        samples = struct.unpack(f"<{num_samples}h", pcm_bytes)
        block_size = 4096 if num_samples >= 4096 else 2048
        num_blocks = num_samples // block_size
        if num_blocks <= 0:
            return 0

        def calc_block_power(f_target):
            omega = 2.0 * math.pi * f_target / sample_rate
            coeff = 2.0 * math.cos(omega)
            tot_p = 0.0
            for b in range(num_blocks):
                block = samples[b * block_size : (b + 1) * block_size]
                s_prev, s_prev2 = 0.0, 0.0
                for s_val in block:
                    s = float(s_val) + coeff * s_prev - s_prev2
                    s_prev2, s_prev = s_prev, s
                p = s_prev2**2 + s_prev**2 - coeff * s_prev * s_prev2
                tot_p += p / (block_size * block_size)
            return tot_p / num_blocks

        ref_power = max(calc_block_power(f) for f in [2000.0, 3500.0, 5000.0, 7000.0])
        if ref_power <= 0.001:
            return 0

        thresh = ref_power * 0.00001
        max_test = min(22000, (sample_rate // 2) - 500)
        for freq in range(max_test, 13500, -500):
            p = calc_block_power(freq)
            if p > thresh:
                return freq
    except Exception:
        pass
    return 16000


def generate_spectrogram(audio_path: str, output_png_path: str = None, color: str = "magma", width: int = 760, height: int = 240, ffmpeg_bin: str = "ffmpeg") -> str:
    """
    Renders high-resolution audio spectrogram with frequency legend using FFmpeg.
    """
    if not output_png_path:
        cache_dir = os.path.join(tempfile.gettempdir(), "youxtractor_cache")
        os.makedirs(cache_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(audio_path))[0]
        output_png_path = os.path.join(cache_dir, f"{base}_{color}.png")

    cmd = [
        ffmpeg_bin, "-y",
        "-i", audio_path,
        "-lavfi", f"showspectrumpic=s={width}x{height}:mode=combined:color={color}:scale=log:fscale=lin:legend=1",
        "-frames:v", "1",
        output_png_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_png_path


def inspect_audio_fidelity(audio_path: str, color_palette: str = "magma", ffmpeg_bin: str = "ffmpeg") -> dict:
    """
    Audio frequency distribution analysis:
    1. Generates 2D time-frequency spectrogram plot.
    2. Runs native Goertzel filter in C to measure upper frequency cutoff shelf.
    3. Returns technical acoustic metrics.
    """
    if not os.path.exists(audio_path):
        return {"success": False, "error": "Audio file not found."}

    # 1. Render spectrogram image
    png_path = generate_spectrogram(audio_path, color=color_palette, ffmpeg_bin=ffmpeg_bin)

    # 2. Extract 3-second PCM audio sample for frequency analysis
    pcm_slice = b""
    try:
        p = subprocess.Popen(
            [ffmpeg_bin, "-ss", "1", "-t", "3", "-i", audio_path, "-f", "s16le", "-ac", "1", "-ar", "44100", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        pcm_slice = p.stdout.read()
        p.wait()
    except Exception:
        pass

    if not pcm_slice:
        try:
            p = subprocess.Popen(
                [ffmpeg_bin, "-t", "3", "-i", audio_path, "-f", "s16le", "-ac", "1", "-ar", "44100", "-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            pcm_slice = p.stdout.read()
            p.wait()
        except Exception:
            pass

    # 3. Analyze upper frequency cutoff
    cutoff_hz = analyze_pcm_cutoff(pcm_slice, 44100) if pcm_slice else 0

    # 4. Technical acoustic classification
    if cutoff_hz >= 20000:
        badge = "Full Spectrum (>20 kHz)"
        color_code = "#4ade80"  # Green
        verdict = f"Frequency range extends up to {cutoff_hz / 1000:.1f} kHz. Audio signal preserves full high-frequency harmonics."
    elif cutoff_hz >= 18000:
        badge = "Standard HQ Spectrum (~18 kHz)"
        color_code = "#60a5fa"  # Blue
        verdict = f"High-frequency shelf detected at {cutoff_hz / 1000:.1f} kHz. Consistent with LAME V0 / Opus 160k psychoacoustic models."
    elif cutoff_hz >= 15500:
        badge = "Compressed Spectrum (~16 kHz)"
        color_code = "#fbbf24"  # Amber
        verdict = f"High-frequency cutoff at {cutoff_hz / 1000:.1f} kHz. Consistent with standard 128 kbps compression profiles."
    else:
        badge = "Narrow Bandwidth (<15 kHz)"
        color_code = "#f87171"  # Red
        verdict = f"Steep low-pass filter detected at {cutoff_hz / 1000:.1f} kHz. Source audio exhibits limited acoustic bandwidth."

    filesize_mb = os.path.getsize(audio_path) / (1024 * 1024)

    return {
        "success": True,
        "filepath": audio_path,
        "filename": os.path.basename(audio_path),
        "spectrogram_image": png_path,
        "cutoff_hz": cutoff_hz,
        "cutoff_str": f"{cutoff_hz / 1000:.1f} kHz" if cutoff_hz > 0 else "N/A",
        "badge": badge,
        "color_code": color_code,
        "verdict": verdict,
        "filesize_mb": f"{filesize_mb:.2f} MB",
        "color_palette": color_palette
    }


def probe_audio_file(audio_path: str) -> dict:
    """
    Inspects audio file technical container and frame properties using native C++ binary (audio_probe.exe).
    Returns dict containing format, bitrate, sample rate, channels, ID3 tags, and cover art status.
    """
    if not os.path.exists(audio_path):
        return {"valid": False, "error": "File not found"}

    if os.path.isfile(PROBE_EXE):
        try:
            res = subprocess.run(
                [PROBE_EXE, audio_path, "--json"],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0 and res.stdout.strip():
                return json.loads(res.stdout)
        except Exception:
            pass

    # Pure fallback
    return {
        "valid": True,
        "format": os.path.splitext(audio_path)[1].lower().replace(".", ""),
        "file_size_bytes": os.path.getsize(audio_path),
        "title": "",
        "artist": "",
        "album": "",
        "sample_rate": 44100,
        "bitrate_kbps": 0,
        "has_cover_art": False
    }

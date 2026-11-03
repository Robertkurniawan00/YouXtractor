import os
import shutil
import sys
import site

def ensure_ffmpeg() -> dict:
    """
    Ensures FFmpeg and FFprobe binaries are available on the system.
    Supports system PATH, static_ffmpeg package, and PyInstaller bundled binaries.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")

    if not ffmpeg_path or not ffprobe_path:
        try:
            import static_ffmpeg
            static_ffmpeg.add_paths()
            ffmpeg_path = shutil.which("ffmpeg")
            ffprobe_path = shutil.which("ffprobe")
        except Exception:
            pass

    if not ffmpeg_path:
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        candidates = [
            os.path.join(base_dir, "ffmpeg.exe"),
            os.path.join(base_dir, "static_ffmpeg", "bin", "win32", "ffmpeg.exe"),
        ]

        # Scan site-packages dynamically without hardcoded paths
        try:
            for site_dir in site.getsitepackages():
                candidates.append(os.path.join(site_dir, "static_ffmpeg", "bin", "win32", "ffmpeg.exe"))
        except Exception:
            pass

        user_site = site.getusersitepackages() if hasattr(site, "getusersitepackages") else ""
        if user_site:
            candidates.append(os.path.join(user_site, "static_ffmpeg", "bin", "win32", "ffmpeg.exe"))

        for p in candidates:
            if os.path.isfile(p):
                ffmpeg_path = p
                dir_path = os.path.dirname(p)
                os.environ["PATH"] = dir_path + os.pathsep + os.environ.get("PATH", "")
                ffprobe_candidate = os.path.join(dir_path, "ffprobe.exe")
                if os.path.isfile(ffprobe_candidate):
                    ffprobe_path = ffprobe_candidate
                break

    ffmpeg_dir = os.path.dirname(ffmpeg_path) if ffmpeg_path else ""

    return {
        "available": bool(ffmpeg_path and os.path.isfile(ffmpeg_path)),
        "ffmpeg": ffmpeg_path,
        "ffprobe": ffprobe_path,
        "directory": ffmpeg_dir
    }

if __name__ == "__main__":
    status = ensure_ffmpeg()
    print("FFmpeg Status:", status)

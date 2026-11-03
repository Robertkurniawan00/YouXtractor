import os
import sys
import subprocess
import shutil

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_NAME = "YouXtractor"

def build():
    print("==================================================")
    print("      YouXtractor - Build Standalone Executable   ")
    print("==================================================")
    
    # 1. Ensure native C & C++ binaries are compiled
    c_dll = os.path.join(BASE_DIR, "native", "title_cleaner.dll")
    cpp_exe = os.path.join(BASE_DIR, "native", "audio_probe.exe")
    if not os.path.isfile(c_dll) or not os.path.isfile(cpp_exe):
        print("[INFO] Compiling native C DLL and C++ Audio Probe...")
        bat_file = os.path.join(BASE_DIR, "native", "build_c.bat")
        subprocess.run(["cmd", "/c", bat_file], cwd=os.path.join(BASE_DIR, "native"))

    # 2. Locate static ffmpeg binaries
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except Exception:
        pass

    ffmpeg_exe = shutil.which("ffmpeg")
    ffprobe_exe = shutil.which("ffprobe")
    icon_path = os.path.join(BASE_DIR, "assets", "app.ico")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        f"--name={PROJECT_NAME}",
        "--windowed",
        "--onefile",
        "--clean",
        "--noconfirm",
        "--collect-all=yt_dlp",
        "--collect-all=PyQt6",
        f"--add-binary={c_dll};native",
        f"--add-binary={cpp_exe};native",
        f"--add-data={os.path.join(BASE_DIR, 'tools', 'stream_inspector.mjs')};tools",
        f"--add-data={os.path.join(BASE_DIR, 'assets')};assets",
    ]

    if os.path.isfile(icon_path):
        cmd.append(f"--icon={icon_path}")
        print(f"[ICON] Bundling application icon: {icon_path}")

    if ffmpeg_exe and os.path.isfile(ffmpeg_exe):
        cmd.append(f"--add-binary={ffmpeg_exe};.")
        print(f"[FFmpeg] Bundling FFmpeg binary: {ffmpeg_exe}")
    if ffprobe_exe and os.path.isfile(ffprobe_exe):
        cmd.append(f"--add-binary={ffprobe_exe};.")
        print(f"[FFprobe] Bundling FFprobe binary: {ffprobe_exe}")

    cmd.append(os.path.join(BASE_DIR, "app.py"))

    print("\nRunning PyInstaller packaging... Please wait.")
    subprocess.run(cmd, cwd=BASE_DIR, check=True)
    
    dist_file = os.path.join(BASE_DIR, "dist", f"{PROJECT_NAME}.exe")
    root_file = os.path.join(BASE_DIR, f"{PROJECT_NAME}.exe")

    if os.path.exists(dist_file):
        # Move to root directory for 1-click execution
        shutil.copy2(dist_file, root_file)
        
        # Clean up temporary build artifacts
        build_dir = os.path.join(BASE_DIR, "build")
        if os.path.isdir(build_dir):
            shutil.rmtree(build_dir, ignore_errors=True)

        dist_dir = os.path.join(BASE_DIR, "dist")
        if os.path.isdir(dist_dir):
            shutil.rmtree(dist_dir, ignore_errors=True)

        spec_file = os.path.join(BASE_DIR, f"{PROJECT_NAME}.spec")
        if os.path.isfile(spec_file):
            try:
                os.remove(spec_file)
            except Exception:
                pass

        file_size_mb = os.path.getsize(root_file) / (1024 * 1024)
        print("==================================================")
        print("[SUCCESS] Executable built successfully with custom icon:")
        print(f"[FILE] : {root_file}")
        print(f"[SIZE] : {file_size_mb:.2f} MB")
        print("==================================================")
        return True
    else:
        print("[ERROR] Build failed: Output executable not found in dist.")
        return False

if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)

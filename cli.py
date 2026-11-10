import os
import sys
import shutil
import argparse

# Ensure UTF-8 encoding in Windows console
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.converter import YouTubeAudioConverter, AUDIO_PRESETS, parse_url_list, is_compound_url, clean_ansi_text

# ANSI Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner():
    print(f"{CYAN}{BOLD}")
    print("================================================================")
    print("                    YouXtractor (CLI Mode)                     ")
    print("================================================================")
    print(f"{RESET}{YELLOW}[INFO]{RESET} YouTube streams native Opus ~160kbps / AAC ~128kbps master audio.")
    print("YouXtractor extracts and masters directly without artificial upscaling distortion.\n")

def progress_bar(data):
    stage = data.get("stage")
    if stage == "downloading":
        pct = data.get("percent", 0)
        speed = data.get("speed_str", "N/A")
        eta = data.get("eta_str", "00:00")
        bar_len = 25
        filled = int(bar_len * pct / 100)
        bar = "=" * filled + "-" * (bar_len - filled)
        sys.stdout.write(f"\r[{bar}] {pct:5.1f}% | Speed: {speed:>9} | ETA: {eta}")
        sys.stdout.flush()
    elif stage == "converting":
        sys.stdout.write(f"\n{YELLOW}[PROCESSING] Converting audio and embedding metadata...{RESET}\n")
        sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser(
        description="YouXtractor - High-Fidelity Audio Extractor & Mastering Suite"
    )
    parser.add_argument("url", nargs="?", help="YouTube Video/Playlist URL or path to .txt URL list")
    parser.add_argument(
        "--batch",
        "-b",
        default=None,
        help="Path to .txt file containing YouTube URLs (one URL per line)"
    )
    parser.add_argument(
        "--preset",
        choices=list(AUDIO_PRESETS.keys()),
        default="mp3_vbr0",
        help="Audio quality preset (default: mp3_vbr0)"
    )
    parser.add_argument(
        "--output",
        "-o",
        default=os.path.join(os.path.expanduser("~"), "Music", "YouXtractor"),
        help="Destination directory for audio files"
    )
    parser.add_argument(
        "--cookies",
        type=str,
        default=None,
        help="Import browser cookies (chrome, edge, firefox, brave) or path to cookies.txt file"
    )
    parser.add_argument(
        "--normalize",
        "-n",
        action="store_true",
        help="Enable EBU R128 Loudness Normalization (-14 LUFS)"
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Disable automatic YouTube title cleaning and tag parsing"
    )
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Download entire playlist if URL contains both video and playlist parameters"
    )
    parser.add_argument(
        "--spectrogram",
        "-s",
        action="store_true",
        help="Generate audio spectrogram (.png) and estimate frequency cutoff shelf"
    )
    parser.add_argument("--artist", default=None, help="Custom Artist tag")
    parser.add_argument("--title", default=None, help="Custom Title tag")
    parser.add_argument("--album", default=None, help="Custom Album tag (default: Single)")

    args = parser.parse_args()
    print_banner()

    batch_file = args.batch
    url_input = args.url

    # Check if input parameter is an existing local audio file for direct spectrogram inspection
    if url_input and os.path.isfile(url_input) and url_input.lower().endswith((".mp3", ".flac", ".wav", ".m4a", ".opus", ".ogg")):
        print(f"\n{CYAN}[ANALYSIS] Analyzing audio frequency spectrum: {url_input}{RESET}")
        from native.native_bridge import inspect_audio_fidelity
        from core.ffmpeg_setup import ensure_ffmpeg
        ff = ensure_ffmpeg().get("ffmpeg", "ffmpeg")
        spec_res = inspect_audio_fidelity(url_input, color_palette="magma", ffmpeg_bin=ff)
        if spec_res.get("success"):
            spec_img = os.path.splitext(url_input)[0] + "_spectrogram.png"
            shutil.copyfile(spec_res["spectrogram_image"], spec_img)
            print(f"   File           : {os.path.basename(url_input)}")
            print(f"   Spectrogram PNG: {spec_img}")
            print(f"   Cutoff Shelf   : {spec_res.get('cutoff_str')}")
            print(f"   Status         : {spec_res.get('badge')}")
            print(f"   Verdict        : {spec_res.get('verdict')}\n")
        else:
            print(f"{RED}[ERROR] Failed to analyze file: {spec_res.get('error')}{RESET}")
        return

    # Check if input parameter is a .txt file
    if url_input and os.path.isfile(url_input) and url_input.lower().endswith(".txt"):
        batch_file = url_input
        url_input = None

    # Interactive prompt if no arguments passed
    if not batch_file and not url_input:
        print(f"{BOLD}Select Download Mode:{RESET}")
        print("  [1] Single Track / Direct Playlist")
        print("  [2] Batch Queue from .txt File")
        try:
            mode_choice = input("Choice [1/2] (Default 1): ").strip()
            if mode_choice == "2":
                txt_path = input("Enter path to .txt file: ").strip().strip('"')
                if os.path.isfile(txt_path):
                    batch_file = txt_path
                else:
                    print(f"{RED}[ERROR] File not found: {txt_path}{RESET}")
                    return
            else:
                url_input = input(f"{BOLD}Enter YouTube URL: {RESET}").strip()
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return

    converter = YouTubeAudioConverter()
    output_dir = os.path.abspath(args.output)
    preset_choice = args.preset

    # --- Mode 1: Batch Download from .txt file ---
    if batch_file:
        if not os.path.isfile(batch_file):
            print(f"{RED}[ERROR] Batch file not found: {batch_file}{RESET}")
            return

        with open(batch_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        urls = parse_url_list(content)
        if not urls:
            print(f"{RED}[ERROR] No valid YouTube URLs found in file: {batch_file}{RESET}")
            return

        print(f"{GREEN}[OK] Loaded Batch File:{RESET} {batch_file}")
        print(f"  Total {len(urls)} valid URLs queued.\n")
        print(f"{BOLD}Preset:{RESET} {AUDIO_PRESETS[preset_choice]['name']}")
        print(f"{BOLD}Output Directory:{RESET} {output_dir}\n")

        def item_progress_cb(idx, data):
            stage = data.get("stage")
            if stage == "starting":
                print(f"\n{CYAN}[BATCH] [{idx+1}/{len(urls)}] Processing item...{RESET}")
            elif stage == "downloading":
                progress_bar(data)
            elif stage == "completed":
                print(f"{GREEN}[OK] [{idx+1}/{len(urls)}] Converted successfully.{RESET}")
            elif stage == "error":
                print(f"{RED}[ERROR] [{idx+1}/{len(urls)}] Failed: {clean_ansi_text(data.get('error'))}{RESET}")

        def overall_cb(data):
            curr = data.get("current_index")
            total = data.get("total_items")
            print(f"\n{BOLD}[STATUS] Queue {curr} of {total} ({data.get('overall_percent'):.0f}%){RESET}")

        res = converter.download_batch(
            urls=urls,
            output_dir=output_dir,
            preset_key=preset_choice,
            item_callback=item_progress_cb,
            overall_callback=overall_cb,
            log_callback=lambda msg: None,
            browser_cookies=args.cookies,
            normalize=args.normalize,
            auto_clean_tags=not args.no_clean
        )

        print(f"\n{GREEN}{BOLD}===================================================={RESET}")
        print(f"{GREEN}[OK] Batch Complete! Processed {len(res.get('downloaded_files', []))} audio tracks.{RESET}")
        print(f"Output folder: {output_dir}")
        return

    # --- Mode 2: Single Video / Direct Playlist ---
    if not url_input:
        print(f"{RED}[ERROR] YouTube URL cannot be empty.{RESET}")
        return

    is_comp = is_compound_url(url_input)
    force_single = (not args.playlist) if is_comp else False

    if is_comp:
        if force_single:
            print(f"{YELLOW}[INFO] Compound URL detected (contains both video & playlist parameters).{RESET}")
            print(f"   Mode: Downloading single video only (pass --playlist to download entire playlist).\n")
        else:
            print(f"{YELLOW}[INFO] Playlist mode active (--playlist flag enabled).\n{RESET}")

    print(f"{CYAN}[INFO] Extracting stream metadata...{RESET}")
    info = converter.get_info(url_input, browser_cookies=args.cookies, force_single=force_single)
    if not info.get("success"):
        print(f"{RED}[ERROR] Metadata extraction failed: {clean_ansi_text(info.get('error'))}{RESET}")
        return

    if info.get("is_playlist"):
        print(f"{GREEN}[OK] Playlist:{RESET} {info.get('title')}")
        print(f"  Channel : {info.get('uploader')} | Total: {info.get('count')} tracks")
    else:
        print(f"{GREEN}[OK] Video:{RESET} {info.get('title')}")
        print(f"  Artist/Channel : {info.get('uploader')}")
        print(f"  Duration       : {info.get('duration_str')}")
        print(f"  Source Stream  : {info.get('src_codec', '').upper()} @ ~{info.get('src_bitrate')} kbps ({info.get('src_samplerate')} Hz)")

    print(f"{BOLD}Preset:{RESET} {AUDIO_PRESETS[preset_choice]['name']}")
    print(f"{BOLD}Output Directory:{RESET} {output_dir}\n")
    print(f"{CYAN}[INFO] Starting conversion process...{RESET}")

    custom_tags = {}
    if args.title:
        custom_tags["title"] = args.title
    if args.artist:
        custom_tags["artist"] = args.artist
    if args.album:
        custom_tags["album"] = args.album

    result = converter.download(
        url=url_input,
        output_dir=output_dir,
        preset_key=preset_choice,
        progress_callback=progress_bar,
        log_callback=lambda msg: None,
        browser_cookies=args.cookies,
        normalize=args.normalize,
        custom_tags=custom_tags if custom_tags else None,
        auto_clean_tags=not args.no_clean,
        force_single=force_single
    )

    if result.get("success"):
        print(f"\n{GREEN}[OK] Finished! Files saved to:{RESET}")
        for f in result.get("files", []):
            print(f"   -> {f}")

        if args.spectrogram:
            print(f"\n{CYAN}[INFO] Generating spectrogram and frequency cutoff analysis...{RESET}")
            from native.native_bridge import inspect_audio_fidelity
            from core.ffmpeg_setup import ensure_ffmpeg
            ff = ensure_ffmpeg().get("ffmpeg", "ffmpeg")
            for f in result.get("files", []):
                spec_res = inspect_audio_fidelity(f, color_palette="magma", ffmpeg_bin=ff)
                if spec_res.get("success"):
                    spec_img = os.path.splitext(f)[0] + "_spectrogram.png"
                    shutil.copyfile(spec_res["spectrogram_image"], spec_img)
                    print(f"   [OK] Spectrogram PNG: {spec_img}")
                    print(f"        Cutoff Shelf   : {spec_res.get('cutoff_str')}")
                    print(f"        Status         : {spec_res.get('badge')}")
                    print(f"        Verdict        : {spec_res.get('verdict')}\n")
    else:
        err = clean_ansi_text(result.get('error'))
        print(f"\n{RED}[ERROR] Operation failed: {err}{RESET}")

if __name__ == "__main__":
    main()

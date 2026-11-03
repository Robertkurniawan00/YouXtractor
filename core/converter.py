import os
import sys
import re
import json
import shutil
import subprocess
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Dict, Any, Optional, Callable
import yt_dlp

from core.ffmpeg_setup import ensure_ffmpeg
from native.native_bridge import clean_youtube_title, verify_audio_format, sanitize_filename, probe_audio_file

ANSI_ESCAPE_PATTERN = re.compile(r'(?:\x1b|\u001b|\[\]|\?\?)*\[[0-9;]*[a-zA-Z]')

def clean_ansi_text(text: str) -> str:
    """Removes ANSI terminal color escape codes and formats clean error messages."""
    if not text:
        return ""
    cleaned = ANSI_ESCAPE_PATTERN.sub("", str(text)).strip()
    while cleaned.startswith("ERROR:"):
        cleaned = cleaned[6:].strip()
    return cleaned

def is_compound_url(url: str) -> bool:
    """
    Returns True if the URL contains both a video ID and a playlist ID
    (e.g., https://www.youtube.com/watch?v=...&list=... or https://youtu.be/...&list=...)
    """
    if not url:
        return False
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        has_video = ("v" in qs and bool(qs["v"][0])) or ("youtu.be" in parsed.netloc and bool(parsed.path.strip("/")))
        has_playlist = ("list" in qs and bool(qs["list"][0]))
        return bool(has_video and has_playlist)
    except Exception:
        return False

def extract_video_only_url(url: str) -> str:
    """Extracts only the single video URL, stripping playlist and index query parameters."""
    if not url:
        return url
    try:
        parsed = urlparse(url)
        if "youtu.be" in parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        qs = parse_qs(parsed.query)
        if "v" in qs:
            new_query = urlencode({"v": qs["v"][0]})
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    except Exception:
        pass
    return url

def extract_playlist_only_url(url: str) -> str:
    """Extracts the pure playlist URL if list parameter is present."""
    if not url:
        return url
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "list" in qs:
            p_id = qs["list"][0]
            return f"https://www.youtube.com/playlist?list={p_id}"
    except Exception:
        pass
    return url

def quick_node_stream_probe(url: str) -> Optional[dict]:
    """
    Fast initial YouTube metadata inspection via Node.js stream inspector.
    """
    node_bin = shutil.which("node")
    if not node_bin:
        return None

    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    inspector_script = os.path.join(base_dir, "tools", "stream_inspector.mjs")
    if not os.path.isfile(inspector_script):
        return None

    try:
        res = subprocess.run(
            [node_bin, inspector_script, url],
            capture_output=True,
            text=True,
            check=False,
            timeout=4
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            if not data.get("error"):
                return data
    except Exception:
        pass
    return None

AUDIO_PRESETS = {
    "mp3_vbr0": {
        "name": "MP3 VBR V0 (~245 kbps) · Recommended",
        "description": "Dynamic variable bitrate with perceptual transparency. Ideal acoustic quality.",
        "ext": "mp3",
        "is_reencode": True,
        "codec": "mp3",
        "quality": "0",  # LAME highest quality VBR
    },
    "mp3_320": {
        "name": "MP3 320 kbps (CBR)",
        "description": "Constant 320 kbps bitrate for legacy players and maximum hardware compatibility.",
        "ext": "mp3",
        "is_reencode": True,
        "codec": "mp3",
        "quality": "320",
    },
    "mp3_192": {
        "name": "MP3 192 kbps (CBR)",
        "description": "Balanced standard audio quality for storage-conscious libraries.",
        "ext": "mp3",
        "is_reencode": True,
        "codec": "mp3",
        "quality": "192",
    },
    "original": {
        "name": "Original Audio (Opus / M4A)",
        "description": "Direct stream extraction from YouTube without re-encoding (0% generation loss).",
        "ext": "original",
        "is_reencode": False,
        "codec": None,
        "quality": None,
    },
    "flac": {
        "name": "FLAC Lossless",
        "description": "Free Lossless Audio Codec container.",
        "ext": "flac",
        "is_reencode": True,
        "codec": "flac",
        "quality": "0",
    },
    "wav": {
        "name": "WAV (16-bit PCM)",
        "description": "Uncompressed raw pulse-code modulation audio.",
        "ext": "wav",
        "is_reencode": True,
        "codec": "wav",
        "quality": "0",
    }
}

def parse_url_list(content: str) -> list:
    """
    Parses a list of URLs from multi-line text or a .txt file.
    Filters out comments, empty lines, and validates YouTube links.
    """
    lines = content.strip().splitlines()
    valid_urls = []
    seen = set()

    for line in lines:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        url_match = re.search(r"https?://[^\s]+", cleaned)
        url = url_match.group(0) if url_match else cleaned
        
        if any(domain in url.lower() for domain in ["youtube.com", "youtu.be", "music.youtube.com"]):
            if url not in seen:
                seen.add(url)
                valid_urls.append(url)
        elif url.startswith("http://") or url.startswith("https://"):
            if url not in seen:
                seen.add(url)
                valid_urls.append(url)

    return valid_urls

def apply_custom_metadata(filepath: str, tags: dict, ffmpeg_exe: str = "ffmpeg") -> str:
    """
    Injects ID3v2 metadata (Title, Artist, Album, Album Artist) into audio files
    using FFmpeg stream-copy without re-encoding (zero quality loss, instant).
    Also renames physical file to 'Artist - Title.ext'.
    Returns final file path.
    """
    if not os.path.exists(filepath):
        return filepath

    dir_name = os.path.dirname(filepath)
    base_name, ext = os.path.splitext(filepath)

    title = tags.get("title", "").strip()
    artist = tags.get("artist", "").strip()
    album = tags.get("album", "").strip()

    if not title and not artist:
        return filepath

    tmp_path = os.path.join(dir_name, f"__tmp_tag_{os.path.basename(filepath)}")

    cmd = [
        ffmpeg_exe, "-y",
        "-i", filepath,
        "-map", "0",
        "-c", "copy"
    ]

    if ext.lower() == ".mp3":
        cmd.extend(["-id3v2_version", "3"])

    if title:
        cmd.extend(["-metadata", f"title={title}"])
    if artist:
        cmd.extend(["-metadata", f"artist={artist}"])
        cmd.extend(["-metadata", f"album_artist={artist}"])
    if album:
        cmd.extend(["-metadata", f"album={album}"])

    cmd.append(tmp_path)

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            if artist and title:
                safe_artist = sanitize_filename(artist)
                safe_title = sanitize_filename(title)
                new_filename = f"{safe_artist} - {safe_title}{ext}"
            elif title:
                safe_title = sanitize_filename(title)
                new_filename = f"{safe_title}{ext}"
            else:
                new_filename = os.path.basename(filepath)

            target_path = os.path.join(dir_name, new_filename)

            try:
                os.remove(filepath)
            except Exception:
                pass

            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass

            shutil.move(tmp_path, target_path)
            return target_path
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    return filepath

class YouTubeAudioConverter:
    def __init__(self):
        self.ffmpeg_info = ensure_ffmpeg()
        self.ffmpeg_dir = self.ffmpeg_info.get("directory", "")
        self._is_cancelled = False

    def cancel(self):
        """Requests cancellation of active download."""
        self._is_cancelled = True

    def reset_cancel(self):
        self._is_cancelled = False

    def _get_base_ydl_opts(self, browser_cookies: Optional[str] = None) -> Dict[str, Any]:
        """Base yt-dlp configuration for maximum speed and reliability."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "ignoreerrors": True,
            "remote_components": ["ejs:github"],
            "socket_timeout": 30,
            "retries": 10,
            "fragment_retries": 10,
            "nocheckcertificate": True,
        }

        node_bin = shutil.which("node")
        if node_bin:
            opts["js_runtimes"] = {"node": {"path": node_bin}}
        else:
            opts["js_runtimes"] = {"node": {}}

        if self.ffmpeg_dir:
            opts["ffmpeg_location"] = self.ffmpeg_dir

        if browser_cookies and browser_cookies.lower() not in ("none", "", "tidak ada"):
            opts["cookiesfrombrowser"] = (browser_cookies.lower(),)

        return opts

    def get_info(self, url: str, browser_cookies: Optional[str] = None, force_single: bool = False) -> Dict[str, Any]:
        """
        Retrieves complete YouTube metadata without downloading content.
        Analyzes original audio stream specs transparently.
        """
        is_compound = is_compound_url(url)
        target_url = extract_video_only_url(url) if (force_single and is_compound) else url

        opts = self._get_base_ydl_opts(browser_cookies)
        if force_single and is_compound:
            opts["noplaylist"] = True
        else:
            opts["extract_flat"] = "in_playlist"

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(target_url, download=False)
        except Exception as e:
            return {
                "success": False,
                "error": clean_ansi_text(str(e))
            }

        if not info:
            return {"success": False, "error": "Unable to extract stream metadata from URL."}

        is_playlist = ("_type" in info and info["_type"] == "playlist") and not (force_single and is_compound)
        
        if is_playlist:
            entries = info.get("entries", [])
            playlist_title = info.get("title", "YouTube Playlist")
            item_count = len(list(entries)) if entries else 0
            first_entry = entries[0] if entries and len(entries) > 0 else {}
            
            return {
                "success": True,
                "is_playlist": True,
                "is_compound": is_compound,
                "video_url": extract_video_only_url(url) if is_compound else "",
                "playlist_url": extract_playlist_only_url(url) if is_compound else url,
                "title": playlist_title,
                "uploader": info.get("uploader") or info.get("channel") or "Unknown Channel",
                "count": item_count,
                "thumbnail": first_entry.get("thumbnail") or info.get("thumbnail") or "",
                "url": url,
                "raw_info": info
            }

        # Single Video
        formats = info.get("formats", [])
        best_audio_opus = None
        best_audio_aac = None
        highest_abr = 0

        for f in formats:
            acodec = f.get("acodec", "")
            if f.get("vcodec") == "none" and acodec and acodec != "none":
                abr = f.get("abr") or 0
                asr = f.get("asr") or 0
                if "opus" in acodec.lower():
                    if not best_audio_opus or abr > (best_audio_opus.get("abr") or 0):
                        best_audio_opus = f
                elif "mp4a" in acodec.lower() or "aac" in acodec.lower():
                    if not best_audio_aac or abr > (best_audio_aac.get("abr") or 0):
                        best_audio_aac = f
                if abr > highest_abr:
                    highest_abr = abr

        primary_audio = best_audio_opus or best_audio_aac or (formats[0] if formats else {})
        src_codec = primary_audio.get("acodec", "Unknown") if primary_audio else "Unknown"
        src_abr = primary_audio.get("abr") or highest_abr or 160
        src_asr = primary_audio.get("asr") or 48000

        stream_note = (
            f"Native YouTube audio stream: {src_codec.upper()} ~{int(src_abr)} kbps ({src_asr} Hz)."
        )

        duration = info.get("duration", 0)
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        duration_str = f"{minutes:02d}:{seconds:02d}" if duration else "00:00"

        raw_title = info.get("title", "Unknown Title")
        raw_uploader = info.get("uploader") or info.get("channel") or "Unknown Artist"
        clean_artist, clean_title = clean_youtube_title(raw_title, raw_uploader)

        return {
            "success": True,
            "is_playlist": False,
            "is_compound": is_compound,
            "video_url": extract_video_only_url(url) if is_compound else url,
            "playlist_url": extract_playlist_only_url(url) if is_compound else "",
            "id": info.get("id"),
            "title": raw_title,
            "uploader": raw_uploader,
            "clean_title": clean_title,
            "clean_artist": clean_artist,
            "clean_album": "Single",
            "duration": duration,
            "duration_str": duration_str,
            "thumbnail": info.get("thumbnail") or "",
            "view_count": info.get("view_count", 0),
            "upload_date": info.get("upload_date", ""),
            "src_codec": src_codec,
            "src_bitrate": int(src_abr) if src_abr else 160,
            "src_samplerate": src_asr,
            "no_gimmick_note": stream_note,
            "stream_note": stream_note,
            "url": url,
            "raw_info": info
        }

    def download(
        self,
        url: str,
        output_dir: str,
        preset_key: str = "mp3_vbr0",
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        browser_cookies: Optional[str] = None,
        normalize: bool = False,
        custom_tags: Optional[Dict[str, str]] = None,
        auto_clean_tags: bool = True,
        force_single: bool = False
    ) -> Dict[str, Any]:
        """
        Downloads and converts YouTube audio with highest fidelity,
        embedding ID3v2 tags, high-resolution album artwork,
        EBU R128 loudness normalization, and native title cleaning.
        """
        self.reset_cancel()
        os.makedirs(output_dir, exist_ok=True)
        preset = AUDIO_PRESETS.get(preset_key, AUDIO_PRESETS["mp3_vbr0"])

        def log(msg: str):
            if log_callback:
                log_callback(msg)

        def emit_progress(data: Dict[str, Any]):
            if progress_callback:
                progress_callback(data)

        is_compound = is_compound_url(url)
        target_url = extract_video_only_url(url) if (force_single and is_compound) else url

        log(f"Starting conversion task: {preset['name']}")
        log(f"Output directory: {output_dir}")
        if force_single and is_compound:
            log("Single Track mode active (ignoring playlist parameter).")
        if normalize:
            log("Loudness Normalization active: EBU R128 (Target: -14 LUFS, True Peak: -1.0 dBTP)")

        ydl_opts = self._get_base_ydl_opts(browser_cookies)
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["outtmpl"] = os.path.join(output_dir, "%(title)s.%(ext)s")
        ydl_opts["writethumbnail"] = True

        if force_single and is_compound:
            ydl_opts["noplaylist"] = True

        if normalize and preset["is_reencode"]:
            ydl_opts["postprocessor_args"] = {
                "ExtractAudio": ["-af", "loudnorm=I=-14:TP=-1.0:LRA=11"]
            }

        postprocessors = []

        if preset["is_reencode"]:
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": preset["codec"],
                "preferredquality": preset["quality"],
            })
            postprocessors.append({
                "key": "FFmpegMetadata",
                "add_metadata": True,
            })
            postprocessors.append({
                "key": "EmbedThumbnail",
                "already_have_thumbnail": False,
            })
        else:
            postprocessors.append({
                "key": "FFmpegMetadata",
                "add_metadata": True,
            })

        ydl_opts["postprocessors"] = postprocessors

        downloaded_files = []

        def ydl_hook(d):
            if self._is_cancelled:
                raise Exception("Process cancelled by user.")

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                percent = (downloaded / total * 100) if total > 0 else 0
                speed = d.get("speed") or 0
                eta = d.get("eta") or 0

                speed_str = f"{speed / (1024 * 1024):.2f} MB/s" if speed else "N/A"
                eta_str = f"{int(eta // 60):02d}:{int(eta % 60):02d}" if eta else "00:00"

                emit_progress({
                    "stage": "downloading",
                    "percent": percent,
                    "speed_str": speed_str,
                    "eta_str": eta_str,
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                    "filename": os.path.basename(d.get("filename", ""))
                })
            elif status == "finished":
                emit_progress({
                    "stage": "converting",
                    "percent": 100,
                    "message": "Converting audio & embedding HQ ID3 artwork...",
                    "filename": os.path.basename(d.get("filename", ""))
                })
                log("Download stream complete. Starting FFmpeg post-processing...")

        ydl_opts["progress_hooks"] = [ydl_hook]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target_url, download=True)
                if info:
                    if "entries" in info:
                        for entry in info["entries"]:
                            if entry and isinstance(entry, dict):
                                try:
                                    downloaded_files.append(ydl.prepare_filename(entry))
                                except Exception:
                                    pass
                    else:
                        downloaded_files.append(ydl.prepare_filename(info))

            final_files = []
            expected_ext = "." + preset["ext"] if preset["is_reencode"] else None

            for fpath in downloaded_files:
                base, ext = os.path.splitext(fpath)
                if expected_ext:
                    target_path = base + expected_ext
                    if os.path.exists(target_path):
                        final_files.append(target_path)
                    elif os.path.exists(fpath):
                        final_files.append(fpath)
                else:
                    if os.path.exists(fpath):
                        final_files.append(fpath)

            if not final_files:
                raise Exception("No audio files were downloaded. The video or playlist may be unavailable, deleted, or private.")

            # Smart Title Cleaning & Custom Tag Injection
            tagged_files = []
            ffmpeg_bin = self.ffmpeg_info.get("ffmpeg") or "ffmpeg"

            for fpath in final_files:
                target_tags = {}
                if custom_tags and (custom_tags.get("title") or custom_tags.get("artist")):
                    target_tags = custom_tags
                elif auto_clean_tags and preset["is_reencode"]:
                    v_title = info.get("title", "") if info else os.path.splitext(os.path.basename(fpath))[0]
                    v_artist = info.get("uploader", "") if info else ""
                    c_art, c_tit = clean_youtube_title(v_title, v_artist)
                    target_tags = {
                        "artist": c_art,
                        "title": c_tit,
                        "album": "Single"
                    }

                if target_tags:
                    log(f"Embedding clean ID3 tags: {target_tags.get('artist')} - {target_tags.get('title')}")
                    new_fpath = apply_custom_metadata(fpath, target_tags, ffmpeg_bin)
                    tagged_files.append(new_fpath)
                else:
                    tagged_files.append(fpath)

            final_files = tagged_files

            # Binary container verification (C DLL) & frame inspection (C++)
            for f in final_files:
                fmt_detected = verify_audio_format(f)
                if fmt_detected != "unknown":
                    log(f"Verified container format (C DLL): {fmt_detected.upper()}")
                
                probe_res = probe_audio_file(f)
                if probe_res.get("valid"):
                    br = probe_res.get("bitrate_kbps", 0)
                    sr = probe_res.get("sample_rate", 0)
                    art_status = "Available" if probe_res.get("has_cover_art") else "None"
                    log(f"Binary frame analysis (C++): {br} kbps | {sr} Hz | Cover Art: {art_status}")

            log("Conversion and metadata tagging completed.")
            emit_progress({
                "stage": "completed",
                "percent": 100,
                "message": "Audio conversion completed.",
                "files": final_files
            })

            return {
                "success": True,
                "files": final_files,
                "output_dir": output_dir
            }

        except Exception as e:
            raw_err = str(e)
            err_msg = clean_ansi_text(raw_err)
            log(f"Error encountered: {err_msg}")
            emit_progress({
                "stage": "error",
                "message": err_msg
            })
            return {
                "success": False,
                "error": err_msg
            }

    def download_batch(
        self,
        urls: list,
        output_dir: str,
        preset_key: str = "mp3_vbr0",
        item_callback: Optional[Callable[[int, Dict[str, Any]], None]] = None,
        overall_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        browser_cookies: Optional[str] = None,
        normalize: bool = False,
        auto_clean_tags: bool = True
    ) -> Dict[str, Any]:
        """
        Processes a sequential queue of URLs with per-item and overall progress reporting.
        """
        self.reset_cancel()
        total_items = len(urls)
        results = []
        all_downloaded_files = []

        if log_callback:
            log_callback(f"Starting Batch Download task: {total_items} items queued.")
            if normalize:
                log_callback("Loudness Normalization active: EBU R128 (-14 LUFS) for all queue items.")

        for idx, url in enumerate(urls):
            if self._is_cancelled:
                if log_callback:
                    log_callback("Batch download cancelled by user.")
                break

            current_num = idx + 1
            if overall_callback:
                overall_callback({
                    "current_index": current_num,
                    "total_items": total_items,
                    "current_url": url,
                    "overall_percent": (idx / total_items) * 100
                })

            if item_callback:
                item_callback(idx, {
                    "stage": "starting",
                    "status": "Processing...",
                    "percent": 0
                })

            def per_item_progress(prog_data):
                if item_callback:
                    item_callback(idx, prog_data)

            res = self.download(
                url=url,
                output_dir=output_dir,
                preset_key=preset_key,
                progress_callback=per_item_progress,
                log_callback=log_callback,
                browser_cookies=browser_cookies,
                normalize=normalize,
                auto_clean_tags=auto_clean_tags
            )

            res["url"] = url
            res["index"] = idx
            results.append(res)

            if res.get("success"):
                files = res.get("files", [])
                all_downloaded_files.extend(files)
                if item_callback:
                    item_callback(idx, {
                        "stage": "completed",
                        "status": "Ready",
                        "percent": 100,
                        "files": files
                    })
            else:
                if item_callback:
                    item_callback(idx, {
                        "stage": "error",
                        "status": "Failed",
                        "error": res.get("error")
                    })

        if overall_callback:
            overall_callback({
                "current_index": total_items,
                "total_items": total_items,
                "overall_percent": 100
            })

        return {
            "success": not self._is_cancelled,
            "total_processed": len(results),
            "total_items": total_items,
            "downloaded_files": all_downloaded_files,
            "results": results
        }

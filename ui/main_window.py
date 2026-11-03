import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QFileDialog, QProgressBar,
    QTextEdit, QPlainTextEdit, QScrollArea, QFrame, QMessageBox,
    QApplication, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QIcon

from core.converter import (
    YouTubeAudioConverter, AUDIO_PRESETS, parse_url_list,
    is_compound_url, extract_playlist_only_url, clean_ansi_text
)
from native.native_bridge import is_native_c_active
from ui.components import VideoPreviewCard, AudioPlayerWidget, HistoryListItem
from ui.spectrogram_dialog import SpectrogramDialog
from ui.styles import STYLESHEET

DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Music", "YouXtractor")
if not os.path.exists(DEFAULT_DOWNLOAD_DIR):
    try:
        os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
    except Exception:
        DEFAULT_DOWNLOAD_DIR = os.path.dirname(os.path.abspath(__file__))


class FetchInfoWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, converter: YouTubeAudioConverter, url: str, cookies: str, force_single: bool = True):
        super().__init__()
        self.converter = converter
        self.url = url
        self.cookies = cookies
        self.force_single = force_single

    def run(self):
        try:
            res = self.converter.get_info(self.url, self.cookies, force_single=self.force_single)
            if res.get("success"):
                self.finished.emit(res)
            else:
                raw_err = res.get("error", "Failed to retrieve stream metadata.")
                self.error.emit(clean_ansi_text(raw_err))
        except Exception as e:
            self.error.emit(clean_ansi_text(str(e)))


class DownloadWorker(QThread):
    progress = pyqtSignal(dict)
    log = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, converter: YouTubeAudioConverter, url: str, output_dir: str, preset: str, cookies: str, normalize: bool = False, custom_tags: dict = None, auto_clean: bool = True, force_single: bool = True):
        super().__init__()
        self.converter = converter
        self.url = url
        self.output_dir = output_dir
        self.preset = preset
        self.cookies = cookies
        self.normalize = normalize
        self.custom_tags = custom_tags
        self.auto_clean = auto_clean
        self.force_single = force_single

    def run(self):
        try:
            res = self.converter.download(
                url=self.url,
                output_dir=self.output_dir,
                preset_key=self.preset,
                progress_callback=lambda d: self.progress.emit(d),
                log_callback=lambda m: self.log.emit(m),
                browser_cookies=self.cookies,
                normalize=self.normalize,
                custom_tags=self.custom_tags,
                auto_clean_tags=self.auto_clean,
                force_single=self.force_single
            )
            self.finished.emit(res)
        except Exception as e:
            self.finished.emit({"success": False, "error": clean_ansi_text(str(e))})


class BatchDownloadWorker(QThread):
    item_progress = pyqtSignal(int, dict)
    overall_progress = pyqtSignal(dict)
    log = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, converter: YouTubeAudioConverter, urls: list, output_dir: str, preset: str, cookies: str, normalize: bool = False, auto_clean: bool = True):
        super().__init__()
        self.converter = converter
        self.urls = urls
        self.output_dir = output_dir
        self.preset = preset
        self.cookies = cookies
        self.normalize = normalize
        self.auto_clean = auto_clean

    def run(self):
        try:
            res = self.converter.download_batch(
                urls=self.urls,
                output_dir=self.output_dir,
                preset_key=self.preset,
                item_callback=lambda idx, d: self.item_progress.emit(idx, d),
                overall_callback=lambda d: self.overall_progress.emit(d),
                log_callback=lambda m: self.log.emit(m),
                browser_cookies=self.cookies,
                normalize=self.normalize,
                auto_clean_tags=self.auto_clean
            )
            self.finished.emit(res)
        except Exception as e:
            self.finished.emit({"success": False, "error": clean_ansi_text(str(e))})


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouXtractor - Audio Extractor & Mastering Suite")
        self.resize(840, 890)
        self.setMinimumSize(740, 720)

        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "app.ico")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.converter = YouTubeAudioConverter()
        self.current_video_info = None
        self.info_worker = None
        self.download_worker = None
        self.batch_worker = None
        self.batch_urls = []

        self.setStyleSheet(STYLESHEET)
        self.init_ui()

    def init_ui(self):
        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        root_layout = QVBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Scroll Area for Workspace
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root_layout.addWidget(scroll_area, stretch=1)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        workspace_layout = QVBoxLayout(content_widget)
        workspace_layout.setContentsMargins(28, 24, 28, 24)
        workspace_layout.setSpacing(16)

        # Header Bar (Branding)
        header_bar = QHBoxLayout()
        header_meta = QVBoxLayout()
        header_meta.setSpacing(1)

        app_title = QLabel("YouXtractor")
        app_title.setObjectName("AppBrand")
        header_meta.addWidget(app_title)

        app_subtitle = QLabel("High-Fidelity Audio Extractor & Mastering Suite")
        app_subtitle.setObjectName("AppTagline")
        header_meta.addWidget(app_subtitle)

        header_bar.addLayout(header_meta)
        header_bar.addStretch()

        c_engine_text = "C/C++ Native" if is_native_c_active() else "Py-Bridge"
        self.lbl_tech = QLabel(f"FFmpeg 8.0 · {c_engine_text} · Node.js")
        self.lbl_tech.setObjectName("EngineActiveBadge")
        header_bar.addWidget(self.lbl_tech)

        workspace_layout.addLayout(header_bar)

        # 2. Main Studio Card
        studio_card = QFrame()
        studio_card.setObjectName("StudioCard")
        card_layout = QVBoxLayout(studio_card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(14)

        # Segmented Control Tabs
        self.tabs = QTabWidget()

        # --- TAB 1: Single Stream ---
        tab_single = QWidget()
        single_layout = QVBoxLayout(tab_single)
        single_layout.setContentsMargins(2, 8, 2, 2)
        single_layout.setSpacing(12)

        # Spotlight Input Bar
        url_input_box = QVBoxLayout()
        url_input_box.setSpacing(6)

        lbl_url = QLabel("MEDIA URL")
        lbl_url.setObjectName("SectionHeader")
        url_input_box.addWidget(lbl_url)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Paste YouTube video or playlist link...")
        self.txt_url.returnPressed.connect(self.check_url_info)
        self.txt_url.textChanged.connect(self._on_url_text_changed)
        input_row.addWidget(self.txt_url, stretch=1)

        self.btn_paste = QPushButton("Paste")
        self.btn_paste.setObjectName("GhostButton")
        self.btn_paste.clicked.connect(self._paste_clipboard)
        input_row.addWidget(self.btn_paste)

        self.btn_inspect = QPushButton("Inspect")
        self.btn_inspect.clicked.connect(self.check_url_info)
        input_row.addWidget(self.btn_inspect)

        url_input_box.addLayout(input_row)

        # Compound URL Playlist Selector
        self.compound_banner = QFrame()
        self.compound_banner.setObjectName("PlaylistNoticeCard")
        self.compound_banner.setVisible(False)
        compound_layout = QHBoxLayout(self.compound_banner)
        compound_layout.setContentsMargins(12, 8, 12, 8)
        compound_layout.setSpacing(14)

        lbl_notice = QLabel("Playlist detected in link:")
        lbl_notice.setStyleSheet("font-size: 11px; font-weight: 600; color: #94a3b8;")
        compound_layout.addWidget(lbl_notice)

        self.btn_group_mode = QButtonGroup(self)
        self.radio_mode_single = QRadioButton("Single Video Only")
        self.radio_mode_single.setChecked(True)
        self.radio_mode_single.toggled.connect(self._on_compound_mode_changed)
        self.btn_group_mode.addButton(self.radio_mode_single)
        compound_layout.addWidget(self.radio_mode_single)

        self.radio_mode_playlist = QRadioButton("Entire Playlist")
        self.radio_mode_playlist.toggled.connect(self._on_compound_mode_changed)
        self.btn_group_mode.addButton(self.radio_mode_playlist)
        compound_layout.addWidget(self.radio_mode_playlist)

        compound_layout.addStretch()

        self.btn_send_batch = QPushButton("Send to Batch Queue")
        self.btn_send_batch.setObjectName("GhostButton")
        self.btn_send_batch.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        self.btn_send_batch.clicked.connect(self._send_playlist_to_batch)
        compound_layout.addWidget(self.btn_send_batch)

        url_input_box.addWidget(self.compound_banner)
        single_layout.addLayout(url_input_box)

        # Media Preview Card
        self.preview_card = VideoPreviewCard()
        single_layout.addWidget(self.preview_card)

        # Metadata & Tag Editor
        self.tag_card = QFrame()
        self.tag_card.setObjectName("InnerSurface")
        self.tag_card.setVisible(False)
        tag_layout = QVBoxLayout(self.tag_card)
        tag_layout.setContentsMargins(12, 10, 12, 10)
        tag_layout.setSpacing(8)

        tag_header = QHBoxLayout()
        lbl_tag_title = QLabel("METADATA TAGS")
        lbl_tag_title.setObjectName("SectionHeader")
        tag_header.addWidget(lbl_tag_title)
        tag_header.addStretch()

        self.chk_auto_clean = QCheckBox("Smart Title Cleaner")
        self.chk_auto_clean.setChecked(True)
        self.chk_auto_clean.setToolTip("Auto-cleans YouTube clutter ('Official Video', '[HD]', etc.) and formats Artist - Title")
        tag_header.addWidget(self.chk_auto_clean)
        tag_layout.addLayout(tag_header)

        fields_row = QHBoxLayout()
        fields_row.setSpacing(8)

        # Artist
        artist_col = QVBoxLayout()
        artist_col.setSpacing(3)
        lbl_art = QLabel("Artist")
        lbl_art.setObjectName("FieldLabel")
        self.txt_artist = QLineEdit()
        self.txt_artist.setPlaceholderText("Artist Name")
        artist_col.addWidget(lbl_art)
        artist_col.addWidget(self.txt_artist)
        fields_row.addLayout(artist_col, stretch=1)

        # Title
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        lbl_tit = QLabel("Title")
        lbl_tit.setObjectName("FieldLabel")
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Track Title")
        title_col.addWidget(lbl_tit)
        title_col.addWidget(self.txt_title)
        fields_row.addLayout(title_col, stretch=2)

        # Album
        album_col = QVBoxLayout()
        album_col.setSpacing(3)
        lbl_alb = QLabel("Album")
        lbl_alb.setObjectName("FieldLabel")
        self.txt_album = QLineEdit()
        self.txt_album.setPlaceholderText("Single")
        album_col.addWidget(lbl_alb)
        album_col.addWidget(self.txt_album)
        fields_row.addLayout(album_col, stretch=1)

        tag_layout.addLayout(fields_row)
        single_layout.addWidget(self.tag_card)

        self.tabs.addTab(tab_single, "Single Track")

        # --- TAB 2: Batch Queue ---
        tab_batch = QWidget()
        batch_layout = QVBoxLayout(tab_batch)
        batch_layout.setContentsMargins(2, 8, 2, 2)
        batch_layout.setSpacing(10)

        batch_toolbar = QHBoxLayout()
        batch_toolbar.setSpacing(6)

        btn_load_txt = QPushButton("Import .txt")
        btn_load_txt.setObjectName("GhostButton")
        btn_load_txt.clicked.connect(self._load_batch_file)
        batch_toolbar.addWidget(btn_load_txt)

        btn_paste_multi = QPushButton("Paste Multiple")
        btn_paste_multi.setObjectName("GhostButton")
        btn_paste_multi.clicked.connect(self._paste_multi_clipboard)
        batch_toolbar.addWidget(btn_paste_multi)

        btn_clear_batch = QPushButton("Clear")
        btn_clear_batch.setObjectName("GhostButton")
        btn_clear_batch.clicked.connect(self._clear_batch)
        batch_toolbar.addWidget(btn_clear_batch)

        batch_toolbar.addStretch()

        self.lbl_batch_count = QLabel("0 URLs queued")
        self.lbl_batch_count.setStyleSheet("color: #71717a; font-size: 11px; font-weight: 600;")
        batch_toolbar.addWidget(self.lbl_batch_count)

        batch_layout.addLayout(batch_toolbar)

        self.txt_batch_input = QPlainTextEdit()
        self.txt_batch_input.setPlaceholderText("Paste YouTube links here (one URL per line) or import from a text file...")
        self.txt_batch_input.setFixedHeight(95)
        self.txt_batch_input.textChanged.connect(self._on_batch_text_changed)
        batch_layout.addWidget(self.txt_batch_input)

        self.table_batch = QTableWidget(0, 3)
        self.table_batch.setHorizontalHeaderLabels(["#", "URL", "Status"])
        self.table_batch.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_batch.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_batch.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_batch.setFixedHeight(135)
        batch_layout.addWidget(self.table_batch)

        self.tabs.addTab(tab_batch, "Batch Queue")

        card_layout.addWidget(self.tabs)

        # 3. Audio Profile & Master Settings
        settings_box = QVBoxLayout()
        settings_box.setSpacing(10)

        lbl_settings = QLabel("AUDIO PROFILE & MASTERING")
        lbl_settings.setObjectName("SectionHeader")
        settings_box.addWidget(lbl_settings)

        self.combo_preset = QComboBox()
        for key, p in AUDIO_PRESETS.items():
            self.combo_preset.addItem(p["name"], key)
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)
        settings_box.addWidget(self.combo_preset)

        self.lbl_preset_desc = QLabel(AUDIO_PRESETS["mp3_vbr0"]["description"])
        self.lbl_preset_desc.setStyleSheet("font-size: 11px; color: #71717a;")
        settings_box.addWidget(self.lbl_preset_desc)

        # Output options row
        opt_row = QHBoxLayout()
        opt_row.setSpacing(10)

        dest_col = QVBoxLayout()
        dest_col.setSpacing(3)
        lbl_dest = QLabel("OUTPUT FOLDER")
        lbl_dest.setObjectName("SectionHeader")
        dest_col.addWidget(lbl_dest)

        dest_input_row = QHBoxLayout()
        dest_input_row.setSpacing(6)
        self.txt_dest = QLineEdit()
        self.txt_dest.setText(DEFAULT_DOWNLOAD_DIR)
        dest_input_row.addWidget(self.txt_dest, stretch=1)

        btn_browse = QPushButton("Browse...")
        btn_browse.setObjectName("GhostButton")
        btn_browse.clicked.connect(self._browse_directory)
        dest_input_row.addWidget(btn_browse)
        dest_col.addLayout(dest_input_row)
        opt_row.addLayout(dest_col, stretch=2)

        cookies_col = QVBoxLayout()
        cookies_col.setSpacing(3)
        lbl_cookie = QLabel("BROWSER COOKIES")
        lbl_cookie.setObjectName("SectionHeader")
        cookies_col.addWidget(lbl_cookie)

        self.combo_browser = QComboBox()
        self.combo_browser.addItems(["None", "Chrome", "Edge", "Firefox", "Brave"])
        cookies_col.addWidget(self.combo_browser)
        opt_row.addLayout(cookies_col, stretch=1)

        settings_box.addLayout(opt_row)

        # Normalization Checkbox
        self.chk_normalize = QCheckBox("Loudness Normalization (EBU R128 · -14 LUFS)")
        self.chk_normalize.setChecked(True)
        self.chk_normalize.setToolTip("Applies standard EBU R128 mastering to ensure consistent perceived loudness across all tracks")
        settings_box.addWidget(self.chk_normalize)

        card_layout.addLayout(settings_box)

        # 4. Action Row (Primary CTA)
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.btn_download = QPushButton("Convert to MP3")
        self.btn_download.setObjectName("PrimaryActionButton")
        self.btn_download.clicked.connect(self.start_download)
        action_layout.addWidget(self.btn_download, stretch=3)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("DangerButton")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self.cancel_download)
        action_layout.addWidget(self.btn_cancel, stretch=1)

        card_layout.addLayout(action_layout)

        # 5. Progress Area
        self.progress_container = QWidget()
        self.progress_container.setVisible(False)
        prog_layout = QVBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(0, 4, 0, 0)
        prog_layout.setSpacing(6)

        self.lbl_overall_status = QLabel("Overall progress:")
        self.lbl_overall_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #d4d4d8;")
        self.lbl_overall_status.setVisible(False)
        prog_layout.addWidget(self.lbl_overall_status)

        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setVisible(False)
        prog_layout.addWidget(self.overall_progress_bar)

        self.lbl_progress_status = QLabel("Processing...")
        self.lbl_progress_status.setStyleSheet("font-size: 12px; font-weight: 500; color: #fafafa;")
        prog_layout.addWidget(self.lbl_progress_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.progress_bar)

        self.lbl_progress_details = QLabel("Speed: - | ETA: -")
        self.lbl_progress_details.setStyleSheet("font-size: 11px; color: #71717a; font-family: 'Cascadia Mono', monospace;")
        prog_layout.addWidget(self.lbl_progress_details)

        card_layout.addWidget(self.progress_container)

        workspace_layout.addWidget(studio_card)

        # 6. Recent Conversions Section
        self.history_frame = QFrame()
        self.history_frame.setObjectName("StudioCard")
        self.history_frame.setVisible(False)
        self.history_layout = QVBoxLayout(self.history_frame)
        self.history_layout.setContentsMargins(16, 14, 16, 14)
        self.history_layout.setSpacing(8)

        hist_header = QHBoxLayout()
        lbl_hist_title = QLabel("CONVERTED TRACKS")
        lbl_hist_title.setObjectName("SectionHeader")
        hist_header.addWidget(lbl_hist_title)
        hist_header.addStretch()

        btn_clear_hist = QPushButton("Clear")
        btn_clear_hist.setStyleSheet("font-size: 11px; padding: 2px 8px; background: transparent; border: none; color: #52525b;")
        btn_clear_hist.clicked.connect(self._clear_history)
        hist_header.addWidget(btn_clear_hist)

        self.history_layout.addLayout(hist_header)

        workspace_layout.addWidget(self.history_frame)

        # 7. Diagnostics Console
        log_header_row = QHBoxLayout()
        self.btn_toggle_log = QPushButton("Diagnostics & Technical Log ▾")
        self.btn_toggle_log.setStyleSheet("font-size: 11px; padding: 2px 8px; background: transparent; border: none; color: #52525b;")
        self.btn_toggle_log.clicked.connect(self._toggle_log_console)
        log_header_row.addWidget(self.btn_toggle_log)
        log_header_row.addStretch()

        workspace_layout.addLayout(log_header_row)

        self.log_console = QTextEdit()
        self.log_console.setObjectName("LogConsole")
        self.log_console.setReadOnly(True)
        self.log_console.setFixedHeight(90)
        self.log_console.setVisible(False)
        workspace_layout.addWidget(self.log_console)

        workspace_layout.addStretch()

        # 8. Fixed Docked Audio Player at Bottom
        self.audio_player = AudioPlayerWidget()
        self.audio_player.spectrum_requested.connect(self._show_spectrogram)
        root_layout.addWidget(self.audio_player)

        self.tabs.currentChanged.connect(self._on_tab_changed)

    # --- Handlers & UX Automation ---
    def _on_url_text_changed(self, text: str):
        cleaned = text.strip()
        is_comp = is_compound_url(cleaned)
        if hasattr(self, "compound_banner"):
            self.compound_banner.setVisible(is_comp)

        if ("youtube.com" in cleaned or "youtu.be/" in cleaned) and len(cleaned) >= 20:
            if not self.btn_inspect.isEnabled():
                return
            if hasattr(self, "_auto_inspect_timer"):
                self._auto_inspect_timer.stop()
            self._auto_inspect_timer = QTimer(self)
            self._auto_inspect_timer.setSingleShot(True)
            self._auto_inspect_timer.timeout.connect(self.check_url_info)
            self._auto_inspect_timer.start(400)

    def _on_compound_mode_changed(self):
        url = self.txt_url.text().strip()
        if url and is_compound_url(url):
            self.check_url_info()

    def _send_playlist_to_batch(self):
        url = self.txt_url.text().strip()
        if not url:
            return
        p_url = extract_playlist_only_url(url) if is_compound_url(url) else url
        existing = self.txt_batch_input.toPlainText()
        new_text = (existing + "\n" + p_url) if existing.strip() else p_url
        self.txt_batch_input.setPlainText(new_text)
        self.tabs.setCurrentIndex(1)
        self.append_log(f"Transferred playlist to Batch Queue: {p_url}")

    def _on_tab_changed(self, index):
        if not hasattr(self, "btn_download"):
            return
        if index == 0:
            self.btn_download.setText("Convert to MP3")
        else:
            count = len(self.batch_urls)
            self.btn_download.setText(f"Convert All ({count} Tracks)")

    def _paste_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            self.txt_url.setText(text)
            self.check_url_info()

    def _paste_multi_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            existing = self.txt_batch_input.toPlainText()
            new_text = (existing + "\n" + text) if existing.strip() else text
            self.txt_batch_input.setPlainText(new_text)

    def _clear_batch(self):
        self.txt_batch_input.clear()
        self.table_batch.setRowCount(0)
        self.batch_urls = []
        self.lbl_batch_count.setText("0 URLs queued")
        self._on_tab_changed(self.tabs.currentIndex())

    def _load_batch_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Text File with Links",
            "",
            "Text files (*.txt);;All files (*.*)"
        )
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                self.txt_batch_input.setPlainText(content)
            except Exception as e:
                QMessageBox.critical(self, "File Error", f"Unable to read file: {e}")

    def _on_batch_text_changed(self):
        content = self.txt_batch_input.toPlainText()
        urls = parse_url_list(content)
        self.batch_urls = urls
        self.lbl_batch_count.setText(f"{len(urls)} URLs queued")

        self.table_batch.setRowCount(len(urls))
        for row, u in enumerate(urls):
            item_no = QTableWidgetItem(str(row + 1))
            item_no.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_url = QTableWidgetItem(u)
            item_status = QTableWidgetItem("Queued")
            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table_batch.setItem(row, 0, item_no)
            self.table_batch.setItem(row, 1, item_url)
            self.table_batch.setItem(row, 2, item_status)

        self._on_tab_changed(self.tabs.currentIndex())

    def _browse_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.txt_dest.text())
        if folder:
            self.txt_dest.setText(folder)

    def _on_preset_changed(self, index):
        key = self.combo_preset.currentData()
        if key in AUDIO_PRESETS:
            self.lbl_preset_desc.setText(AUDIO_PRESETS[key]["description"])

    def _toggle_log_console(self):
        is_visible = not self.log_console.isVisible()
        self.log_console.setVisible(is_visible)
        self.btn_toggle_log.setText("Hide Technical Log ▴" if is_visible else "Diagnostics & Technical Log ▾")

    def _get_selected_cookies(self):
        text = self.combo_browser.currentText().lower()
        if "chrome" in text:
            return "chrome"
        elif "edge" in text:
            return "edge"
        elif "firefox" in text:
            return "firefox"
        elif "brave" in text:
            return "brave"
        return None

    def append_log(self, text: str):
        cleaned_text = clean_ansi_text(text)
        self.log_console.append(cleaned_text)
        sb = self.log_console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def check_url_info(self):
        url = self.txt_url.text().strip()
        if not url:
            return

        is_comp = is_compound_url(url)
        if hasattr(self, "compound_banner"):
            self.compound_banner.setVisible(is_comp)

        force_single = True
        if is_comp and hasattr(self, "radio_mode_playlist") and self.radio_mode_playlist.isChecked():
            force_single = False

        self.btn_inspect.setEnabled(False)
        self.btn_inspect.setText("...")
        mode_str = "Single Track" if (is_comp and force_single) else ("Playlist" if (is_comp or "playlist" in url) else "Single Track")
        self.append_log(f"Inspecting stream ({mode_str}): {url}")

        cookies = self._get_selected_cookies()
        self.info_worker = FetchInfoWorker(self.converter, url, cookies, force_single=force_single)
        self.info_worker.finished.connect(self._on_info_loaded)
        self.info_worker.error.connect(self._on_info_error)
        self.info_worker.start()

    def _on_info_loaded(self, info: dict):
        self.btn_inspect.setEnabled(True)
        self.btn_inspect.setText("Inspect")
        self.current_video_info = info
        self.preview_card.set_data(info)

        if not info.get("is_playlist"):
            self.txt_title.setText(info.get("clean_title", info.get("title", "")))
            self.txt_artist.setText(info.get("clean_artist", info.get("uploader", "")))
            self.txt_album.setText(info.get("clean_album", "Single"))
            self.tag_card.setVisible(True)
        else:
            self.tag_card.setVisible(False)

        self.append_log(f"Stream metadata verified: {info.get('title')}")

    def _on_info_error(self, err: str):
        self.btn_inspect.setEnabled(True)
        self.btn_inspect.setText("Inspect")
        clean_err = clean_ansi_text(err)
        self.append_log(f"Inspection error: {clean_err}")
        QMessageBox.critical(self, "Stream Error", f"Unable to parse stream information:\n\n{clean_err}")

    def start_download(self):
        out_dir = self.txt_dest.text().strip()
        if not out_dir:
            out_dir = DEFAULT_DOWNLOAD_DIR
            self.txt_dest.setText(out_dir)

        preset_key = self.combo_preset.currentData()
        cookies = self._get_selected_cookies()
        normalize = self.chk_normalize.isChecked()

        is_batch = (self.tabs.currentIndex() == 1)

        if is_batch:
            if not self.batch_urls:
                QMessageBox.warning(self, "Queue Empty", "No valid URLs in batch queue. Paste links or import a .txt file.")
                return

            self.btn_download.setEnabled(False)
            self.btn_download.setText("Processing Batch...")
            self.btn_cancel.setVisible(True)
            self.progress_container.setVisible(True)
            self.lbl_overall_status.setVisible(True)
            self.overall_progress_bar.setVisible(True)
            self.overall_progress_bar.setValue(0)
            self.progress_bar.setValue(0)

            self.batch_worker = BatchDownloadWorker(self.converter, self.batch_urls, out_dir, preset_key, cookies, normalize=normalize, auto_clean=True)
            self.batch_worker.item_progress.connect(self._on_batch_item_progress)
            self.batch_worker.overall_progress.connect(self._on_batch_overall_progress)
            self.batch_worker.log.connect(self.append_log)
            self.batch_worker.finished.connect(self._on_batch_finished)
            self.batch_worker.start()

        else:
            url = self.txt_url.text().strip()
            if not url:
                QMessageBox.warning(self, "Input Required", "Please enter a valid YouTube URL.")
                return

            is_comp = is_compound_url(url)
            force_single = True
            if is_comp and hasattr(self, "radio_mode_playlist") and self.radio_mode_playlist.isChecked():
                force_single = False

            self.btn_download.setEnabled(False)
            self.btn_download.setText("Processing...")
            self.btn_cancel.setVisible(True)
            self.progress_container.setVisible(True)
            self.lbl_overall_status.setVisible(False)
            self.overall_progress_bar.setVisible(False)
            self.progress_bar.setValue(0)
            self.lbl_progress_status.setText("Connecting...")
            self.lbl_progress_details.setText("Selecting highest audio stream...")

            custom_tags = {
                "title": self.txt_title.text().strip(),
                "artist": self.txt_artist.text().strip(),
                "album": self.txt_album.text().strip() or "Single"
            }
            auto_clean = self.chk_auto_clean.isChecked()

            self.download_worker = DownloadWorker(
                self.converter, url, out_dir, preset_key, cookies,
                normalize=normalize, custom_tags=custom_tags, auto_clean=auto_clean,
                force_single=force_single
            )
            self.download_worker.progress.connect(self._on_download_progress)
            self.download_worker.log.connect(self.append_log)
            self.download_worker.finished.connect(self._on_download_finished)
            self.download_worker.start()

    def cancel_download(self):
        if self.converter:
            self.converter.cancel()
        self.lbl_progress_status.setText("Cancelling...")
        self.btn_cancel.setEnabled(False)

    # Single Download Handlers
    def _on_download_progress(self, data: dict):
        stage = data.get("stage")
        if stage == "downloading":
            pct = int(data.get("percent", 0))
            self.progress_bar.setValue(pct)
            speed = data.get("speed_str", "N/A")
            eta = data.get("eta_str", "00:00")
            filename = data.get("filename", "")
            self.lbl_progress_status.setText(f"Downloading audio · {pct}%")
            self.lbl_progress_details.setText(f"{filename}  |  {speed}  |  ETA {eta}")
        elif stage == "converting":
            self.progress_bar.setValue(100)
            self.lbl_progress_status.setText("Converting & embedding metadata...")
            self.lbl_progress_details.setText("Writing ID3 tags and high-resolution cover art...")

    def _on_download_finished(self, res: dict):
        self.btn_download.setEnabled(True)
        self.btn_download.setText("Convert to MP3")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)

        if res.get("success"):
            self.lbl_progress_status.setText("Conversion completed.")
            self.lbl_progress_details.setText("Audio files saved to target folder.")
            files = res.get("files", [])
            if files:
                self.history_frame.setVisible(True)
                for f in files:
                    item_widget = HistoryListItem(f)
                    item_widget.play_requested.connect(self.audio_player.play_file)
                    item_widget.spectrum_requested.connect(self._show_spectrogram)
                    self.history_layout.addWidget(item_widget)

                self.audio_player.play_file(files[0])
        else:
            raw_err = res.get("error", "Unknown error encountered.")
            err = clean_ansi_text(raw_err)
            self.lbl_progress_status.setText("Download Failed")
            self.lbl_progress_details.setText(err)
            QMessageBox.critical(self, "Download Error", f"Download failed:\n\n{err}")

    # Batch Handlers
    def _on_batch_item_progress(self, idx: int, data: dict):
        stage = data.get("stage")
        status_text = "Processing..."

        if stage == "starting":
            status_text = "Downloading..."
        elif stage == "downloading":
            pct = int(data.get("percent", 0))
            self.progress_bar.setValue(pct)
            speed = data.get("speed_str", "N/A")
            eta = data.get("eta_str", "00:00")
            self.lbl_progress_status.setText(f"Track #{idx+1} · {pct}%")
            self.lbl_progress_details.setText(f"{speed}  |  ETA {eta}")
            status_text = f"{pct}%"
        elif stage == "converting":
            self.progress_bar.setValue(100)
            self.lbl_progress_status.setText(f"Track #{idx+1} · Converting...")
            status_text = "Converting..."
        elif stage == "completed":
            status_text = "Ready"
            files = data.get("files", [])
            if files:
                self.history_frame.setVisible(True)
                for f in files:
                    item_widget = HistoryListItem(f)
                    item_widget.play_requested.connect(self.audio_player.play_file)
                    item_widget.spectrum_requested.connect(self._show_spectrogram)
                    self.history_layout.addWidget(item_widget)
        elif stage == "error":
            status_text = "Failed"

        status_item = QTableWidgetItem(status_text)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if status_text == "Ready":
            status_item.setForeground(QColor("#4ade80"))
        elif status_text == "Failed":
            status_item.setForeground(QColor("#f87171"))
        elif "%" in status_text:
            status_item.setForeground(QColor("#60a5fa"))
        self.table_batch.setItem(idx, 2, status_item)

    def _on_batch_overall_progress(self, data: dict):
        curr = data.get("current_index", 0)
        total = data.get("total_items", 0)
        pct = int(data.get("overall_percent", 0))

        self.lbl_overall_status.setText(f"Queue Progress: {curr}/{total} tracks ({pct}%)")
        self.overall_progress_bar.setValue(pct)

    def _on_batch_finished(self, res: dict):
        count = len(self.batch_urls)
        self.btn_download.setEnabled(True)
        self.btn_download.setText(f"Convert All ({count} Tracks)")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)

        downloaded_count = len(res.get("downloaded_files", []))

        if res.get("success"):
            self.overall_progress_bar.setValue(100)
            self.lbl_overall_status.setText(f"Batch completed: {downloaded_count} tracks ready.")
        else:
            self.lbl_overall_status.setText(f"Batch ended: {downloaded_count} tracks completed.")

    def _show_spectrogram(self, filepath: str):
        if not filepath or not os.path.exists(filepath):
            return
        dialog = SpectrogramDialog(filepath, self)
        dialog.exec()

    def _clear_history(self):
        while self.history_layout.count() > 1:
            child = self.history_layout.takeAt(1)
            if child.widget():
                child.widget().deleteLater()
        self.history_frame.setVisible(False)

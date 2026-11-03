import os
import subprocess
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QSlider
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPainterPath
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from urllib.request import Request, urlopen
from threading import Thread

class RoundedThumbnailLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(124, 70)
        self.setStyleSheet("background-color: #16161a; border-radius: 7px;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("")
        self._pixmap = None

    def set_image(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        if not self._pixmap:
            super().paintEvent(event)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.GlobalColor.transparent)
            painter.setBrush(Qt.GlobalColor.transparent)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 7, 7)
        painter.setClipPath(path)

        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)


class VideoPreviewCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InnerSurface")
        self.setVisible(False)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Header Row: Thumbnail + Meta info
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.thumb_label = RoundedThumbnailLabel()
        top_row.addWidget(self.thumb_label)

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(4)

        title_dur_row = QHBoxLayout()
        self.title_label = QLabel("Track Title")
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #fafafa;")
        self.title_label.setWordWrap(True)
        title_dur_row.addWidget(self.title_label, stretch=1)

        self.dur_badge = QLabel("00:00")
        self.dur_badge.setStyleSheet("font-family: 'Cascadia Mono', monospace; font-size: 11px; color: #71717a;")
        title_dur_row.addWidget(self.dur_badge)
        meta_layout.addLayout(title_dur_row)

        self.channel_label = QLabel("Artist / Channel")
        self.channel_label.setStyleSheet("font-size: 11px; color: #71717a;")
        meta_layout.addWidget(self.channel_label)

        # Stream Specs Ribbon
        specs_row = QHBoxLayout()
        specs_row.setSpacing(6)

        self.stream_spec_label = QLabel("OPUS 48kHz · ~160 kbps")
        self.stream_spec_label.setObjectName("SpecBadge")
        specs_row.addWidget(self.stream_spec_label)

        self.spec_desc = QLabel("Native source stream")
        self.spec_desc.setStyleSheet("font-size: 11px; color: #52525b;")
        specs_row.addWidget(self.spec_desc, stretch=1)
        meta_layout.addLayout(specs_row)

        top_row.addLayout(meta_layout, stretch=1)
        main_layout.addLayout(top_row)

    def set_data(self, data: dict):
        if not data:
            self.setVisible(False)
            return

        if data.get("is_playlist"):
            self.title_label.setText(data.get("title", "YouTube Playlist"))
            count = data.get("count", 0)
            uploader = data.get("uploader", "Unknown")
            self.channel_label.setText(f"{uploader} · {count} tracks")
            self.dur_badge.setText("Batch")
            self.stream_spec_label.setText("BATCH PLAYLIST")
            self.spec_desc.setText("Automatic per-item stream selection")
        else:
            self.title_label.setText(data.get("title", "Track"))
            channel = data.get("uploader", "Artist")
            dur = data.get("duration_str", "00:00")
            self.channel_label.setText(channel)
            self.dur_badge.setText(dur)

            codec = str(data.get("src_codec", "Opus")).upper()
            bitrate = data.get("src_bitrate", 160)
            sample = data.get("src_samplerate", 48000)
            self.stream_spec_label.setText(f"{codec} {sample}Hz · ~{bitrate} kbps")
            self.spec_desc.setText("Direct stream from YouTube servers")

        thumb_url = data.get("thumbnail")
        if thumb_url:
            self._load_thumbnail(thumb_url)

        self.setVisible(True)

    def _load_thumbnail(self, url: str):
        def _fetch():
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(req, timeout=5) as resp:
                    raw_data = resp.read()
                    image = QImage()
                    if image.loadFromData(raw_data):
                        pixmap = QPixmap.fromImage(image)
                        self.thumb_label.set_image(pixmap)
            except Exception:
                pass
        Thread(target=_fetch, daemon=True).start()


class AudioPlayerWidget(QFrame):
    """Built-in docked audio player widget."""
    spectrum_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FooterDock")
        self.current_filepath = ""
        self.setVisible(False)
        self.setFixedHeight(64)
        self.init_player()
        self.init_ui()

    def init_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.85)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(16)

        # Left: Play Toggle
        self.btn_play = QPushButton("Play")
        self.btn_play.setFixedSize(52, 32)
        self.btn_play.setStyleSheet("font-weight: 600; font-size: 11px; padding: 4px;")
        self.btn_play.clicked.connect(self.toggle_play)
        layout.addWidget(self.btn_play)

        # Center: Track meta & Slider
        track_col = QVBoxLayout()
        track_col.setSpacing(3)

        info_row = QHBoxLayout()
        self.file_title = QLabel("No active track")
        self.file_title.setStyleSheet("font-weight: 600; color: #fafafa; font-size: 12px;")
        info_row.addWidget(self.file_title, stretch=1)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("font-family: 'Cascadia Mono', monospace; font-size: 11px; color: #71717a;")
        info_row.addWidget(self.time_label)
        track_col.addLayout(info_row)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.sliderMoved.connect(self._set_position)
        track_col.addWidget(self.slider)

        layout.addLayout(track_col, stretch=1)

        # Volume Controls
        vol_row = QHBoxLayout()
        vol_row.setSpacing(6)

        self.btn_mute = QPushButton("Vol")
        self.btn_mute.setFixedSize(36, 26)
        self.btn_mute.setStyleSheet("font-size: 11px; padding: 2px; background: transparent; border: 1px solid #27272a; color: #71717a;")
        self.btn_mute.clicked.connect(self._toggle_mute)
        vol_row.addWidget(self.btn_mute)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(85)
        self.vol_slider.setFixedWidth(70)
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        vol_row.addWidget(self.vol_slider)

        layout.addLayout(vol_row)

        # Right: Action
        self.btn_spectrum = QPushButton("Spectrum")
        self.btn_spectrum.setStyleSheet("font-size: 11px; padding: 6px 10px; background: transparent; border: 1px solid #27272a; color: #a1a1aa;")
        self.btn_spectrum.clicked.connect(self._open_spectrum)
        layout.addWidget(self.btn_spectrum)

        self.btn_open_folder = QPushButton("Reveal in Explorer")
        self.btn_open_folder.setStyleSheet("font-size: 11px; padding: 6px 12px;")
        self.btn_open_folder.clicked.connect(self._open_in_explorer)
        layout.addWidget(self.btn_open_folder)

    def _open_spectrum(self):
        if self.current_filepath and os.path.exists(self.current_filepath):
            self.spectrum_requested.emit(self.current_filepath)

    def play_file(self, filepath: str):
        if not os.path.exists(filepath):
            return

        self.current_filepath = filepath
        filename = os.path.basename(filepath)
        self.file_title.setText(filename)
        self.player.setSource(QUrl.fromLocalFile(filepath))
        self.player.play()
        self.setVisible(True)

    def toggle_play(self):
        state = self.player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _set_position(self, pos):
        dur = self.player.duration()
        if dur > 0:
            target_pos = int((pos / 100.0) * dur)
            self.player.setPosition(target_pos)

    def _on_position_changed(self, position):
        dur = self.player.duration()
        if dur > 0:
            val = int((position / dur) * 100)
            self.slider.blockSignals(True)
            self.slider.setValue(val)
            self.slider.blockSignals(False)
            self._update_time_label(position, dur)

    def _on_duration_changed(self, duration):
        pos = self.player.position()
        self._update_time_label(pos, duration)

    def _update_time_label(self, pos, dur):
        pos_sec = int(pos // 1000)
        dur_sec = int(dur // 1000)
        pos_str = f"{pos_sec // 60:02d}:{pos_sec % 60:02d}"
        dur_str = f"{dur_sec // 60:02d}:{dur_sec % 60:02d}"
        self.time_label.setText(f"{pos_str} / {dur_str}")

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("Pause")
        else:
            self.btn_play.setText("Play")

    def _toggle_mute(self):
        is_muted = self.audio_output.isMuted()
        self.audio_output.setMuted(not is_muted)
        self.btn_mute.setText("Muted" if not is_muted else "Vol")
        self.btn_mute.setStyleSheet(
            "font-size: 11px; padding: 2px; background: #27272a; border: 1px solid #3f3f46; color: #fb7185;"
            if not is_muted else
            "font-size: 11px; padding: 2px; background: transparent; border: 1px solid #27272a; color: #71717a;"
        )

    def _on_volume_changed(self, val):
        self.audio_output.setVolume(val / 100.0)
        if self.audio_output.isMuted():
            self.audio_output.setMuted(False)
            self.btn_mute.setText("Vol")
            self.btn_mute.setStyleSheet("font-size: 11px; padding: 2px; background: transparent; border: 1px solid #27272a; color: #71717a;")

    def _open_in_explorer(self):
        if self.current_filepath and os.path.exists(self.current_filepath):
            subprocess.run(["explorer", f"/select,{os.path.normpath(self.current_filepath)}"])
        elif self.current_filepath:
            folder = os.path.dirname(self.current_filepath)
            if os.path.exists(folder):
                subprocess.run(["explorer", os.path.normpath(folder)])


class HistoryListItem(QFrame):
    """Converted track history card."""
    play_requested = pyqtSignal(str)
    spectrum_requested = pyqtSignal(str)

    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.setObjectName("InnerSurface")
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)

        filename = os.path.basename(self.filepath)
        name_label = QLabel(filename)
        name_label.setStyleSheet("font-weight: 600; color: #fafafa; font-size: 12px;")
        meta_layout.addWidget(name_label)

        size_bytes = os.path.getsize(self.filepath) if os.path.exists(self.filepath) else 0
        size_mb = size_bytes / (1024 * 1024)
        ext = os.path.splitext(self.filepath)[1].upper().replace(".", "")
        sub_label = QLabel(f"{ext} · {size_mb:.2f} MB")
        sub_label.setStyleSheet("color: #71717a; font-size: 11px;")
        meta_layout.addWidget(sub_label)

        layout.addLayout(meta_layout, stretch=1)

        btn_play = QPushButton("Play")
        btn_play.setStyleSheet("font-size: 11px; padding: 4px 12px;")
        btn_play.clicked.connect(lambda: self.play_requested.emit(self.filepath))
        layout.addWidget(btn_play)

        btn_spec = QPushButton("Spectrum")
        btn_spec.setStyleSheet("font-size: 11px; padding: 4px 10px; background: transparent; border: 1px solid #27272a; color: #a1a1aa;")
        btn_spec.clicked.connect(lambda: self.spectrum_requested.emit(self.filepath))
        layout.addWidget(btn_spec)

        btn_folder = QPushButton("Folder")
        btn_folder.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        btn_folder.clicked.connect(self._open_folder)
        layout.addWidget(btn_folder)

    def _open_folder(self):
        if os.path.exists(self.filepath):
            subprocess.run(["explorer", f"/select,{os.path.normpath(self.filepath)}"])

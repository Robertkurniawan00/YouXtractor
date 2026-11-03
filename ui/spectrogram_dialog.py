"""
Audio Frequency Spectrogram & Cutoff Shelf Inspector Dialog.
"""

import os
import shutil
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QFrame, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap

from core.ffmpeg_setup import ensure_ffmpeg
from native.native_bridge import inspect_audio_fidelity


class SpectrogramWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, filepath: str, palette: str, ffmpeg_bin: str):
        super().__init__()
        self.filepath = filepath
        self.palette = palette
        self.ffmpeg_bin = ffmpeg_bin

    def run(self):
        try:
            res = inspect_audio_fidelity(
                audio_path=self.filepath,
                color_palette=self.palette,
                ffmpeg_bin=self.ffmpeg_bin
            )
            if res.get("success"):
                self.finished.emit(res)
            else:
                self.error.emit(res.get("error", "Analysis failed."))
        except Exception as e:
            self.error.emit(str(e))


class SpectrogramDialog(QDialog):
    """Studio-grade Audio Spectrogram & Frequency Shelf Inspector Dialog."""
    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.ffmpeg_info = ensure_ffmpeg()
        self.ffmpeg_bin = self.ffmpeg_info.get("ffmpeg", "ffmpeg")
        self.current_analysis = None
        self.worker = None

        self.setWindowTitle("Audio Frequency Spectrogram Analyzer")
        self.resize(820, 560)
        self.setMinimumSize(720, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #09090b;
                color: #a1a1aa;
                font-family: 'Segoe UI Variable Text', 'Segoe UI', -apple-system, sans-serif;
            }
            QLabel {
                color: #a1a1aa;
            }
            QFrame#SurfaceCard {
                background-color: #121215;
                border: 1px solid #1f1f24;
                border-radius: 9px;
            }
            QFrame#SpectrogramFrame {
                background-color: #0b0b0e;
                border: 1px solid #27272a;
                border-radius: 7px;
            }
            QPushButton#PrimaryBtn {
                background-color: #fafafa;
                color: #09090b;
                font-weight: 600;
                font-size: 12px;
                padding: 7px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton#PrimaryBtn:hover {
                background-color: #e4e4e7;
            }
            QPushButton#GhostBtn {
                background-color: transparent;
                color: #d4d4d8;
                font-size: 12px;
                padding: 6px 14px;
                border: 1px solid #27272a;
                border-radius: 6px;
            }
            QPushButton#GhostBtn:hover {
                background-color: #1a1a20;
                border-color: #3f3f46;
            }
            QComboBox {
                background-color: #16161a;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 4px 10px;
                color: #fafafa;
                font-size: 11px;
                min-width: 100px;
            }
        """)

        self.init_ui()
        self.run_analysis("magma")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(14)

        # 1. Header Row (Track title, badge, file size)
        header_card = QFrame()
        header_card.setObjectName("SurfaceCard")
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(14, 12, 14, 12)
        h_layout.setSpacing(6)

        top_meta = QHBoxLayout()
        self.lbl_title = QLabel(os.path.basename(self.filepath))
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #fafafa;")
        top_meta.addWidget(self.lbl_title, stretch=1)

        self.lbl_badge = QLabel("Analyzing...")
        self.lbl_badge.setStyleSheet("""
            background-color: #1a1a22;
            border: 1px solid #2e2e38;
            color: #a1a1aa;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 10px;
        """)
        top_meta.addWidget(self.lbl_badge)
        h_layout.addLayout(top_meta)

        self.lbl_subtitle = QLabel("Visual time-frequency spectrogram and estimated high-frequency cutoff shelf")
        self.lbl_subtitle.setStyleSheet("font-size: 11px; color: #71717a;")
        h_layout.addWidget(self.lbl_subtitle)

        main_layout.addWidget(header_card)

        # 2. Spectrogram Display Area
        spec_container = QFrame()
        spec_container.setObjectName("SurfaceCard")
        spec_layout = QVBoxLayout(spec_container)
        spec_layout.setContentsMargins(14, 12, 14, 12)
        spec_layout.setSpacing(10)

        # Controls row (Palette selector + Legend note)
        controls_row = QHBoxLayout()
        lbl_palette = QLabel("Color Palette:")
        lbl_palette.setStyleSheet("font-size: 11px; font-weight: 600; color: #71717a;")
        controls_row.addWidget(lbl_palette)

        self.combo_palette = QComboBox()
        self.combo_palette.addItems(["Magma (Default)", "Fire", "Plasma", "Viridis", "Cool", "Rainbow"])
        self.combo_palette.currentIndexChanged.connect(self._on_palette_changed)
        controls_row.addWidget(self.combo_palette)

        controls_row.addStretch()

        self.lbl_scale_info = QLabel("Scale: Logarithmic Amplitude (dB) vs Linear Frequency (0 – 22 kHz)")
        self.lbl_scale_info.setStyleSheet("font-size: 11px; color: #52525b; font-family: 'Cascadia Mono', monospace;")
        controls_row.addWidget(self.lbl_scale_info)
        spec_layout.addLayout(controls_row)

        # Spectrogram Image View
        self.spec_frame = QFrame()
        self.spec_frame.setObjectName("SpectrogramFrame")
        frame_layout = QVBoxLayout(self.spec_frame)
        frame_layout.setContentsMargins(4, 4, 4, 4)

        self.lbl_image = QLabel("Rendering audio spectrogram...")
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setStyleSheet("font-size: 12px; color: #71717a; min-height: 220px;")
        frame_layout.addWidget(self.lbl_image)

        spec_layout.addWidget(self.spec_frame, stretch=1)

        # Progress bar during rendering
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setStyleSheet("background-color: #1a1a20; border: none;")
        self.progress_bar.setVisible(False)
        spec_layout.addWidget(self.progress_bar)

        main_layout.addWidget(spec_container, stretch=1)

        # 3. Verdict & Metrics Card
        verdict_card = QFrame()
        verdict_card.setObjectName("SurfaceCard")
        v_layout = QHBoxLayout(verdict_card)
        v_layout.setContentsMargins(14, 10, 14, 10)
        v_layout.setSpacing(16)

        cutoff_col = QVBoxLayout()
        cutoff_col.setSpacing(2)
        lbl_c_title = QLabel("ESTIMATED CUTOFF SHELF")
        lbl_c_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #71717a; letter-spacing: 0.5px;")
        cutoff_col.addWidget(lbl_c_title)
        self.lbl_cutoff_val = QLabel("-- kHz")
        self.lbl_cutoff_val.setStyleSheet("font-size: 16px; font-weight: 700; color: #fafafa; font-family: 'Cascadia Mono', monospace;")
        cutoff_col.addWidget(self.lbl_cutoff_val)
        v_layout.addLayout(cutoff_col)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet("color: #1f1f24;")
        v_layout.addWidget(divider)

        verdict_col = QVBoxLayout()
        verdict_col.setSpacing(2)
        lbl_v_title = QLabel("ANALYSIS VERDICT")
        lbl_v_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #71717a; letter-spacing: 0.5px;")
        verdict_col.addWidget(lbl_v_title)
        self.lbl_verdict_text = QLabel("Analyzing audio frequency distribution...")
        self.lbl_verdict_text.setStyleSheet("font-size: 12px; color: #d4d4d8;")
        self.lbl_verdict_text.setWordWrap(True)
        verdict_col.addWidget(self.lbl_verdict_text)
        v_layout.addLayout(verdict_col, stretch=1)

        main_layout.addWidget(verdict_card)

        # 4. Action Buttons (Save Spectrogram PNG + Close)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        self.btn_save_png = QPushButton("Export PNG")
        self.btn_save_png.setObjectName("GhostBtn")
        self.btn_save_png.setEnabled(False)
        self.btn_save_png.clicked.connect(self._save_png)
        actions_row.addWidget(self.btn_save_png)

        actions_row.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("PrimaryBtn")
        self.btn_close.clicked.connect(self.accept)
        actions_row.addWidget(self.btn_close)

        main_layout.addLayout(actions_row)

    def run_analysis(self, palette_name: str):
        self.progress_bar.setVisible(True)
        self.lbl_image.setText("Processing frequency spectrum analysis...")

        palette_code = palette_name.lower().split(" ")[0]
        self.worker = SpectrogramWorker(self.filepath, palette_code, self.ffmpeg_bin)
        self.worker.finished.connect(self._on_analysis_finished)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()

    def _on_analysis_finished(self, data: dict):
        self.progress_bar.setVisible(False)
        self.current_analysis = data

        # Load Spectrogram Image
        img_path = data.get("spectrogram_image")
        if img_path and os.path.isfile(img_path):
            pixmap = QPixmap(img_path)
            scaled = pixmap.scaled(
                self.spec_frame.width() - 8,
                240,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_image.setPixmap(scaled)
            self.btn_save_png.setEnabled(True)

        # Update Badge & Verdict
        badge_text = data.get("badge", "ANALYZED")
        color_code = data.get("color_code", "#4ade80")
        self.lbl_badge.setText(f"● {badge_text}")
        self.lbl_badge.setStyleSheet(f"""
            background-color: #121814;
            border: 1px solid {color_code}44;
            color: {color_code};
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 10px;
        """)

        self.lbl_cutoff_val.setText(data.get("cutoff_str", "N/A"))
        self.lbl_cutoff_val.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {color_code}; font-family: 'Cascadia Mono', monospace;")
        self.lbl_verdict_text.setText(data.get("verdict", ""))

    def _on_analysis_error(self, err: str):
        self.progress_bar.setVisible(False)
        self.lbl_image.setText(f"Spectrogram generation error:\n{err}")
        QMessageBox.warning(self, "Analysis Warning", f"Could not generate complete spectrogram:\n\n{err}")

    def _on_palette_changed(self, idx: int):
        palette = self.combo_palette.currentText()
        self.run_analysis(palette)

    def _save_png(self):
        if not self.current_analysis or not self.current_analysis.get("spectrogram_image"):
            return

        src_png = self.current_analysis["spectrogram_image"]
        base_name = os.path.splitext(os.path.basename(self.filepath))[0]
        suggested = f"{base_name}_spectrogram.png"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Spectrogram Image",
            suggested,
            "PNG Image (*.png)"
        )
        if save_path:
            try:
                shutil.copyfile(src_png, save_path)
                QMessageBox.information(self, "Export Complete", f"Spectrogram image saved to:\n\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Unable to save image: {e}")

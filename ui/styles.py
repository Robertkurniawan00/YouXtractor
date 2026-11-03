"""
Theme and visual styling for YouXtractor application.
"""

STYLESHEET = """
QMainWindow {
    background-color: #09090b;
}

QWidget {
    color: #a1a1aa;
    font-family: 'Segoe UI Variable Text', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13px;
    selection-background-color: #27272a;
    selection-color: #fafafa;
}

/* Scroll Area & Bars */
QScrollArea {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #27272a;
    min-height: 28px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #3f3f46;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* Cards & Surfaces */
QFrame#SurfaceCard, QFrame#StudioCard {
    background-color: #121215;
    border: 1px solid #1f1f24;
    border-radius: 10px;
}

QFrame#InnerSurface {
    background-color: #16161a;
    border: 1px solid #232329;
    border-radius: 8px;
}

QFrame#FooterDock {
    background-color: #0e0e11;
    border-top: 1px solid #1f1f24;
}

/* Typography Hierarchy */
QLabel#AppBrand {
    font-size: 15px;
    font-weight: 700;
    color: #fafafa;
    letter-spacing: -0.4px;
}

QLabel#AppTagline {
    font-size: 12px;
    color: #52525b;
}

QLabel#SectionHeader {
    font-size: 11px;
    font-weight: 700;
    color: #71717a;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}

QLabel#FieldLabel {
    font-size: 11px;
    font-weight: 600;
    color: #a1a1aa;
}

QLabel#SpecBadge {
    background-color: #1a1815;
    border: 1px solid #383020;
    color: #fbbf24;
    font-size: 11px;
    font-weight: 600;
    font-family: 'Cascadia Mono', 'Consolas', monospace;
    padding: 3px 8px;
    border-radius: 4px;
}

QLabel#EngineActiveBadge {
    background-color: #0f2316;
    border: 1px solid #173822;
    color: #4ade80;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 12px;
}

/* Interactive Controls: Inputs */
QLineEdit {
    background-color: #16161a;
    border: 1px solid #27272a;
    border-radius: 7px;
    padding: 9px 12px;
    color: #fafafa;
    font-size: 13px;
}

QLineEdit:focus {
    border: 1px solid #3b82f6;
    background-color: #18181d;
}

QLineEdit::placeholder {
    color: #52525b;
}

QPlainTextEdit {
    background-color: #16161a;
    border: 1px solid #27272a;
    border-radius: 7px;
    padding: 10px;
    color: #fafafa;
    font-family: 'Cascadia Mono', 'Consolas', monospace;
    font-size: 12px;
    line-height: 1.5;
}

QPlainTextEdit:focus {
    border: 1px solid #3b82f6;
}

/* Buttons */
QPushButton {
    background-color: #1c1c21;
    border: 1px solid #27272a;
    border-radius: 7px;
    color: #e4e4e7;
    font-size: 12px;
    font-weight: 600;
    padding: 8px 14px;
}

QPushButton:hover {
    background-color: #27272f;
    border-color: #3f3f46;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #141418;
}

QPushButton#PrimaryActionButton {
    background-color: #fafafa;
    border: 1px solid #ffffff;
    color: #09090b;
    font-size: 13px;
    font-weight: 600;
    padding: 10px 20px;
    border-radius: 7px;
}

QPushButton#PrimaryActionButton:hover {
    background-color: #e4e4e7;
    border-color: #e4e4e7;
}

QPushButton#PrimaryActionButton:disabled {
    background-color: #27272a;
    border-color: #27272a;
    color: #52525b;
}

QPushButton#GhostButton {
    background-color: transparent;
    border: 1px solid #27272a;
    color: #a1a1aa;
}

QPushButton#GhostButton:hover {
    background-color: #1c1c21;
    color: #fafafa;
}

QPushButton#DangerButton {
    background-color: #251216;
    border: 1px solid #3f171e;
    color: #fb7185;
    font-weight: 600;
    padding: 10px 20px;
    border-radius: 7px;
}

QPushButton#DangerButton:hover {
    background-color: #3b161e;
}

/* Segmented Control / Tabs */
QTabWidget::pane {
    border: 1px solid #1f1f24;
    background-color: #121215;
    border-radius: 10px;
    padding: 14px;
}

QTabBar {
    background: transparent;
    qproperty-drawBase: 0;
}

QTabBar::tab {
    background-color: #16161a;
    border: 1px solid #232329;
    color: #71717a;
    padding: 7px 18px;
    margin-right: 4px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background-color: #27272a;
    border-color: #3f3f46;
    color: #ffffff;
}

QTabBar::tab:hover:!selected {
    color: #d4d4d8;
    background-color: #1c1c21;
}

/* Dropdown */
QComboBox {
    background-color: #16161a;
    border: 1px solid #27272a;
    border-radius: 7px;
    padding: 7px 12px;
    color: #fafafa;
    font-size: 12px;
    min-height: 22px;
}

QComboBox:hover {
    border-color: #3f3f46;
}

QComboBox:focus {
    border-color: #3b82f6;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #71717a;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #16161a;
    border: 1px solid #27272a;
    selection-background-color: #27272a;
    selection-color: #fafafa;
    color: #d4d4d8;
    border-radius: 7px;
    padding: 4px;
}

/* Checkbox (Modern Switch-like Pill) */
QCheckBox {
    font-size: 12px;
    color: #d4d4d8;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #3f3f46;
    background-color: #16161a;
}

QCheckBox::indicator:hover {
    border-color: #71717a;
}

QCheckBox::indicator:checked {
    background-color: #3b82f6;
    border-color: #3b82f6;
}

/* Hairline Progress */
QProgressBar {
    background-color: #1c1c21;
    border: none;
    border-radius: 2px;
    height: 4px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 2px;
}

/* Clean Borderless Queue Table */
QTableWidget {
    background-color: #0e0e11;
    border: 1px solid #1f1f24;
    border-radius: 7px;
    gridline-color: transparent;
    color: #d4d4d8;
    font-size: 12px;
}

QTableWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid #18181c;
}

QTableWidget::item:selected {
    background-color: #1a1a20;
}

QHeaderView::section {
    background-color: #121215;
    color: #71717a;
    font-weight: 600;
    font-size: 11px;
    padding: 7px 10px;
    border: none;
    border-bottom: 1px solid #1f1f24;
}

/* Mini Player Slider */
QSlider::groove:horizontal {
    height: 3px;
    background: #27272a;
    border-radius: 1.5px;
}

QSlider::sub-page:horizontal {
    background: #fafafa;
    border-radius: 1.5px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: none;
    width: 8px;
    margin-top: -2.5px;
    margin-bottom: -2.5px;
    border-radius: 4px;
}

/* Diagnostics Console */
QTextEdit#LogConsole {
    background-color: #0e0e11;
    border: 1px solid #1f1f24;
    border-radius: 7px;
    font-family: 'Cascadia Mono', 'Consolas', monospace;
    font-size: 11px;
    color: #71717a;
    padding: 8px;
}

/* Radio Button & Playlist Banner */
QRadioButton {
    font-size: 12px;
    color: #d4d4d8;
    spacing: 6px;
}

QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border-radius: 7px;
    border: 1px solid #3f3f46;
    background-color: #16161a;
}

QRadioButton::indicator:hover {
    border-color: #71717a;
}

QRadioButton::indicator:checked {
    background-color: #3b82f6;
    border-color: #3b82f6;
}

QFrame#PlaylistNoticeCard {
    background-color: #13151b;
    border: 1px solid #1e2638;
    border-radius: 7px;
}
"""

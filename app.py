import sys
import os
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"[FATAL ERROR] {err_msg}", file=sys.stderr)
    try:
        QMessageBox.critical(
            None,
            "Application Error",
            f"An unexpected error occurred:\n\n{str(exc_value)}\n\nPlease check logs for details."
        )
    except Exception:
        pass

sys.excepthook = handle_exception

def main():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    app.setApplicationName("YouXtractor")
    app.setOrganizationName("Antigravity")

    # Load application icon for taskbar and window
    icon_path = os.path.join(BASE_DIR, "assets", "app.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    if os.path.isfile(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow

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

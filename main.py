"""
ФСНБ XML to RAG-Friendly Markdown Converter
PyQt6 GUI application.
"""

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.resize(1200, 700)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

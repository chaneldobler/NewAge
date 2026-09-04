import sys
import os
import json
from PySide6 import QtWidgets,QtCore
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QVBoxLayout, QLabel, QMainWindow
from PySide6.QtCore import QSize, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QPolygonF, QBrush
import pyqtgraph as pg

# Hardware & Worker Imports
import keller, smc, tm
import worker
import procedures, control

class UI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("New Age")

        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        self.control = control.Control(self)

        self.tabs.addTab(self.control, "Control")
        
    def closeEvent(self, event):
        self.control.closeEvent(event)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = UI()

    window.show()
    sys.exit(app.exec())

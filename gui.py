import sys
import os
import json
from PySide6 import QtWidgets,QtCore
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QMainWindow, QGroupBox, QFormLayout, QGridLayout, QLineEdit
from PySide6.QtCore import QSize, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QPolygonF, QBrush
import pyqtgraph as pg

# Hardware & Worker Imports
import keller, smc, tm
import worker
import procedures, control
import components
import schematic

class Configurations(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(components.styleSheet)
        self.setFixedSize(1950, 550)
        self.filename = "procedures_config.json"

        with open(self.filename, "r") as f:
            self.config = json.load(f)

        self.data = {}
        self.container = QGridLayout(self)
        for i, (title, items) in enumerate(self.config.items()):
            header = components.Title(title, alignment=Qt.AlignmentFlag.AlignCenter)
            self.container.addWidget(header, 0, 3 * i, 1, 3)
            
            for j, (name, properties) in enumerate(items.items()):
                item = QLabel(name, alignment=Qt.AlignmentFlag.AlignLeft)
                value = QLineEdit(str(properties.get("Value", "")), alignment=Qt.AlignmentFlag.AlignRight)
                unit = QLabel(properties.get("Unit", ""), alignment=Qt.AlignmentFlag.AlignLeft)

                value.returnPressed.connect(self.save)
                self.data[(title, name)] = value
                self.container.addWidget(item, j + 1, 3 * i)
                self.container.addWidget(value, j + 1, 3 * i + 1)
                self.container.addWidget(unit, j + 1, 3 * i + 2)
    
    def save(self):
        for (title, name), item in self.data.items():
            val = item.text()
            val = float(val) if "." in val else int(val)
            self.config[title][name]["Value"] = val

        with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)

    def reset(self):
        for (title, name), item in self.data.items():
            val = self.config[title][name]["Default"]
            item.edit.setText(str(val))
            self.config[title][name]["Value"] = val

        with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)

class GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NewAGE")

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid grey;  
                top: -1px;
                background-color: #f5f5f5;
            }
            QTabBar::tab {
                height: 30px;
                min-width: 100px;
                font-size: 20px;
                background-color: #f5f5f5;
                border: 1px solid black;
                padding: 8px 16px;
            }
            QTabBar::tab:selected {
                background-color: #f5f5f5;
                border-bottom-color: #f5f5f5; 
            }
        """)
        self.setCentralWidget(self.tabs)

        self.control = control.Control(self)
        self.configurations = Configurations(self)

        self.tabs.addTab(self.control, "Controls")
        self.tabs.addTab(self.configurations, "Configurations")
        
    def closeEvent(self, event):
        self.control.closeEvent(event)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = GUI()

    window.show()
    sys.exit(app.exec())

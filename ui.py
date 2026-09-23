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

class Configurations(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        with open("procedures_config.json", "r") as f:
            self.config = json.load(f)

        self.grid = QGridLayout()
        self.grid.setVerticalSpacing(0)
        self.grid.setRowStretch(100, 1)
        self.setFixedSize(1600, 800)
        self.setContentsMargins(20, 20, 20, 20)

        self.inputs = {}
        for i, (stage, items) in enumerate(self.config.items()):
            header = QLabel(stage)
            header.setStyleSheet(f"""
            QLabel {{
                background-color: #495057;
                color: white;
                border: none;
                font-weight: bold;
                border-radius: 0px;
                font-size: 14px;
                padding: 12px 16px;
            }}
             """)
            self.grid.addWidget(header, 0, 3*i, 1, 3, alignment=Qt.AlignmentFlag.AlignTop)

            for j, (name, properties) in enumerate(items.items()):
                label = QLabel(name)
                label.setStyleSheet(f"""
                QLabel {{
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    border-radius: 0px;
                    font-size: 12px;
                    padding: 16px 24px;
                }}
                """)

                value = QLineEdit(str(properties.get("Value", "")), alignment=Qt.AlignmentFlag.AlignRight)
                value.setStyleSheet("""
                QLineEdit {
                    background-color: white;
                    border: none;
                    border-radius: 0px;
                    color: black;
                    font-size: 12px;
                    padding: 16px 8px;
                }
                """)

                unit = QLabel(properties.get("Unit", ""))
                unit.setStyleSheet(f"""
                QLabel {{
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    border-radius: 0px;
                    font-size: 12px;
                    padding: 16px 12px;
                }}
                """)

                self.inputs[(stage, name)] = value
                self.grid.addWidget(label, j+1, 3*i)
                self.grid.addWidget(value, j+1, 3*i+1)
                self.grid.addWidget(unit, j+1, 3*i+2)

        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-size: 14px;
                font-weight: bold;
                padding: 12px 16px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)
        
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-size: 14px;
                font-weight: bold;
                padding: 12px 16px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

        self.save_btn.clicked.connect(self.save)        
        self.reset_btn.clicked.connect(self.reset)

        self.buttons = QHBoxLayout()
        self.buttons.addWidget(self.save_btn, alignment=Qt.AlignmentFlag.AlignTop)
        self.buttons.addWidget(self.reset_btn, alignment=Qt.AlignmentFlag.AlignTop)

        self.container = QHBoxLayout(self)
        self.container.addLayout(self.grid)
        self.container.addLayout(self.buttons)

    def save(self):
        for (category, name), value in self.inputs.items():
            val = value.text()
            val = float(val) if "." in val else int(val)
            self.config[category][name]["Value"] = val

        with open("procedures_config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)

    def reset(self):
        for (category, name), value in self.inputs.items():
            val = self.config[category][name]["Default"]
            value.setText(str(val))
            self.config[category][name]["Value"] = val

        with open("procedures_config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)

class UI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("New Age")

        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        self.control = control.Control(self)
        self.configurations = Configurations(self)

        self.tabs.addTab(self.control, "Control")
        self.tabs.addTab(self.configurations, "Configuration")
        
    def closeEvent(self, event):
        self.control.closeEvent(event)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = UI()

    window.show() #showMaximized()
    sys.exit(app.exec())

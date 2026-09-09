import sys
import os
import json
from PySide6 import QtWidgets,QtCore
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QVBoxLayout, QLabel, QSizePolicy, QGridLayout, QHBoxLayout
from PySide6.QtCore import QSize, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QPolygonF, QBrush
import pyqtgraph as pg

# Hardware & Worker Imports
import keller, smc, tm
import worker
import procedures
import schematic

# adapt to offset yes or no?

class History(QWidget):
    def __init__(self, parent, pressures):
        super().__init__(parent)
        self.parent = parent
        self.pressures = pressures


        # Properties
        self.history = [[] for _ in self.pressures]
        self.dt = 0.1
        self.time = []

        # Graph
        self.graph = pg.PlotWidget()
        self.graph.setLabel('left', 'Pressure', units='bar')
        self.graph.setLabel('bottom', 'Time', units='s') 
        self.graph.setBackground('w')
        self.graph.setYRange(0, 2)
        self.graph.addLegend()

        # Pressure Curves
        self.curves = []
        for p in self.pressures:
            pen = pg.mkPen(color=p.color, width=2)
            curve = self.graph.plot(pen=pen, name=f"R{p.id}")
            self.curves.append(curve)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.graph)
        self.setContentsMargins(20, 20, 20, 20)

    def update(self, values):
        # History
        for p in self.pressures:
            if p.id <= len(values):
                if not p.active or values[p.id - 1] is None:
                    val = float('nan')
                else: 
                    val = values[p.id - 1]
                self.history[p.id - 1].append(val)

        # Time
        stamp = self.time[-1] + self.dt if len(self.time) > 0 else 0
        self.time.append(stamp)

        # Graph
        for i, curve in enumerate(self.curves):
            if i < len(self.history):
                curve.setData(self.time, self.history[i])

class Conditioning(QWidget):
    def __init__(self, parent, id, request=None):
        super().__init__(parent)
        self.parent = parent
        self.request = request

        # Properties
        self.id = id

        # Header
        self.header = QLabel(f"Conditioning", alignment=Qt.AlignmentFlag.AlignCenter)
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: #acacac;
                color: black;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
            }}
        """)

        # Toggle Button
        self.button = QPushButton("Start")
        self.button.clicked.connect(self.request_toggle)
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-size: 12px;
                padding: 4px 4px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.header)
        self.container.addWidget(self.button)
        self.container.setSpacing(0)

    def request_toggle(self):
        if self.request is not None:
            self.parent.running = True
            self.request("conditioning")

class Sampling(QWidget):
    def __init__(self, parent, id, request=None):
        super().__init__(parent)
        self.parent = parent
        self.request = request

        # Properties
        self.id = id

        # Header
        self.header = QLabel(f"Sampling", alignment=Qt.AlignmentFlag.AlignCenter)
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: #acacac;
                color: black;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
            }}
        """)

        # Toggle Button
        self.button = QPushButton("Start")
        self.button.clicked.connect(self.request_toggle)
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-size: 12px;
                padding: 4px 4px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.header)
        self.container.addWidget(self.button)
        self.container.setSpacing(0)

    def request_toggle(self):
        if self.request is not None:
            self.parent.running = True
            self.request("conditioning")

class Reacting(QWidget):
    def __init__(self, parent, id, request=None):
        super().__init__(parent)
        self.parent = parent
        self.request = request

        # Properties
        self.id = id

        # Header
        self.header = QLabel(f"Reacting", alignment=Qt.AlignmentFlag.AlignCenter)
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: #acacac;
                color: black;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
            }}
        """)

        # Toggle Button
        self.button = QPushButton("Start")
        self.button.clicked.connect(self.request_toggle)
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-size: 12px;
                padding: 4px 4px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.header)
        self.container.addWidget(self.button)
        self.container.setSpacing(0)

    def request_toggle(self):
        if self.request is not None:
            self.parent.running = True
            self.request("conditioning")

class Control(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        # Properties
        self.running = False

        # Schematic
        self.schematic = schematic.Schematic(self)

        # Graph
        self.graph = History(self, self.schematic.reactors)
        self.schematic.keller_worker.update.connect(self.graph.update)

        # ----- Procedures -----
        # Worker
        self.procedures = procedures.Procedures(self)
        self.procedures_worker = worker.Worker(self.procedures)
        self.procedures_worker.start()

        # Display
        self.conditioning = Conditioning(self, 1, self.procedures_worker.request)
        self.sampling = Sampling(self, 2, self.procedures_worker.request)
        self.reacting = Reacting(self, 3, self.procedures_worker.request)

        # Stop Button
        self.button = QPushButton("Stop")
        self.button.clicked.connect(self.stop)
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

        # Container
        self.container = QHBoxLayout()
        self.container.addWidget(self.conditioning, alignment=Qt.AlignmentFlag.AlignCenter)
        self.container.addWidget(self.sampling, alignment=Qt.AlignmentFlag.AlignCenter)
        self.container.addWidget(self.reacting, alignment=Qt.AlignmentFlag.AlignCenter)
        self.container.addWidget(self.button, alignment=Qt.AlignmentFlag.AlignCenter)

        # Grid
        self.grid = QGridLayout(self)
        self.grid.addWidget(self.schematic, 0, 0)
        self.grid.addWidget(self.graph, 0, 1)
        self.grid.addLayout(self.container, 1, 0)

        self.setContentsMargins(20, 20, 20, 20)

    def stop(self):
        self.schematic.stop()
        self.running = False

    def closeEvent(self, event):
        self.schematic.closeEvent(event)
        self.running = False
        self.procedures_worker.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = Control(parent=None)

    window.show() #showMaximized()
    sys.exit(app.exec())


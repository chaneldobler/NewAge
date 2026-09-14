import sys
import os
import json
from PySide6 import QtWidgets,QtCore
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QVBoxLayout, QLabel, QSizePolicy, QGridLayout, QHBoxLayout
from PySide6.QtCore import QSize, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QPolygonF, QBrush
import pyqtgraph as pg

# Hardware & Worker Imports
import keller, smc, tm, peltier
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
                    val = p.get_value()
                self.history[p.id - 1].append(val)

        # Time
        stamp = self.time[-1] + self.dt if len(self.time) > 0 else 0
        self.time.append(stamp)

        # Graph
        for i, curve in enumerate(self.curves):
            if i < len(self.history):
                curve.setData(self.time, self.history[i])

class Status(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        # Colored Header
        self.header = QLabel(f"Status", alignment=Qt.AlignmentFlag.AlignCenter)
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: #555555;
                color: white;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
            }}
        """)

        # Name Display
        self.name_display = QLabel("", alignment=Qt.AlignmentFlag.AlignLeft)
        self.name_display.setStyleSheet(f"""
            QLabel {{
                background-color: white;
                color: black;
                border: none;
                border-radius: 0px;
                font-size: 12px;
                padding: 8px 8px;
            }}
        """)

        # Value Display
        self.value_display = QLabel("", alignment=Qt.AlignmentFlag.AlignRight)
        self.value_display.setStyleSheet(f"""
            QLabel {{
                background-color: white;
                color: black;
                border: none;
                border-radius: 0px;
                font-size: 12px;
                padding: 8px 8px;
            }}
        """)

        self.table = QHBoxLayout(self)
        self.table.addWidget(self.name_display)
        self.table.addWidget(self.value_display)

        self.container = QVBoxLayout(self)
        self.container.addWidget(self.header)
        self.container.addLayout(self.table)
        self.container.setSpacing(0)

        self.update(0, "")

    def update(self, status: int, message: str):
        if message != "" and message in self.names:
            id = self.names.index(message)
            if status == 0:
                self.values[id] = 1  
                self.config[message] = 1

            with open("status.json", "w") as f:
                json.dump(self.config, f, indent=2)

        with open("status.json", "r") as f:
            self.config = json.load(f)

        self.names = list(self.config.keys())
        self.values = list(self.config.values())

        self.name_text = "\n" + "\n".join(self.names) + "\n"
        self.value_text = "\n" + "\n".join(str(v) for v in self.values) + "\n"

        self.name_display.setText(self.name_text)
        self.value_display.setText(self.value_text)

    def get_funcs(self):
        func = []
        for id, name in enumerate(self.names):
            if self.values[id] == 0:
                func.append(name.replace(" ", "_"))

class Control(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        # Devices
        self.smc_device = smc.SmcDevNet()
        self.smc_device.start()
        self.keller_device = keller.Keller()
        self.tm_device = tm.TMHardware()
        self.peltier_device = peltier.Peltier()

        # Schematic
        self.schematic = schematic.Schematic(self)

        # Graph
        self.graph = History(self, self.schematic.reactors)
        self.schematic.keller_worker.update.connect(self.graph.update)

        # Procedures 
        self.procedures = procedures.Procedures(self)

        # Status
        self.status = Status(self)
        self.procedures.procedures_worker.reply.connect(self.status.update)

        # Start Button
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start)
        self.start_btn.setStyleSheet("""
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

        # Stop Button
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setStyleSheet("""
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
        self.container.addWidget(self.status, alignment=Qt.AlignmentFlag.AlignCenter)
        self.container.addWidget(self.start_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        self.container.addWidget(self.stop_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Grid
        self.grid = QGridLayout(self)
        self.grid.addWidget(self.schematic, 0, 0)
        self.grid.addWidget(self.graph, 0, 1)
        self.grid.addLayout(self.container, 1, 0)

        self.setContentsMargins(20, 20, 20, 20) 

    def start(self):
        self.procedures.start()

        for func in self.status.get_funcs():
            f = getattr(self.procedures, func)
            if f is not None:
                self.procedures_worker.request(f)

    def stop(self):
        self.schematic.stop()
        self.procedures.stop()

    def closeEvent(self, event):
        self.schematic.closeEvent(event)
        self.procedures.closeEvent(event)

        self.tm_device.stop([h.id for h in self.schematic.heaters])
        self.peltier_device.stop()
        self.smc_device.stop()

        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = Control(parent=None)

    window.show() #showMaximized()
    sys.exit(app.exec())


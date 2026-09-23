import sys
import os
import json
from PySide6 import QtWidgets,QtCore
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QVBoxLayout, QLabel, QSizePolicy, QGridLayout, QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem, QTableView, QHeaderView
from PySide6.QtCore import QSize, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QPolygonF, QBrush, QStandardItem, QStandardItemModel
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
        self.setFixedSize(1000, 800)

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

    def reset(self):
        self.history = [[] for _ in self.pressures]
        self.time = []

class Table(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.headers = ["Sample Name", "Weight [mg]", "CO2", "CO2 fin", "CO2 + H2", "p end"]
        self.reactors = [f"Reactor {i+1}" for i in range(10)]

        self.model = QStandardItemModel(len(self.reactors), len(self.headers))
        self.model.setHorizontalHeaderLabels(self.headers)
        self.model.setVerticalHeaderLabels(self.reactors)

        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.view.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.view.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.view.setStyleSheet("""
            QTableView, QHeaderView, QHeaderView::section, QTableCornerButton::section {
                background-color: #ffffff;
                color: #000000;
                border: none;
                font-size: 13px;
            }
            QTableView {
                gridline-color: #e0e0e0;
            }
            
            /* Padding for data cells (Y: 8px, X: 12px) */
            QTableView::item {
                padding-top: 8px;
                padding-bottom: 8px;
                padding-left: 12px;
                padding-right: 12px;
            }
            
            /* Padding for headers (Y: 8px, X: 12px) */
            QHeaderView::section, QTableCornerButton::section {
                padding-top: 8px;
                padding-bottom: 8px;
                padding-left: 12px;
                padding-right: 12px;
                border-right: 1px solid #e0e0e0;
                border-bottom: 1px solid #e0e0e0;
            }
            
            QTableView:focus {
                outline: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        self.setFixedSize(1000, 400)
        self.setContentsMargins(20, 20, 20, 20)

    def set_entry(self, text, row, col):
        item = QStandardItem(str(text))
        self.model.setItem(row, col, item)

    def clear(self):
        for row in range(self.model.rowCount()):
            for col in range(self.model.columnCount()):
                self.model.setItem(row, col, None)

class Display(QWidget):
    def __init__(self, parent, name):
        super().__init__(parent)
        self.name = name

        self.button = QPushButton(self.name)
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 12px 16px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

        color = QColor.fromHslF(0.6, 0.45, 0.3)
        self.display = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.display.setStyleSheet(f"""
            QLabel {{
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 0px;
                font-size: 12px;
                padding: 8px 16px;
            }}
        """)

        self.container = QVBoxLayout(self)
        self.container.addWidget(self.button)
        self.container.addWidget(self.display)
        self.container.setSpacing(0)

    def set_text(self, message: str):
        self.display.setText(message)

class Button(QWidget):
    def __init__(self, parent, name):
        super().__init__(parent)
        self.name = name

        self.button = QPushButton(self.name)
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

        self.container = QVBoxLayout(self)
        self.container.addWidget(self.button)

class Control(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        with open("procedures_config.json", "r") as f:
            self.config = json.load(f)

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

        # Table
        self.table = Table(self)

        # Procedures 
        self.procedures = procedures.Procedures(self)
    
        # Displays
        self.conditioning = Display(self, "Conditioning")
        self.load_samples = Display(self, "Load Samples")
        self.reaction = Display(self, "Reaction")
        self.separate = Display(self, "Separate")
        self.separate.button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 0px;
                border-radius: 0px;
                font-size: 12px;
                font-weight: bold;
                padding: 12px 16px;
            }
        """)
        self.stages = {
            "Conditioning": self.conditioning, 
            "Load Samples": self.load_samples, 
            "Reaction": self.reaction, 
            "Separate": self.separate
        } # Could be prettier

        self.conditioning.button.clicked.connect(lambda: self.procedures.start([self.conditioning.name]))
        self.load_samples.button.clicked.connect(lambda: self.procedures.start([self.load_samples.name]))
        self.reaction.button.clicked.connect(lambda: self.procedures.start([self.reaction.name]))

        self.displays = QVBoxLayout()
        self.displays.setSpacing(0)
        self.displays.setContentsMargins(0, 0, 0, 0)
        self.displays.addWidget(self.conditioning)
        self.displays.addWidget(self.load_samples)
        self.displays.addWidget(self.reaction)
        self.displays.addWidget(self.separate)

        # Buttons
        self.start_btn = Button(self, "Start")
        self.stop_btn = Button(self, "Stop")
        self.reset_btn = Button(self, "Reset")

        self.start_btn.button.clicked.connect(lambda: self.procedures.start([self.conditioning.name, self.load_samples.name, self.reaction.name]))
        self.stop_btn.button.clicked.connect(self.stop)
        self.reset_btn.button.clicked.connect(self.reset)

        self.buttons = QHBoxLayout()
        # self.buttons.setSpacing(0)
        self.buttons.addWidget(self.start_btn, alignment=Qt.AlignmentFlag.AlignTop)
        self.buttons.addWidget(self.stop_btn, alignment=Qt.AlignmentFlag.AlignTop)
        self.buttons.addWidget(self.reset_btn, alignment=Qt.AlignmentFlag.AlignTop)

        # Overview
        self.overview = QWidget(self)
        self.overview.setFixedSize(700, 400)
        self.container = QHBoxLayout(self.overview)
        self.container.setContentsMargins(20, 20, 20, 20)
        self.container.addLayout(self.buttons)
        self.container.addLayout(self.displays)

        # Grid
        self.grid = QGridLayout(self)
        self.grid.addWidget(self.schematic, 0, 0)
        self.grid.addWidget(self.graph, 0, 1)
        self.grid.addWidget(self.table, 1, 1)
        self.grid.addWidget(self.overview, 1, 0, alignment=Qt.AlignmentFlag.AlignRight)

    # def start(self, stages):
    #     self.procedures.start(stages)

    def stop(self):
        self.schematic.stop()
        self.procedures.stop()

        self.smc_device.close_all()
        self.tm_device.stop([h.id for h in self.schematic.heaters])
        self.peltier_device.stop()

    def reset(self):
        self.table.clear()
        self.graph.reset()
        for r in self.schematic.reactors:
            r.reset()
        for obj in self.stages.values():
            obj.set_text("")

    def set_running(self, stage: str, message: str):
        if stage in self.stages.keys():
            self.stages[stage].set_text(message)

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


import sys
import os
import json
from PySide6 import QtWidgets,QtCore
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QVBoxLayout, QLabel, QSizePolicy, QGridLayout
from PySide6.QtCore import QSize, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QPolygonF, QBrush
import pyqtgraph as pg

# Hardware & Worker Imports
import keller, smc, tm
import worker
import procedures
import schematic

class History(QWidget):
    def __init__(self, parent, pressures):
        super().__init__(parent)
        self.parent = parent
        self.pressures = pressures

        # Properties
        self.history = [[] for _ in self.pressures]

        # Graph
        self.graph = pg.PlotWidget()
        self.graph.setLabel('left', 'Pressure', units='bar')
        self.graph.setLabel('bottom', 'Time Steps') #TODO: adapt to Time s
        self.graph.setBackground('w')
        self.graph.setYRange(0, 2)
        self.graph.addLegend()

        # Pressure Curves
        self.curves = []
        for p in self.pressures:
            pen = pg.mkPen(color=p.color, width=2)
            curve = self.graph.plot(pen=pen, name=f"R{p.id}")
            self.curves.append(curve)

        # Box Frame
        self.frame = QFrame(self)
        self.frame.setStyleSheet("QFrame { background-color: #ffffff; }")
        self.frame.setFrameShape(QFrame.Shape.Box)
        self.frame.setLineWidth(2)

        # Box Content
        self.content = QVBoxLayout(self.frame)
        self.content.addWidget(self.graph)
        self.content.setContentsMargins(4, 4, 4, 4)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.frame)

    def update(self, values):
        # History
        for i, val in enumerate(values):
            if i < len(self.pressures):
                p = self.pressures[i]
                if not p.active or val is None:
                    val = float('nan')
                self.history[i].append(val)

        # Graph
        for i, curve in enumerate(self.curves):
            if i < len(self.history):
                curve.setData(self.history[i])


class Control(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        # ----- Devices and Workers -----
        # SMC
        self.smc_device = smc.SmcDevNet()
        self.smc_device.start()
        self.smc_worker = worker.Worker(self.smc_device, "get_status_all", 0.1)
        self.smc_worker.update.connect(self.valve_update)
        self.smc_worker.start()

        # Keller
        self.keller_device = keller.Keller()
        self.keller_worker = worker.Worker(self.keller_device, "get_pressure_all", 0.1)
        self.keller_worker.update.connect(self.pressure_update)
        self.keller_worker.start()

        # TM
        self.tm_device = tm.TMHardware()
        self.tm_worker = worker.Worker(self.tm_device, "get_temperature_all", 0.1)
        self.tm_worker.update.connect(self.temperature_update)
        self.tm_worker.start()

        # ----- Grid -----
        self.grid = QGridLayout(self)

        # Schematic
        self.schematic = schematic.Schematic(self, self.smc_worker.request)
        self.grid.addWidget(self.schematic, 0, 0)

        # Graph
        self.graph = History(self, self.schematic.reactors)
        self.grid.addWidget(self.graph, 0, 1)

    def valve_update(self, values):
        for i, val in enumerate(values):
            if i < len(self.schematic.valves):
                self.schematic.valves[i].set_status(val)

    def pressure_update(self, values):
        for i, val in enumerate(values):
            if i < len(self.schematic.reactors):
                self.schematic.reactors[i].set_value(val)
        self.graph.update(values)

    def temperature_update(self, values):
        for i, val in enumerate(values):
            if i < len(self.schematic.heaters):
                self.schematic.heaters[i].set_value(val)
            
    def closeEvent(self, event):
        self.keller_worker.stop()
        self.tm_worker.stop()
        self.smc_worker.stop()
        self.smc_device.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = QWidget()
    control = Control(parent=window)

    window.show()
    sys.exit(app.exec())


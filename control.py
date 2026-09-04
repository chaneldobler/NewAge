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
        for p in self.pressures:
            if p.id <= len(values):
                if not p.active or values[p.id - 1] is None:
                    val = float('nan')
                else: 
                    val = values[p.id - 1]
                self.history[p.id - 1].append(val)

        # Graph
        for i, curve in enumerate(self.curves):
            if i < len(self.history):
                curve.setData(self.history[i])


class Control(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.container = QHBoxLayout(self)

        # Schematic
        self.schematic = schematic.Schematic(self)
        self.container.addWidget(self.schematic)

        # Graph
        self.graph = History(self, self.schematic.reactors)
        self.schematic.keller_worker.update.connect(self.graph.update)
        self.container.addWidget(self.graph)
            
    def closeEvent(self, event):
        self.schematic.closeEvent(event)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = Control(parent=None)

    window.show()
    sys.exit(app.exec())


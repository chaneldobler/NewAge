import sys
import os
import json
from PySide6 import QtWidgets,QtCore
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QVBoxLayout, QLabel, QSizePolicy, QGridLayout, QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem, QTableView, QHeaderView, QMessageBox
from PySide6.QtCore import QSize, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QPolygonF, QBrush, QStandardItem, QStandardItemModel
import pyqtgraph as pg

# Hardware & Worker Imports
import keller, smc, tm, peltier
import worker
import procedures
import schematic
import components

# adapt to offset yes or no?

class History(QWidget):
    def __init__(self, parent, pressures):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(2000, 1300)
        self.pressures = pressures
        self.history = [[] for _ in self.pressures]
        self.dt = 0.1
        self.time = []

        self.graph = pg.PlotWidget()
        self.graph.setLabel('left', 'Pressure', units='bar')
        self.graph.setLabel('bottom', 'Time', units='s') 
        self.graph.setBackground('w')
        self.graph.setYRange(0, 2)
        self.graph.addLegend()

        self.curves = []
        for p in self.pressures:
            pen = pg.mkPen(color=p.color, width=2)
            curve = self.graph.plot(pen=pen, name=f"R{p.id}")
            self.curves.append(curve)

        self.container = QGridLayout(self)
        self.container.addWidget(self.graph, 0, 0)

    def update(self, values):
        for p in self.pressures:
            if p.id <= len(values):
                if not p.active or values[p.id - 1] is None:
                    val = float('nan')
                else: 
                    val = p.get_value()
                self.history[p.id - 1].append(val)

        stamp = self.time[-1] + self.dt if len(self.time) > 0 else 0
        self.time.append(stamp)

        for i, curve in enumerate(self.curves):
            if i < len(self.history):
                curve.setData(self.time, self.history[i])

    def reset(self):
        self.history = [[] for _ in self.pressures]
        self.time = []

class Table(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(2000, 600)
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
                background-color: white;
                color: black;
                font-size: 20px;
                border: none;
            }
            QTableView {
                gridline-color: grey;
            }
            QTableView::item {
                padding-top: 8px;
                padding-bottom: 8px;
                padding-left: 12px;
                padding-right: 12px;
            }
            QHeaderView::section, QTableCornerButton::section {
                padding-top: 8px;
                padding-bottom: 8px;
                padding-left: 64px;
                padding-right: 64px;
                border-right: 1px solid grey;
                border-bottom: 1px solid grey;
            }
            QTableView:focus {
                outline: none;
            }
        """)

        self.container = QGridLayout(self)
        self.container.addWidget(self.view)

    def set_entry(self, text, row, col):
        item = QStandardItem(str(text))
        self.model.setItem(row, col, item)

    def clear(self):
        for row in range(self.model.rowCount()):
            for col in range(self.model.columnCount()):
                self.model.setItem(row, col, None)

class Display(QFrame):
    def __init__(self, parent, label):
        super().__init__(parent)
        self.parent = parent
        self.active = True
        self.running = False

        self.color = QColor.fromHslF(0.75, 0.5, 0.45)
        self.title = components.Title(label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.button = QPushButton("Start")

        self.container = QVBoxLayout(self)
        self.container.addWidget(self.title)
        self.container.addWidget(self.button)

        self.update()

    def update(self):
        if not self.active:
            color = "black"
        elif not self.running:
            color = "grey"
        else:
            color = self.color.name()
        self.title.setStyleSheet(f"background-color: {color};")

class Status(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.title = components.Title("Status", alignment=Qt.AlignmentFlag.AlignCenter)
        self.main = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.side = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)

        self.container = QVBoxLayout(self)
        self.container.addWidget(self.title)
        self.container.addWidget(self.main)
        self.container.addWidget(self.side)      

    def set_main(self, message: str):
        self.main.setText(message)

    def set_side(self, message: str):
        self.side.setText(message)

class Reactors(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.title = components.Title("Reactor Valves", alignment=Qt.AlignmentFlag.AlignCenter)
        self.btn_open = QPushButton("Open")
        self.btn_close = QPushButton("Close")

        self.container = QGridLayout(self)
        self.container.addWidget(self.title, 0, 0, 1, 2)
        self.container.addWidget(self.btn_open, 1, 0)
        self.container.addWidget(self.btn_close, 1, 1)

class Panel(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(1300, 600)
        self.setStyleSheet(components.styleSheet)

        self.graphitization = Display(self, "Graphitization")
        self.conditioning = Display(self, "Conditioning")
        self.load_samples = Display(self, "Load Samples")
        self.reaction = Display(self, "Reaction")
        self.status = Status(self)
        self.reactors = Reactors(self)
        self.stop = QPushButton("Abort")

        self.container = QGridLayout(self)
        self.container.addWidget(self.stop, 0, 1)
        self.container.addWidget(self.graphitization, 1, 1)
        self.container.addWidget(self.status, 0, 0, 2, 1)
        self.container.addWidget(self.conditioning, 2, 0)
        self.container.addWidget(self.load_samples, 2, 1)
        self.container.addWidget(self.reaction, 2, 2)
        self.container.addWidget(self.reactors, 3, 1)

class Control(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        with open("procedures_config.json", "r") as f:
            self.config = json.load(f)

        self.smc_device = smc.SmcDevNet()
        self.smc_device.start()
        self.keller_device = keller.Keller()
        self.tm_device = tm.TMHardware()
        self.peltier_device = peltier.Peltier()

        self.schematic = schematic.Schematic(self)
        self.graph = History(self, self.schematic.reactors)
        self.table = Table(self)
        self.panel = Panel(self)
        self.procedures = procedures.Procedures(self)

        self.schematic.keller_worker.update.connect(self.graph.update)
        self.panel.conditioning.button.clicked.connect(lambda: self.procedures.start(["Conditioning"])) # move to function parameters?
        self.panel.load_samples.button.clicked.connect(lambda: self.procedures.start(["Load Samples"]))
        self.panel.reaction.button.clicked.connect(lambda: self.procedures.start(["Reaction"]))
        self.panel.graphitization.button.clicked.connect(lambda: self.procedures.start(["Conditioning", "Load Samples", "Reaction"])) # make a wrapper
        self.panel.stop.clicked.connect(self.stop)
        self.panel.reactors.btn_open.clicked.connect(lambda: self.procedures.set_reactors(1))
        self.panel.reactors.btn_close.clicked.connect(lambda: self.procedures.set_reactors(0))

        self.container = QGridLayout(self)
        self.container.addWidget(self.schematic, 0, 0)
        self.container.addWidget(self.graph, 0, 1)
        self.container.addWidget(self.panel, 1, 0)
        self.container.addWidget(self.table, 1, 1)

    def prompt(self, message, event):
        reply = QMessageBox.warning(
            self,
            "User Action Required",
            message,
            QMessageBox.StandardButton.Retry
        )
        self.procedures.prompt_reply = reply
        event.set()

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

    def set_main(self, message: str):
        self.panel.status.set_main(message)
        print(message)

    def set_side(self, message: str):
        self.panel.status.set_side(message)
        print(message)

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


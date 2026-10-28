import sys
import os
import json
import time
from PySide6 import QtWidgets,QtCore
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QVBoxLayout, QLabel, QSizePolicy, QGridLayout, QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem, QTableView, QHeaderView, QMessageBox
from PySide6.QtCore import QSize, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QPolygonF, QBrush, QStandardItem, QStandardItemModel
import pyqtgraph as pg

# Hardware & Worker Imports
import keller, smc, tm, peltier, tcpip
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
        self.start = 0
        self.end = 0
        self.stamp = 0
        self.time = []

        self.graph = pg.PlotWidget()
        self.graph.setLabel('left', 'Pressure', units='bar')
        self.graph.setLabel('bottom', 'Time', units='min') 
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

    def update(self, _):
        for p in self.pressures:
            if not p.active or p.value is None:
                val = float('nan')
            else: 
                val = p.get_value()
            self.history[p.id - 1].append(val)

        self.end = time.time()
        self.stamp = self.stamp + self.end - self.start if len(self.time) > 0 else 0
        self.start = self.end
        self.time.append(self.stamp/60)

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
        self.setFixedSize(2000, 700) # make adaptive in height
        self.headers = ["Sample Name", "Weight [mg]", "CO2 [mbar]", "CO2 fin [mbar]", "CO2 + H2 [mbar]", "p end [mbar]"]
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
                font-size: 22px;
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
                padding-top: 16px;
                padding-bottom: 16px;
                padding-left: 32px;
                padding-right: 32px;
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

        self.conditioning = QPushButton("Conditioning")
        self.load_samples = QPushButton("Load Samples")
        self.reaction = QPushButton("Reaction")

        self.start =  QPushButton("Start")
        self.stop = QPushButton("Stop")
        self.reset = QPushButton("Reset")

        self.container = QGridLayout(self)
        self.container.addWidget(self.title, 0, 0, 1, 2)
        self.container.addWidget(self.start, 1, 0)
        self.container.addWidget(self.stop, 2, 0)
        self.container.addWidget(self.reset, 3, 0)
        self.container.addWidget(self.conditioning, 1, 1)
        self.container.addWidget(self.load_samples, 2, 1)
        self.container.addWidget(self.reaction, 3, 1)

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

        self.title = components.Title("Activity", alignment=Qt.AlignmentFlag.AlignCenter)
        self.worker_label = QLabel("Worker", alignment=Qt.AlignmentFlag.AlignRight)
        self.helper_label = QLabel("Helper", alignment=Qt.AlignmentFlag.AlignRight)
        self.worker_display = components.Body("", alignment=Qt.AlignmentFlag.AlignLeft)
        self.helper_display = components.Body("", alignment=Qt.AlignmentFlag.AlignLeft)

        self.container = QGridLayout(self)
        self.container.addWidget(self.title, 0, 0, 1, 2)
        self.container.addWidget(self.worker_label, 1, 0)
        self.container.addWidget(self.helper_label, 2, 0)      
        self.container.addWidget(self.worker_display, 1, 1)
        self.container.addWidget(self.helper_display, 2, 1) 

    def set_worker(self, message: str):
        self.worker_display.setText(message)

    def set_helper(self, message: str):
        self.helper_display.setText(message)

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
        self.setFixedSize(1400, 700)
        self.setStyleSheet(components.styleSheet)

        self.graphitization = Display(self, "Graphitization")
        self.status = Status(self)
        self.reactors = Reactors(self)

        self.container = QGridLayout(self)
        self.container.addWidget(self.graphitization, 0, 1, 2, 1)
        self.container.addWidget(self.status, 2, 1)
        self.container.addWidget(self.reactors, 3, 1)
        self.container.addWidget(QWidget(), 0, 0)

class Control(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        with open("procedures_config.json", "r") as f:
            self.config = json.load(f)

        self.smc = smc.SmcDevNet()
        self.keller = keller.Keller()
        self.tm = tm.TMHardware()
        self.peltier = peltier.Peltier()
        self.tcpip = tcpip.TcpIp()

        self.smc.start()

        self.schematic = schematic.Schematic(self)
        self.graph = History(self, self.schematic.reactors)
        self.table = Table(self)
        self.panel = Panel(self)

        self.worker = worker.Worker()
        self.helper = worker.Worker()
        self.smc_worker = worker.Worker(0.1, self.smc.get)
        self.keller_worker = worker.Worker(0.1, self.keller.get, self.schematic.get_reactor_idx())
        self.tm_worker = worker.Worker(1.0, self.tm.get, self.schematic.get_heaters_idx())
        self.peltier_worker = worker.Worker(1.0)

        self.procedures = procedures.Procedures(
            self, self.tcpip, self.smc, self.keller, self.tm, self.peltier,
            self.worker, self.helper, self.table, self.schematic
        )

        self.panel.graphitization.conditioning.clicked.connect(lambda: self.procedures.start(["Conditioning"]))
        self.panel.graphitization.load_samples.clicked.connect(lambda: self.procedures.start(["Load Samples"]))
        self.panel.graphitization.reaction.clicked.connect(lambda: self.procedures.start(["Reaction"]))
        self.panel.graphitization.start.clicked.connect(lambda: self.procedures.start(["Conditioning", "Load Samples", "Reaction"]))
        self.panel.graphitization.stop.clicked.connect(self.stop)
        self.panel.graphitization.reset.clicked.connect(self.reset)
        self.panel.reactors.btn_open.clicked.connect(lambda: self.procedures.set_reactor_valves(1))
        self.panel.reactors.btn_close.clicked.connect(lambda: self.procedures.set_reactor_valves(0))

        self.worker.message.connect(self.panel.status.set_worker)
        self.helper.message.connect(self.panel.status.set_helper)
        self.worker.prompt.connect(self.prompt)
        self.smc_worker.update.connect(self.schematic.set_valves_active)
        self.keller_worker.update.connect(self.schematic.set_reactor_values)
        self.tm_worker.update.connect(self.schematic.set_heater_values)
        self.keller_worker.update.connect(self.graph.update)

        self.worker.start()
        self.helper.start()
        self.smc_worker.start()
        self.keller_worker.start()
        self.tm_worker.start()
        self.peltier_worker.start()

        self.container = QGridLayout(self)
        self.container.addWidget(self.schematic, 0, 0)
        self.container.addWidget(self.graph, 0, 1)
        self.container.addWidget(self.panel, 1, 0)
        self.container.addWidget(self.table, 1, 1)

    def stop(self):
        self.worker.clear()
        self.helper.clear()

        self.schematic.stop()
        self.procedures.stop()

        self.smc.close_all()
        self.tm.stop([h.id for h in self.schematic.heaters])
        self.peltier.stop()

    def reset(self):
        self.table.clear()
        self.graph.reset()
        for r in self.schematic.reactors:
            r.reset()

    def prompt(self, message, event=None):
        if event is not None:
            reply = QMessageBox.warning(
                self,
                "User Action Required",
                message,
                QMessageBox.StandardButton.Retry
            )
            self.procedures.prompt_reply = reply
            event.set()
        else:
            QMessageBox.warning(
                self,
                "Configuration Error",
                message,
            )

    def closeEvent(self, event):
        self.stop()

        self.keller_worker.stop()
        self.tm_worker.stop()
        self.smc_worker.stop()
        self.peltier_worker.stop()
        self.worker.stop()
        self.helper.stop()

        self.smc.stop()

        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = Control(parent=None)

    window.show() #showMaximized()
    sys.exit(app.exec())


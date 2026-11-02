import sys
import time
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QAbstractItemView, QLabel, QGridLayout, QTableView, QHeaderView, QMessageBox
from PySide6.QtGui import QStandardItem, QStandardItemModel, QFont, QColor
from PySide6.QtCore import Qt
import pyqtgraph as pg
import keller, smc, tm, peltier, tcpip
import worker
import procedures
import schematic
import components as c

class History(QWidget):
    def __init__(self, parent, pressures):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(1600, 1100)
        self.pressures = pressures
        self.history = [[] for _ in self.pressures]

        self.start = 0
        self.end = 0
        self.stamp = 0
        self.time = []

        self.graph = pg.PlotWidget()
        self.graph.setLabel('left', 'Pressure', units='bar', **{'color': 'grey', 'font-size': '18pt'})
        self.graph.setLabel('bottom', 'Time', units='min', **{'color': 'grey', 'font-size': '18pt'}) 
        self.graph.setBackground('w')
        self.graph.getViewBox().setLimits(xMin=0)
        self.graph.setYRange(0, 2.1)
        self.graph.addLegend(labelTextSize='14pt')
        axis_font = QFont()
        axis_font.setPointSize(14)
        self.graph.getAxis('left').setStyle(tickFont=axis_font)
        self.graph.getAxis('bottom').setStyle(tickFont=axis_font)

        self.curves = []
        for p in self.pressures:
            pen = pg.mkPen(color=p.color, width=4)
            curve = self.graph.plot(pen=pen, name=f"R{p.id}")
            self.curves.append(curve)

        self.container = QGridLayout(self)
        self.container.addWidget(self.graph, 0, 0)

    def set_stamp(self, _):  
        self.end = time.time()
        self.stamp = self.stamp + self.end - self.start if len(self.time) > 0 else 0
        self.start = self.end
        self.time.append(self.stamp / 60)

        for i, p in enumerate(self.pressures):
            if not p.active:
                val = float('nan')
            else: 
                val = p.get_value()
            self.history[i].append(val)

        for i, curve in enumerate(self.curves):
            if i < len(self.history):
                curve.setData(self.time, self.history[i])

    def reset(self):
        self.history = [[] for _ in self.pressures]
        self.time = []

        self.graph.setYRange(0, 2.1)

class Table(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(1600, 600)
        self.headers = ["Sample Name", "Weight [mg]", "CO2 [mbar]", "CO2 fin [mbar]", "CO2 + H2 [mbar]", "p end [mbar]", "N [%]", "C [%]"]
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
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
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
                padding-left: 8px;
                padding-right: 8px;
            }
            QHeaderView::section, QTableCornerButton::section {
                padding-top: 16px;
                padding-bottom: 16px;
                padding-left: 16px;
                padding-right: 16px;
                border-right: 1px solid grey;
                border-bottom: 1px solid grey;
            }
            QTableView:focus {
                outline: none;
            }
        """)

        self.container = QGridLayout(self)
        self.container.addWidget(self.view, 0, 0)

    def get_entry(self, row, col):
        item = self.model.item(row, col)
        return item.text() if item is not None else ""

    def set_entry(self, text, row, col):
        item = QStandardItem(str(text))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.model.setItem(row, col, item)

    def reset(self):
        for row in range(self.model.rowCount()):
            for col in range(self.model.columnCount()):
                self.model.setItem(row, col, None)

class Reactors(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.title = c.Title("Reactor Valves", alignment=Qt.AlignmentFlag.AlignCenter)
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
        self.setFixedSize(1400, 600)
        self.setStyleSheet(c.styleSheet)

        self.graphitization = schematic.Auto(
            parent=self, 
            name="Graphitization", 
            active_txt="Abort", 
            inactive_txt="Start", 
        )
        self.graphitization.set_active(False)
        self.graphitization.set_text()
        self.reset = QPushButton("Reset")
        self.reactors = Reactors(self)
        self.auto = schematic.Auto(parent=self, name="Automatic")
        self.conditioning = schematic.Auto(parent=self, name="Conditioning")
        self.load_samples = schematic.Auto(parent=self, name="Load Samples")
        self.sampling = schematic.Auto(
            parent=self, 
            name="Sampling",
            active_txt="Pause", 
            inactive_txt="Continue"
        )
        self.load_reactor = schematic.Auto(
            parent=self, 
            name="Load Reactor",
            active_txt="Pause", 
            inactive_txt="Continue"
        )
        self.reaction = schematic.Auto(parent=self, name="Reaction")
        self.worker = schematic.Display(parent=self, name="Worker")
        self.helper = schematic.Display(parent=self, name="Helper")

        self.container = QGridLayout(self)
        self.container.addWidget(self.reset, 0, 0)
        self.container.addWidget(self.sampling, 1, 0)
        self.container.addWidget(self.load_reactor, 2, 0)
        self.container.addWidget(QWidget(), 0, 1)
        self.container.addWidget(self.auto, 0, 2)
        self.container.addWidget(self.conditioning, 1, 2)
        self.container.addWidget(self.load_samples, 2, 2)
        self.container.addWidget(self.reaction, 3, 2)
        self.container.addWidget(self.graphitization, 0, 3)
        self.container.addWidget(self.worker, 1, 3)
        self.container.addWidget(self.helper, 2, 3)
        self.container.addWidget(self.reactors, 3, 0)

class Control(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

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
        self.tm_worker = worker.Worker(1.0, self.tm.get, self.schematic.get_heater_idx())
        self.peltier_worker = worker.Worker(1.0)

        self.procedures = procedures.Procedures(
            self, self.tcpip, self.smc, self.keller, self.tm, self.peltier,
            self.worker, self.helper, self.table, self.schematic, self.panel
        )

        self.panel.reactors.btn_open.clicked.connect(lambda: self.procedures.set_reactor_valves(1))
        self.panel.reactors.btn_close.clicked.connect(lambda: self.procedures.set_reactor_valves(0))

        self.panel.graphitization.button.clicked.connect(lambda: self.start(self.panel.graphitization.active))
        self.panel.reset.clicked.connect(self.reset)

        for v in self.schematic.valves:
            v.button.clicked.connect(self.request_wrapper(v))

        self.worker.message.connect(self.panel.worker.display.setText)
        self.helper.message.connect(self.panel.helper.display.setText)
        self.worker.prompt.connect(self.prompt)
        self.helper.prompt.connect(self.prompt)
        self.smc_worker.update.connect(self.schematic.set_valves_active)
        self.keller_worker.update.connect(self.schematic.set_reactor_values)
        self.tm_worker.update.connect(self.schematic.set_heater_values)
        self.keller_worker.update.connect(self.graph.set_stamp)

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

    def start(self, active: bool):
        if active:
            self.panel.graphitization.set_running(True)
            self.procedures.start()
        else:
            self.stop()
        
# make button
    def reset(self):
        self.table.reset()
        self.graph.reset()

    def stop(self):
        self.worker.clear()
        self.helper.clear()

        self.schematic.stop()
        self.procedures.stop()

        self.smc.close_all()
        self.tm.stop([h.id for h in self.schematic.heaters])
        self.peltier.stop()

        self.panel.worker.set_running(False)

        self.panel.graphitization.set_active(False)
        self.panel.graphitization.set_running(False)
        self.panel.graphitization.set_text()

        self.panel.conditioning.set_active(True)
        self.panel.conditioning.set_running(False)
        self.panel.conditioning.set_text() # move funcs

        self.panel.load_samples.set_active(True)
        self.panel.load_samples.set_running(False)
        self.panel.load_samples.set_text() # move funcs

        self.panel.reaction.set_active(True)
        self.panel.reaction.set_running(False)
        self.panel.reaction.set_text() # move funcs

    def prompt(self, message, event=None):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)

        font = QFont()
        font.setPointSize(16)
        msg_box.setFont(font)

        if event is not None:
            msg_box.setWindowTitle("Warning")
            msg_box.setText(message)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Retry)
            self.procedures.prompt_reply = msg_box.exec()
            event.set()
        else:
            msg_box.setWindowTitle("Error")
            msg_box.setText(message)
            msg_box.exec()

    def request_wrapper(self, valve):
        return lambda: self.request(valve)

    def request(self, valve):
            if valve.active:
                self.smc_worker.request(self.smc.set, [valve.id], 0)
            else:
                self.smc_worker.request(self.smc.set, [valve.id], 1)

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
    window.show()
    sys.exit(app.exec())


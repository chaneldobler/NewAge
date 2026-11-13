import sys
import json
import time
import os
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QComboBox, QFileDialog, QGridLayout, QTableView, QHeaderView, QMessageBox
from PySide6.QtGui import QStandardItem, QStandardItemModel, QFont, QColor
from PySide6.QtCore import Qt
import pyqtgraph as pg
import keller, smc, tm, peltier, tcpip
import worker
import procedures
import schematic
import components as c
import database as db

class History(QWidget):
    def __init__(self, parent, pressures):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(1200, 900)
        self.pressures = pressures
        self.history = [[] for _ in self.pressures]
        self.filename = "history.json"
        self.running = False

        self.start = 0
        self.end = 0
        self.stamp = 0
        self.time = []

        self.graph = pg.PlotWidget()
        self.graph.setLabel('left', 'Pressure', units='bar', **{'color': 'black', 'font-size': '14pt'})
        self.graph.setLabel('bottom', 'Time', units='min', **{'color': 'black', 'font-size': '14pt'}) 
        self.graph.setBackground('w')
        self.graph.getViewBox().setLimits(xMin=0)
        self.graph.enableAutoRange(axis='x')
        self.graph.setYRange(0, 2.1)
        legend = self.graph.addLegend(labelTextSize='12pt')
        legend.setLabelTextColor('k')
        legend.anchor(itemPos=(0, 1), parentPos=(0, 1), offset=(10, -10))
        axis_font = QFont()
        axis_font.setPointSize(12)

        for axis_name in ['left', 'bottom']:
            axis = self.graph.getAxis(axis_name)
            axis.setStyle(tickFont=axis_font)
            axis.setPen('k')  
            axis.setTextPen('k')  

        self.curves = []
        for p in self.pressures:
            pen = pg.mkPen(color=p.color, width=5)
            curve = self.graph.plot(pen=pen, name=f"R{p.id}")
            self.curves.append(curve)

        self.container = QGridLayout(self)
        self.container.addWidget(self.graph, 0, 0)

    def set_stamp(self, _):
        if not self.running:
            return
          
        self.end = time.time()
        self.stamp = self.stamp + self.end - self.start if len(self.time) > 0 else 0
        self.start = self.end
        self.time.append(self.stamp / 60)

        for i, p in enumerate(self.pressures):
            if not p.running:
                val = float('nan')
            else: 
                val = p.get_value()
            self.history[i].append(val)

        for i, curve in enumerate(self.curves):
            if i < len(self.history):
                curve.setData(self.time, self.history[i])

    def set_running(self, running: bool):
        self.running = running
        self.start = time.time()

    def default(self):
        self.graph.setYRange(0, 2.1)
        self.graph.enableAutoRange(axis='x')

    def auto(self):
        self.graph.getViewBox().autoRange()
        self.graph.enableAutoRange(axis='x')

    def reset(self):
        self.running = False
        self.history = [[] for _ in self.pressures]
        self.time = []
        self.default()

        for curve in self.curves:
            curve.setData([], [])

    def save(self, folder: str):
        time_snapshot = list(self.time)
        history_snapshot = [list(h) for h in self.history]
        data = {
            "time": time_snapshot,
            "history": history_snapshot
        }
        filepath = os.path.join(folder, self.filename)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

    def load(self, folder: str):
        self.running = False

        with open(os.path.join(folder, self.filename), 'r') as f:
            data = json.load(f)

        self.time = data["time"]
        self.history = data["history"]

        self.stamp = 60 * self.time[-1] if len(self.time) > 0 else 0

        for i, curve in enumerate(self.curves):
            if i < len(self.history):
                curve.setData(self.time, self.history[i])

class Table(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(1225, 450)
        self.filename = "table.json"

        self.db = db.Database()

        self.headers = ["Sample Name", "Weight \n [mg]",
                         "CO2 \n [\u03bcg]", "CO2 fin \n [\u03bcg]", "CO2+H2 \n [mbar]", "p end \n [mbar]", 
                         "N [%]", "C [%]", "C / N", "Reaction \n [min]", "Date [Y-M-D H:M:S]"]
        self.reactors = [f"Reactor {i+1}" for i in range(10)]

        self.model = QStandardItemModel(len(self.reactors), len(self.headers))
        self.model.setHorizontalHeaderLabels(self.headers)
        self.model.setVerticalHeaderLabels(self.reactors)

        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.view.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeToContents)
        self.view.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # self.view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.view.setStyleSheet("""
            QTableView, QHeaderView, QHeaderView::section, QTableCornerButton::section {
                background-color: white;
                color: black;
                font-size: 16px;
                border: none;
            }
            QTableView {
                gridline-color: grey;
            }
            QTableView::item {
                padding-top: 4px;
                padding-bottom: 4px;
                padding-left: 4px;
                padding-right: 4px;
            }
            QHeaderView::section, QTableCornerButton::section {
                padding-top: 4px;
                padding-bottom: 4px;
                padding-left: 4px;
                padding-right: 4px;
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
        text = item.text() if item is not None else ""
        return text

    def set_entry(self, val, row, col):
        item = QStandardItem(str(val))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.model.setItem(row, col, item)

    def reset(self):
        for row in range(self.model.rowCount()):
            for col in range(self.model.columnCount()):
                self.model.setItem(row, col, None)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.view.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeToContents)
        self.view.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def store(self):
        map = {
            1: "weight",
            2: "co2_init",
            3: "co2_final",
            4: "hydro_init",
            5: "hydro_final",
            6: "conc_n",
            7: "conc_c",
            8: "cn_ratio",
            9: "react_time",
        }

        for i in range(self.model.rowCount()):
            name = self.get_entry(i, 0)
            if not name:
                continue

            sample_nr, prep_nr, target_nr = name.split(".")
            self.db.store(int(sample_nr), int(prep_nr), int(target_nr), "reactor_nr", i + 101)

            for j, category in map.items():
                val = self.get_entry(i, j)
                if not val:
                    continue

                self.db.store(int(sample_nr), int(prep_nr), int(target_nr), category, float(val))

            val = self.get_entry(i, 10)
            if not val:
                continue
            self.db.store(int(sample_nr), int(prep_nr), int(target_nr), "graphitized", val)
    
    def save(self, folder: str):
        rows = self.model.rowCount()
        cols = self.model.columnCount()

        data = []
        for r in range(rows):
            data.append([self.get_entry(r, c) for c in range(cols)])

        payload = {"data": data}

        with open(os.path.join(folder, self.filename), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)

    def load(self, folder):
        self.reset()

        with open(os.path.join(folder, self.filename), "r", encoding="utf-8") as f:
            payload = json.load(f)

        data = payload.get("data", [])

        for r, row in enumerate(data):
            if r >= self.model.rowCount():
                break
            for c, val in enumerate(row):
                if c >= self.model.columnCount():
                    break
                self.set_entry(val, r, c)

class Next(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.title = c.Title("Next Reactor", alignment=Qt.AlignmentFlag.AlignCenter)
        self.combo = QComboBox()
        self.combo.setStyleSheet("""
        QComboBox {
            color: black;
            background-color: #eeeeee;
            border: 1px solid grey;
        }
        QComboBox:hover {
            border: 1px solid black;
        }
        QComboBox::drop-down {
            border: none;
            background: transparent;
        }
        QComboBox QAbstractItemView {
            border: none;
            background-color: white;
            selection-background-color: grey;
            selection-color: white;
        }""")
        self.combo.addItems([
            "Reactor 1", "Reactor 2", "Reactor 3", "Reactor 4", "Reactor 5",
            "Reactor 6", "Reactor 7", "Reactor 8", "Reactor 9", "Reactor 10", ""
        ])
        self.combo.setCurrentIndex(10)

        self.container = QGridLayout(self)
        self.container.addWidget(self.title, 0, 0)
        self.container.addWidget(self.combo, 1, 0)

class Logging(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.color = QColor.fromHslF(0.6, 0.9, 0.3).name()

        self.title = c.Title("Logging", alignment=Qt.AlignmentFlag.AlignCenter)
        self.start = QPushButton("Start")
        self.pause = QPushButton("Stop")
        self.reset = QPushButton("Reset")
        self.load = QPushButton("Load")
        self.save = QPushButton("Save")
        self.store = QPushButton("Store DB")
        self.auto = QPushButton("A-Zoom")
        self.default = QPushButton("D-Zoom")

        self.container = QGridLayout(self)
        self.container.addWidget(self.title, 0, 0, 1, 1)
        self.container.addWidget(self.start, 1, 0, 1, 1)
        self.container.addWidget(self.pause, 2, 0, 1, 1)
        self.container.addWidget(self.reset, 3, 0, 1, 1)
        self.container.addWidget(self.load, 4, 0, 1, 1)
        self.container.addWidget(self.save, 5, 0, 1, 1)
        self.container.addWidget(self.store, 6, 0, 1, 1)        
        self.container.addWidget(self.auto, 7, 0, 1, 1)
        self.container.addWidget(self.default, 8, 0, 1, 1)

    def set_color(self):
        color = self.color if self.running else "black"
        self.title.setStyleSheet(f"background-color: {color};")

    def set_running(self, running: bool):
        if self.running != running:
            self.running = running
            self.set_color()

class SidePanel(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(220, 900)
        self.setStyleSheet(c.styleSheet)

        self.reactor_valves = schematic.OpenClose(self)
        self.clean_trap = schematic.Auto(
            parent=self,
            name="Clean Trap",
            active_txt="Start",
            inactive_txt="Start",
            running_txt="Start"
        )
        self.clean_trap.button.clicked.disconnect()
        self.offset = schematic.Auto(
            parent=self,
            name="Correct Offset",
            active_txt="Start",
            inactive_txt="Start",
            running_txt="Start"
        )
        self.offset.button.clicked.disconnect()

        self.logging = Logging(self)

        self.container = QGridLayout(self)
        self.container.addWidget(self.logging, 0, 0)
        self.container.addWidget(QWidget(), 1, 0)
        self.container.addWidget(self.reactor_valves, 2, 0)
        self.container.addWidget(self.clean_trap, 3, 0)
        self.container.addWidget(self.offset, 4, 0)
        self.container.addWidget(QWidget(), 5, 0)

class Panel(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(220, 950)
        self.setStyleSheet(c.styleSheet)

        self.auto = schematic.Auto(
            parent=self, 
            name="Automatic",
            running_txt="Pause",
            active_txt="Continue", 
            inactive_txt="Start"
        )
        self.auto.button.clicked.disconnect()
        self.auto.set_active(False)
        self.abort = c.Button(parent=self, name="Abort")

        self.conditioning = schematic.Auto(
            parent=self, 
            name="Conditioning",
        )
        self.load_samples = schematic.Auto(
            parent=self, 
            name="Load Samples",       
        )
        self.reaction = schematic.Auto(
            parent=self,
            name="Reaction",
        )
        self.next = Next(self)

        self.worker = schematic.Display(
            parent=self,
            name="Worker"
        )
        self.helper = schematic.Display(
            parent=self,
            name="Helper"
        )

        self.container = QGridLayout(self)
        self.container.addWidget(self.auto, 0, 0)
        self.container.addWidget(self.abort, 1, 0, alignment=Qt.AlignmentFlag.AlignTop)
        self.container.addWidget(self.conditioning, 3, 0)
        self.container.addWidget(self.load_samples, 4, 0)
        self.container.addWidget(self.reaction, 5, 0)
        self.container.addWidget(self.next, 6, 0)
        self.container.addWidget(QWidget(), 7, 0)
        self.container.addWidget(self.worker, 8, 0)
        self.container.addWidget(self.helper, 9, 0)

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
        self.sidepanel = SidePanel(self)

        self.worker = worker.Worker()
        self.helper = worker.Worker()
        self.smc_worker = worker.Worker(0.1, self.smc.get)
        self.keller_worker = worker.Worker(0.5, self.keller.get, self.schematic.get_reactor_idx())
        self.tm_worker = worker.Worker(1.0, self.tm.get, self.schematic.get_heater_idx())
        self.peltier_worker = worker.Worker(1.0)

        self.procedures = procedures.Procedures(
            self, self.tcpip, self.smc, self.keller, self.tm, self.peltier,
            self.worker, self.helper, self.table, self.schematic, self.panel
        )

        self.sidepanel.reactor_valves.btn_open.clicked.connect(lambda: self.procedures.set_reactor_valves(1))
        self.sidepanel.reactor_valves.btn_close.clicked.connect(lambda: self.procedures.set_reactor_valves(0))
        self.sidepanel.clean_trap.button.clicked.connect(lambda: self.helper.request(self.procedures.clean_trap))
        self.sidepanel.offset.button.clicked.connect(lambda: self.worker.request(self.procedures.correct_offset))

        self.panel.auto.button.clicked.connect(self.start)
        self.panel.abort.button.clicked.connect(self.stop)

        self.sidepanel.logging.reset.clicked.connect(self.reset)
        self.sidepanel.logging.save.clicked.connect(lambda: self.save(time.time()))
        self.sidepanel.logging.load.clicked.connect(self.load)
        self.sidepanel.logging.store.clicked.connect(self.table.store)

        self.sidepanel.logging.default.clicked.connect(self.graph.default)
        self.sidepanel.logging.auto.clicked.connect(self.graph.auto)
        self.sidepanel.logging.start.clicked.connect(lambda: self.graph.set_running(True))
        self.sidepanel.logging.pause.clicked.connect(lambda: self.graph.set_running(False))
        self.sidepanel.logging.start.clicked.connect(lambda: self.sidepanel.logging.set_running(True))
        self.sidepanel.logging.pause.clicked.connect(lambda: self.sidepanel.logging.set_running(False))
        
        for v in self.schematic.valves:
            v.button.clicked.connect(self.request_wrapper(v))
        self.schematic.lift.button.clicked.connect(lambda: self.smc.set([self.schematic.valve_lift.id], not self.schematic.lift.running))
        for o in self.schematic.ovens:
            o.button.clicked.connect(lambda: self.heater(o))
        self.schematic.trap.button.clicked.connect(self.heater(self.schematic.trap))
        for p in self.schematic.peltiers:
            p.button.clicked.connect(lambda: self.cooler(p))

        self.worker.message.connect(self.panel.worker.display.setText)
        self.helper.message.connect(self.panel.helper.display.setText)
        self.worker.prompt.connect(self.prompt)
        self.helper.prompt.connect(self.prompt)
        self.worker.end.connect(self.stop)
        self.helper.end.connect(self.stop)
        self.smc_worker.update.connect(self.schematic.set_valves_active)
        self.keller_worker.update.connect(self.schematic.set_reactor_values)
        self.tm_worker.update.connect(self.schematic.set_heater_values)
        self.keller_worker.update.connect(self.graph.set_stamp)
        self.smc_worker.update.connect(self.schematic.set_lift_active)

        self.worker.start()
        self.helper.start()
        self.smc_worker.start()
        self.keller_worker.start()
        self.tm_worker.start()
        self.peltier_worker.start()

        self.container = QGridLayout(self)
        self.container.addWidget(self.sidepanel, 0, 2, alignment=Qt.AlignmentFlag.AlignTop)
        self.container.addWidget(self.schematic, 0, 1)
        self.container.addWidget(self.graph, 0, 3, alignment=Qt.AlignmentFlag.AlignTop)
        self.container.addWidget(self.panel, 0, 0, alignment=Qt.AlignmentFlag.AlignTop)
        self.container.addWidget(self.table, 1, 0, 1, 3)

    def start(self):
        if not self.panel.auto.active:
            self.graph.set_running(True)
            self.panel.auto.set_active(True)
            self.panel.auto.set_running(True)
            self.sidepanel.logging.set_running(True)
            self.procedures.start()
        elif not self.panel.auto.running:
            self.panel.auto.set_running(True)
            self.sidepanel.logging.set_running(True)
        else: 
            self.panel.auto.set_running(False)
            self.sidepanel.logging.set_running(False)
        
    def reset(self):
        self.table.reset()
        self.graph.reset()

    def save(self, date):
        path = os.path.join("Records", date)
        os.makedirs(path, exist_ok=True)
        self.table.save(path)
        self.graph.save(path)

    def load(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Data Folder",
            "", 
            QFileDialog.Option.ShowDirsOnly,
        )

        if path:
            self.table.load(path)
            self.graph.load(path)

    def stop(self):
        self.worker.clear()
        self.helper.clear()

        self.schematic.stop()
        self.graph.set_running(False)

        self.smc.close_all()
        self.tm.stop([h.id for h in self.schematic.heaters])
        self.peltier.stop()

        self.panel.auto.set_active(False)
        self.panel.auto.set_running(False)

        self.panel.conditioning.reset()
        self.panel.load_samples.reset()
        self.panel.reaction.reset()

        self.sidepanel.logging.set_running(False)

        self.procedures.running = False
        self.worker.message.emit("")
        self.helper.message.emit("")

        self.panel.worker.set_running(False)
        self.panel.helper.set_running(False)

        self.panel.next.combo.setCurrentIndex(10)

    def prompt(self, message, buttons=QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel, event=None):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)

        font = QFont()
        font.setPointSize(14)
        msg_box.setFont(font)

        if event is not None:
            msg_box.setWindowTitle("Warning")
            msg_box.setText(message)
            msg_box.setStandardButtons(buttons)
            self.procedures.prompt_reply = msg_box.exec()
            event.set()
        else:
            msg_box.setWindowTitle("Error")
            msg_box.setText(message)
            msg_box.exec()

    def heater(self, heater):
        if heater.running:
            self.procedures.stop_heaters([heater])
        elif heater.active:
            self.procedures.start_heaters([heater], 500)

    def cooler(self, cooler):
        if cooler.running:
            self.procedures.set_peltiers([cooler], 0)
        elif cooler.active:
            self.procedures.set_peltiers([cooler], 1)

    def request_wrapper(self, valve):
        return lambda: self.request(valve)

    def request(self, valve):
        self.smc.set([valve.id], not valve.running)

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


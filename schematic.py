
import sys
import numpy
import time
import json
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QVBoxLayout, QLabel, QSizePolicy, QGridLayout
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtCore import Qt, QMutex, QMutexLocker

import keller, smc, tm, peltier
import worker
import procedures
import components as c

class Reactor(QFrame):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent
        self.id = id
        self.active = True 
        self.value = 0
        self.offset = 0
        self.slope = 1

        self.color = QColor.fromHslF(((self.id + 4)/12) % 1, 0.95, 0.45)
        self.title = c.Title(f"Reactor {self.id}")
        self.display = QLabel("-- mbar", alignment=Qt.AlignmentFlag.AlignRight)
        self.button = QPushButton("Deactivate")
        self.button.clicked.connect(self.toggle)

        self.container = QGridLayout(self)
        self.container.addWidget(self.title, 0, 0)
        self.container.addWidget(self.display, 1, 0)
        self.container.addWidget(self.button, 2, 0)

        self.update()

    def toggle(self):
        self.active = not self.active
        if self.active:
            self.button.setText("Deactivate")
        else: 
            self.button.setText("Activate")
        self.update()

    def update(self):
        color = self.color.name() if self.active else "black"
        self.title.setStyleSheet(f"background-color: {color};")

    def reset(self):
        self.offset = 0
        self.slope = 1

    def get_value(self):
        return self.slope*(self.value - self.offset)

    def set_value(self, val: float):
        self.value = val
        if not self.active:
            self.display.setText("")
        elif val is None:
            self.display.setText("-- mbar")
        else:
            self.display.setText(f"{int(self.get_value() * 1000)} mbar")

class Oven(QFrame):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent
        self.id = id
        self.active = True 
        self.value = 0
        self.running = False

        self.color = QColor.fromHslF(0, 0.5, 0.45)
        self.title = c.Title(f"Oven {self.id}")
        self.display = QLabel("-- °C", alignment=Qt.AlignmentFlag.AlignRight)

        self.container = QVBoxLayout(self)
        self.container.addWidget(self.title)
        self.container.addWidget(self.display)

        self.update()

    def set_active(self, active: bool):
        if self.active != active:
            self.active = active
            self.update()

    def set_running(self, running: bool):
        if self.running != running:
            self.running = running
            self.update()

    def update(self):
        if not self.active:
            color = "black"
        elif not self.running:
            color = "grey"
        else:
            color = self.color.name()
        self.title.setStyleSheet(f"background-color: {color};")

    def get_value(self):
        return self.value

    def set_value(self, val: float):
        self.value = val
        if not self.active:
            self.display.setText("")
        elif val is None:
            self.display.setText("-- °C")
        else:
            self.display.setText(f"{val} °C")

class Trap(QFrame):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent
        self.id = id
        self.value = 0
        self.running = False

        self.color = QColor.fromHslF(0, 0.5, 0.45)
        self.title = c.Title(f"Trap")
        self.display = QLabel("-- °C", alignment=Qt.AlignmentFlag.AlignRight)

        self.container = QVBoxLayout(self)
        self.container.addWidget(self.title)
        self.container.addWidget(self.display)

        self.update()

    def set_running(self, running: bool):
        if self.running != running:
            self.running = running
            self.update()

    def update(self):
        if not self.running:
            color = "grey"
        else:
            color = self.color.name()
        self.title.setStyleSheet(f"background-color: {color};")

    def get_value(self):
        return self.value

    def set_value(self, val: float):
        self.value = val
        if val is None:
            self.display.setText("-- °C")
        else:
            self.display.setText(f"{val} °C")

class Peltier(QWidget):
    def __init__(self, parent, id, nr):
        super().__init__(parent)
        self.parent = parent
        self.id = id
        self.active = True 
        self.running = False

        self.color = QColor.fromHslF(0.5, 0.5, 0.45)
        self.title = c.Title(f"Peltier {nr}")

        self.container = QVBoxLayout(self)
        self.container.addWidget(self.title)

        self.update()

    def set_active(self, active: bool):
        if self.active != active:
            self.active = active
            self.update()

    def set_running(self, running: bool):
        if self.running != running:
            self.running = running
            self.update()

    def update(self):
        if not self.active:
            color = "black"
        elif not self.running:
            color = "grey"
        else:
            color = self.color.name()
        self.title.setStyleSheet(f"background-color: {color};")

class Valve(QWidget):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent
        self.id = id
        self.active = False

        self.button = QPushButton(f"{self.id}")
        self.button.clicked.connect(self.request) # move to parent
        self.button.setFixedSize(60, 60)

        self.container = QVBoxLayout(self)
        self.container.addWidget(self.button)

        self.update()

    def set_active(self, active: bool):
        if self.active != active:
            self.active = active
            self.update()

    def update(self):
        if self.active:
            color = "black"
            bg_color = "white"
        else:
            color = "white"
            bg_color = "black"
        self.button.setStyleSheet(f"""
        QPushButton {{
            color: {color};
            background-color: {bg_color};
            border-radius: 24px;
            border: 1px solid black;
        }}
        QPushButton:hover {{
            color: white;
            background-color: grey;
        }}
        QPushButton:pressed {{
            color: white;
            background-color: grey;
        }}
        """)

    def request(self):
        if self.active:
            self.parent.smc_worker.request(self.parent.smc_device.set, [self.id], 0)
        else:
            self.parent.smc_worker.request(self.parent.smc_device.set, [self.id], 1)

class Symbol(QWidget):
    def __init__(self, parent, name):
        super().__init__(parent)
        self.parent = parent
        self.name = name

        self.title = c.Title(name)
        self.title.setStyleSheet(f"background-color: grey;")

        self.container = QVBoxLayout(self)
        self.container.addWidget(self.title)

class Schematic(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setStyleSheet(c.styleSheet)
        with open("devices_config.json", "r") as f:
            self.config = json.load(f)

        # ----- Widgets -----
        valves = self.config["Valves"]
        self.valve_reactors = [Valve(self, id) for name, id in valves.items() if "Reactor" in name]
        self.valve_lines = [Valve(self, id) for name, id in valves.items() if "Line" in name]
        self.valve_vacuum = Valve(self, valves["Vacuum"])
        self.valve_trap = Valve(self, valves["Trap"])
        self.valve_h2 = Valve(self, valves["H2"])
        self.valve_vortex = Valve(self, valves["Vortex"])
        self.valve_sampling = Valve(self, valves["Sampling"])
        self.valve_lift = Valve(self, valves["Lift"])
        self.valves = self.valve_reactors + self.valve_lines \
            + [self.valve_vacuum, self.valve_trap, self.valve_h2, self.valve_vortex, self.valve_sampling, self.valve_lift]

        self.valve_vortex.hide()
        self.valve_lift.hide()

        self.reactors = [Reactor(self, id) for _, id in self.config["Reactors"].items()]

        heaters = self.config["Heaters"]
        self.trap = Trap(self, heaters["Trap"])
        self.ovens = [Oven(self, id) for name, id in heaters.items() if "Oven" in name]
        self.heaters = [self.trap] + self.ovens

        self.peltiers = [Peltier(self, id, nr+1) for nr, (_, id) in enumerate(self.config["Coolers"].items())]

        self.h2 = Symbol(self, "H2")
        self.vacuum = Symbol(self, "Vac")
        self.ea = Symbol(self, "EA")

        # ----- Layout ------
        self.grid = QGridLayout(self)

        for i, v in enumerate(self.valve_reactors[:5]):
            self.grid.addWidget(v, 9, i + 4, alignment=Qt.AlignmentFlag.AlignCenter)
        for i, v in enumerate(self.valve_reactors[5:10]):
            self.grid.addWidget(v, 1, 8 - i, alignment=Qt.AlignmentFlag.AlignCenter) 
        self.grid.addWidget(self.valve_lines[0], 7, 4, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.valve_lines[1], 3, 4, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.valve_vacuum, 6, 4, alignment=Qt.AlignmentFlag.AlignRight)
        self.grid.addWidget(self.valve_trap, 5, 4, alignment=Qt.AlignmentFlag.AlignLeft)
        self.grid.addWidget(self.valve_h2, 4, 4, alignment=Qt.AlignmentFlag.AlignRight)
        self.grid.addWidget(self.valve_sampling, 6, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        for i, r in enumerate(self.reactors[:5]):
            self.grid.addWidget(r, 10, i + 4, alignment=Qt.AlignmentFlag.AlignCenter)
        for i, r in enumerate(self.reactors[5:]):
            self.grid.addWidget(r, 0, 8 - i, alignment=Qt.AlignmentFlag.AlignCenter)

        self.grid.addWidget(self.ovens[0], 7, 8, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.ovens[1], 3, 8, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.trap, 4, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        self.grid.addWidget(self.peltiers[0], 7, 7, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.peltiers[1], 3, 7, alignment=Qt.AlignmentFlag.AlignCenter)

        self.grid.addWidget(self.h2, 4, 5, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.vacuum, 6, 5, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.ea, 7, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # ----- Workers ------
        if self.parent is not None:
            self.smc_device = self.parent.smc_device 
            self.keller_device = self.parent.keller_device
            self.tm_device = self.parent.tm_device
            self.peltier_device = self.parent.peltier_device

            self.smc_worker = worker.Worker(0.5, self.smc_device.get)
            self.keller_worker = worker.Worker(0.1, self.keller_device.get, [r.id for r in self.reactors])
            self.tm_worker = worker.Worker(1.0, self.tm_device.get, [h.id for h in self.heaters])
            self.peltier_worker = worker.Worker(1.0)

            self.smc_worker.update.connect(self.update_valves)
            self.keller_worker.update.connect(self.update_reactors)
            self.tm_worker.update.connect(self.update_heaters) # move?

            self.smc_worker.start()
            self.keller_worker.start()
            self.tm_worker.start()
            self.peltier_worker.start()

    def update_reactors(self, values):
        for r in self.reactors:
            if r.id <= len(values):
                r.set_value(values[r.id - 1])

    def update_heaters(self, values):
        for h in self.heaters:
            if h.id <= len(values):
                h.set_value(values[h.id - 1])

    def update_valves(self, values):
        for v in self.valves:
            if v.id <= len(values):
                v.set_active(values[v.id - 1])

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor("black"), 2)
        painter.setPen(pen)

        # ----- Connecting Lines -----
        # Top and Bottom Lines
        painter.drawLine(self.grid.cellRect(2, 4).center(), self.grid.cellRect(2, 8).center())
        painter.drawLine(self.grid.cellRect(8, 4).center(), self.grid.cellRect(8, 8).center())
        for i in range(5):
            painter.drawLine(self.grid.cellRect(0, 4 + i).center(), self.grid.cellRect(2, 4 + i).center())
            painter.drawLine(self.grid.cellRect(8, 4 + i).center(), self.grid.cellRect(10, 4 + i).center())

        # Left Line
        painter.drawLine(self.grid.cellRect(2, 4).center(), self.grid.cellRect(8, 4).center())
        painter.drawLine(self.grid.cellRect(4, 4).center(), self.grid.cellRect(4, 5).center())
        painter.drawLine(self.grid.cellRect(5, 2).center(), self.grid.cellRect(5, 4).center())
        painter.drawLine(self.grid.cellRect(6, 4).center(), self.grid.cellRect(6, 5).center())

        # Trap Switch Loop
        painter.drawLine(self.grid.cellRect(4, 2).center(), self.grid.cellRect(6, 2).center())
        painter.drawLine(self.grid.cellRect(4, 0).center(), self.grid.cellRect(6, 0).center())
        painter.drawLine(self.grid.cellRect(4, 0).center(), self.grid.cellRect(4, 2).center())
        painter.drawLine(self.grid.cellRect(6, 0).center(), self.grid.cellRect(6, 2).center())
        painter.drawLine(self.grid.cellRect(6, 1).center(), self.grid.cellRect(7, 1).center())

    def stop(self):
        for h in self.heaters:
            h.set_running(False)

        for o in self.ovens:
            o.set_active(True)

        for p in self.peltiers:
            p.set_running(False)
            p.set_active(True)

    def closeEvent(self, event):
        if self.parent is not None:
            self.keller_worker.stop()
            self.tm_worker.stop()
            self.smc_worker.stop()
            self.peltier_worker.stop()

        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = Schematic(parent=None)

    window.show()
    sys.exit(app.exec())

import sys
import json
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QLabel, QGridLayout, QLineEdit
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtCore import Qt
import components as c

class Valve(QWidget):
    def __init__(self, parent=None, id: int = 0):
        super().__init__(parent)
        self.parent = parent
        self.id = id
        self.active = False

        self.button = QPushButton(f"{self.id}")
        self.button.setFixedSize(40, 40)

        self.container = QGridLayout(self)
        self.container.addWidget(self.button, 0, 0)

        self.set_color()

    def set_active(self, active: bool):
        if self.active != active:
            self.active = active
            self.set_color()

    def set_color(self):
        color = "black" if self.active else "white"
        bg_color = "white" if self.active else "black"
        self.button.setStyleSheet(f"""
        QPushButton {{
            color: {color};
            background-color: {bg_color};
            border-radius: 19px;
            border: 1px solid grey;
        }}""")

class OpenClose(QFrame):
    def __init__(self, parent = None, name: str = "Reactor Valves", text_1: str = "Open", text_2: str = "Close"):
        super().__init__(parent)
        self.parent = parent

        self.title = c.Title(name, alignment=Qt.AlignmentFlag.AlignCenter)
        self.btn_open = QPushButton(text_1)
        self.btn_close = QPushButton(text_2)

        self.container = QGridLayout(self)
        self.container.addWidget(self.title, 0, 0, 1, 2)
        self.container.addWidget(self.btn_open, 1, 0)
        self.container.addWidget(self.btn_close, 1, 1)

class Symbol(QFrame):
    def __init__(self, parent = None, name: str = "", color: str = "black", id: int = 0, nr: int = 1, **kwargs):
        super().__init__(parent, **kwargs)
        self.title = c.Title(name, alignment=Qt.AlignmentFlag.AlignCenter)
        self.color = color
        self.id = id
        self.nr = nr

        self.container = QGridLayout(self)
        self.container.addWidget(self.title, 0, 0, 1, 2)

        self.set_color()

    def set_color(self):
        self.title.setStyleSheet(f"background-color: {self.color};")

class Running:
    def __init__(self, **kwargs):
        self.running = False
        super().__init__(**kwargs)

    def set_running(self, running: bool):
        if self.running != running:
            self.running = running
            self.set_color()

    # def set_color(self):
    #     color = self.color if self.running else "black"
    #     self.title.setStyleSheet(f"background-color: {color};")

class Active:
    def __init__(self, **kwargs):
        self.active = True
        super().__init__(**kwargs)

    def set_active(self, active: bool):
        if self.active != active:
            self.active = active
            self.set_color()

    # def set_color(self):
    #     color = self.color if self.active else "grey"
    #     self.title.setStyleSheet(f"background-color: {color};")

class ActiveRunning(Active, Running):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # def set_color(self):
    #     if not self.active:
    #         color = "grey"
    #     elif not self.running:
    #         color = "black"
    #     else:
    #         color = self.color
    #     self.title.setStyleSheet(f"background-color: {color};")

class Value:
    def __init__(self, unit: str = "", **kwargs):
        self.value = 0
        super().__init__(**kwargs)

        self.display = c.Body("", alignment=Qt.AlignmentFlag.AlignRight)
        self.display.setFixedWidth(60)
        self.unit = QLabel(unit)

        self.container.addWidget(self.display, 1, 0, 1, 1)
        self.container.addWidget(self.unit, 1, 1, 1, 1)

    def get_value(self):
        return self.value

    def set_value(self, val: float):
        self.value = val
        text = str(self.get_value())
        self.display.setText(text)

class Field:
    def __init__(self, unit: str = "", value: float = 0.0, **kwargs):
        self.value = value
        super().__init__(**kwargs)

        self.edit = QLineEdit(str(self.value), alignment=Qt.AlignmentFlag.AlignRight)
        self.edit.setFixedWidth(100)
        self.unit = QLabel(unit)
        self.unit.setFixedWidth(50)

        self.container.addWidget(self.edit, 0, 2, 1, 1, Qt.AlignmentFlag.AlignRight)
        self.container.addWidget(self.unit, 0, 3, 1, 1, Qt.AlignmentFlag.AlignRight)

class Toggle(ActiveRunning):
    def __init__(self, running_txt: str = "Deactivate", active_txt: str = "Deactivate", inactive_txt: str = "Activate", **kwargs):
        super().__init__(**kwargs)
        self.running_txt = running_txt
        self.active_txt = active_txt
        self.inactive_txt = inactive_txt

        self.button = QPushButton(self.active_txt)
        self.button.clicked.connect(self.toggle)

        self.container.addWidget(self.button, 2, 0, 1, 2)

    def set_text(self):
        if not self.active:
            self.button.setText(self.inactive_txt)
        elif not self.running:
            self.button.setText(self.active_txt)
        else: 
            self.button.setText(self.running_txt)
        self.set_color()

    def toggle(self):
        self.active = not self.active
        self.set_text()

class Peltier(ActiveRunning, Symbol):
    def __init__(self, name: str = "Peltier", color: str = QColor.fromHslF(0.6, 0.95, 0.45).name(), nr: int = 1, **kwargs):
        super().__init__(name = f"{name} {nr}", color = color, nr = nr, **kwargs)

class Trap(Running, Value, Symbol):
    def __init__(self, name: str = "Trap", color: str = QColor.fromHslF(0, 0.95, 0.45).name(), unit: str = "\u00b0C", **kwargs):
        super().__init__(name = name, color = color, unit = unit, **kwargs)

class Oven(ActiveRunning, Value, Symbol):
    def __init__(self, name: str = "Oven", color: str = QColor.fromHslF(0, 0.95, 0.45).name(), nr: int = 1, unit: str = "\u00b0C", **kwargs):
        super().__init__(name = f"{name} {nr}", color = color, nr = nr, unit = unit, **kwargs)

class Reactor(Toggle, Value, Symbol):
    def __init__(self, name: str = "Reactor", color: str = "grey", id: int = 0, nr: int = 1, unit = "mbar", **kwargs):
        super().__init__(name = f"{name} {nr}", color = QColor.fromHslF(id / 10, 0.65 + ((id + 7) % 3) / 7, 0.35 + ((id + 5) % 3) / 7).name(), id = id, nr = nr, unit = unit, **kwargs)
        self.offset = 0.0
        self.slope = 1.0

        self.set_running(True)

    def set(self, offset: float = 0.0, slope: float = 1.0):
        self.offset = offset
        self.slope = slope

    def reset(self):
        self.offset = 0.0
        self.slope = 1.0

    def get_value(self):
        return self.slope*(self.value - self.offset)

    def set_value(self, val: float):
        self.value = val
        text = f"{int(self.get_value() * 1000)}"
        self.display.setText(text)

class Display(Running, Symbol):
    def __init__(self, color: str = QColor.fromHslF(0.4, 0.9, 0.3).name(), **kwargs):
        super().__init__(color=color, **kwargs)
        self.display = c.Body("")

        self.container.addWidget(self.display, 1, 0, 1, 2)

        self.set_running(False)

class Edit(Field, Symbol):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class Auto(Toggle, Symbol):
    def __init__(self, color: str = QColor.fromHslF(0.6, 0.9, 0.3).name(), **kwargs):
        super().__init__(color=color, **kwargs)

class Lift(QFrame):    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.active = False

        self.title = c.Title("Lift")
        self.button = QPushButton("Up")

        self.container = QGridLayout(self)
        self.container.addWidget(self.title, 0, 0)
        self.container.addWidget(self.button, 1, 0)

    def set_text(self):
        if self.active:
            self.button.setText("Down")
        else:
            self.button.setText("Up")

    def set_active(self, active: bool):
        if self.active != active:
            self.active = active
            self.set_text()        

class Schematic(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(1000, 1000)
        self.setStyleSheet(c.styleSheet)
        with open("devices_config.json", "r") as f:
            self.config = json.load(f)

        # ----- Widgets -----
        valves = self.config["Valves"]
        self.valve_reactors = [Valve(parent=self, id=id) for name, id in valves.items() if "Reactor" in name]
        self.valve_lines = [Valve(parent=self, id=id) for name, id in valves.items() if "Line" in name]
        self.valve_vacuum = Valve(parent=self, id=valves["Vacuum"])
        self.valve_trap = Valve(parent=self, id=valves["Trap"])
        self.valve_h2 = Valve(parent=self, id=valves["H2"])
        self.valve_vortex = Valve(parent=self, id=valves["Vortex"])
        self.valve_sampling = Valve(parent=self, id=valves["Sampling"])
        self.valve_lift = Valve(parent=self, id=valves["Lift"])
        self.valves = self.valve_reactors + self.valve_lines \
            + [self.valve_vacuum, self.valve_trap, self.valve_h2, self.valve_vortex, self.valve_sampling, self.valve_lift]

        self.valve_vortex.hide()
        self.valve_lift.hide()

        self.reactors = [Reactor(parent=self, id=id, nr=id) for _, id in self.config["Reactors"].items()]

        heaters = self.config["Heaters"]
        self.trap = Trap(parent=self, id=heaters["Trap"])
        self.ovens = [Oven(parent=self, id=id, nr=id-1) for name, id in heaters.items() if "Oven" in name]
        self.heaters = [self.trap] + self.ovens

        self.peltiers = [Peltier(parent=self, id=id, nr=nr+1) for nr, (_, id) in enumerate(self.config["Coolers"].items())]

        self.h2 = Symbol(parent=self, name="H2")
        self.vacuum = Symbol(parent=self, name="Vac")
        self.ea = Symbol(parent=self, name="EA")

        self.lift = Lift(self)

        with open("settings.json", "r") as f:
            settings = json.load(f)
        for i, data in enumerate(settings["Reactors"].values()):
            offset = data["Offset"]
            slope = data["Slope"]
            self.reactors[i].set(offset, slope)
            
        # ----- Layout ------
        self.grid = QGridLayout(self)

        for i, v in enumerate(self.valve_reactors[:5]):
            self.grid.addWidget(v, i + 2, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        for i, v in enumerate(self.valve_reactors[5:10]):
            self.grid.addWidget(v, 6 - i, 9, alignment=Qt.AlignmentFlag.AlignCenter) 
        self.grid.addWidget(self.valve_lines[0], 2, 3, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.valve_lines[1], 2, 7, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.valve_vacuum, 2, 4, alignment=Qt.AlignmentFlag.AlignBottom)
        self.grid.addWidget(self.valve_trap, 2, 5, alignment=Qt.AlignmentFlag.AlignTop)
        self.grid.addWidget(self.valve_h2, 2, 6, alignment=Qt.AlignmentFlag.AlignBottom)
        self.grid.addWidget(self.valve_sampling, 0, 5, alignment=Qt.AlignmentFlag.AlignCenter)

        for i, r in enumerate(self.reactors[:5]):
            self.grid.addWidget(r, i + 2, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        for i, r in enumerate(self.reactors[5:]):
            self.grid.addWidget(r, 6 - i, 10, alignment=Qt.AlignmentFlag.AlignCenter)

        self.grid.addWidget(self.ovens[0], 6, 4, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.ovens[1], 6, 6, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.trap, 1, 6, alignment=Qt.AlignmentFlag.AlignCenter)

        self.grid.addWidget(self.peltiers[0], 5, 4, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.peltiers[1], 5, 6, alignment=Qt.AlignmentFlag.AlignCenter)

        self.grid.addWidget(self.h2, 3, 6, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.vacuum, 3, 4, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.ea, 0, 4, alignment=Qt.AlignmentFlag.AlignCenter)

        self.grid.addWidget(self.lift, 6, 5, alignment=Qt.AlignmentFlag.AlignCenter)

    def get_reactor_idx(self):
        return [r.id for r in self.reactors]

    def get_heater_idx(self):
        return [h.id for h in self.heaters]

    def set_reactor_values(self, values):
        for r in self.reactors:
            if r.id <= len(values):
                r.set_value(values[r.id - 1])

    def set_heater_values(self, values):
        for h in self.heaters:
            if h.id <= len(values):
                h.set_value(values[h.id - 1])

    def set_valves_active(self, values):
        for v in self.valves:
            if v.id <= len(values):
                v.set_active(values[v.id - 1])

    def set_lift_active(self, values):
        self.lift.set_active(values[self.valve_lift.id - 1])

    def stop(self):
        for h in self.heaters:
            h.set_running(False)

        for o in self.ovens:
            o.set_active(True)

        for p in self.peltiers:
            p.set_running(False)
            p.set_active(True)

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor("grey"), 4)
        painter.setPen(pen)

        # Right and Left Lines
        painter.drawLine(self.grid.cellRect(2, 8).center(), self.grid.cellRect(6, 8).center())
        painter.drawLine(self.grid.cellRect(2, 2).center(), self.grid.cellRect(6, 2).center())
        for i in range(5):
            painter.drawLine(self.grid.cellRect(i + 2, 10).center(), self.grid.cellRect(i + 2, 8).center())
            painter.drawLine(self.grid.cellRect(i + 2, 2).center(), self.grid.cellRect(i + 2, 0).center())

        # Top Line
        painter.drawLine(self.grid.cellRect(2, 8).center(), self.grid.cellRect(2, 2).center())
        painter.drawLine(self.grid.cellRect(2, 6).center(), self.grid.cellRect(3, 6).center())
        painter.drawLine(self.grid.cellRect(2, 4).center(), self.grid.cellRect(3, 4).center())

        # Trap Switch Loop
        painter.drawLine(self.grid.cellRect(0, 6).center(), self.grid.cellRect(0, 4).center())
        painter.drawLine(self.grid.cellRect(1, 6).center(), self.grid.cellRect(1, 5).center())
        painter.drawLine(self.grid.cellRect(0, 6).center(), self.grid.cellRect(1, 6).center())
        painter.drawLine(self.grid.cellRect(0, 5).center(), self.grid.cellRect(2, 5).center())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Schematic(parent=None)
    window.show()
    sys.exit(app.exec())
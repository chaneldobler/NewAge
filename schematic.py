
import sys
import numpy
import time
import json
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QVBoxLayout, QLabel, QSizePolicy, QGridLayout
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtCore import Qt, QMutex, QMutexLocker

import keller, smc, tm, peltier
import worker
import procedures

class Reactor(QWidget):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent
        self.id = id
        self.active = True 
        self.value = 0
        self.offset = 0
        self.slope = 1

        # Colored Header
        self.color = QColor.fromHslF(((self.id + 4)/12) % 1, 0.95, 0.45)
        self.header = QLabel(f"Reactor {self.id}", alignment=Qt.AlignmentFlag.AlignCenter)

        # Value Display
        self.display = QLabel("-- mbar", alignment=Qt.AlignmentFlag.AlignCenter)
        self.display.setStyleSheet(f"""
            QLabel {{
                background-color: white;
                color: black;
                border: none;
                border-radius: 0px;
                font-size: 12px;
                padding: 8px 8px;
            }}
        """)

        # Toggle Button
        self.button = QPushButton("Deactivate")
        self.button.clicked.connect(self.toggle)
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-size: 12px;
                padding: 4px 4px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.header)
        self.container.addWidget(self.display)
        self.container.addWidget(self.button)
        self.container.setSpacing(0)

        self.update()

    def toggle(self):
        self.active = not self.active
        if self.active:
            self.button.setText("Deactivate")
        else: 
            self.button.setText("Activate")
        self.update()

    def update(self):
        bg_color = self.color.name() if self.active else "black"
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
            }}
        """)

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

class Oven(QWidget):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent
        self.id = id
        self.active = True 
        self.value = 0
        self.running = False

        # Colored Header
        self.color = QColor.fromHslF(0, 0.5, 0.45)
        self.header = QLabel(f"Oven {self.id}", alignment=Qt.AlignmentFlag.AlignCenter)

        # Value Display
        self.display = QLabel("-- °C", alignment=Qt.AlignmentFlag.AlignCenter)
        self.display.setStyleSheet(f"""
            QLabel {{
                background-color: white;
                color: black;
                border: none;
                border-radius: 0px;
                font-size: 12px;
                padding: 8px 8px;
            }}
        """)
        
        # Status Display
        self.status = QLabel("Heating OFF", alignment=Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(f"""
            QLabel {{
                background-color: #6c757d;
                color: white;
                border: 1px solid #6c757d;
                border-radius: 0px;
                font-size: 12px;
                padding: 4px 4px;
            }}
        """)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.header)
        self.container.addWidget(self.display)
        self.container.addWidget(self.status)
        self.container.setSpacing(0)

        self.update()

    def update(self):
        bg_color = self.color.name() if self.active else "black"
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
            }}
        """)

    def set_value(self, val: float):
        if not self.active:
            self.display.setText("")
        elif val is None:
            self.display.setText("-- °C")
        else:
            self.display.setText(f"{val} °C")
        self.value = val

    def set_active(self, active: bool):
        if self.active != active:
            self.active = active
            self.update()

    def set_running(self, running: bool):
        if self.running != running:
            if running:
                self.status.setText("Heating ON")
            else:
                self.status.setText("Heating OFF")
            self.running = running

class Trap(QWidget):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent

        # Properties
        self.id = id
        self.value = 0
        self.running = False

        # Colored Header
        self.color = QColor.fromHslF(0, 0.5, 0.45)
        self.header = QLabel(f"Trap", alignment=Qt.AlignmentFlag.AlignCenter)
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: {self.color.name()};
                color: white;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
            }}
        """)

        # Value Display
        self.display = QLabel("-- °C", alignment=Qt.AlignmentFlag.AlignCenter)
        self.display.setStyleSheet(f"""
            QLabel {{
                background-color: white;
                color: black;
                border: none;
                border-radius: 0px;
                font-size: 12px;
                padding: 8px 8px;
            }}
        """)

        # Status Display
        self.status = QLabel("Heating OFF", alignment=Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(f"""
            QLabel {{
                background-color: #6c757d;
                color: white;
                border: 1px solid #6c757d;
                border-radius: 0px;
                font-size: 12px;
                padding: 4px 4px;
            }}
        """)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.header)
        self.container.addWidget(self.display)
        self.container.addWidget(self.status)
        self.container.setSpacing(0)

    def set_value(self, val: float):
        if val is None:
            self.display.setText("-- °C")
        else:
            self.display.setText(f"{val} °C")
        self.value = val

    def set_running(self, running: bool):
        if self.running != running:
            if running:
                self.status.setText("Heating ON")
            else:
                self.status.setText("Heating OFF")
            self.running = running

class Peltier(QWidget):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent

        # Properties
        self.id = id
        self.active = True 
        self.running = False

        # Colored Header
        self.color = QColor.fromHslF(0.5, 0.5, 0.45)
        self.header = QLabel(f"Peltier {self.id}", alignment=Qt.AlignmentFlag.AlignCenter)

        # Display 
        self.status = QLabel("Cooling OFF", alignment=Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(f"""
            QLabel {{
                background-color: #6c757d;
                color: white;
                border: 1px solid #6c757d;
                border-radius: 0px;
                font-size: 12px;
                padding: 4px 4px;
            }}
        """)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.header)
        self.container.addWidget(self.status)
        self.container.setSpacing(0)

        self.update()

    def update(self):
        bg_color = self.color.name() if self.active else "black"
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
            }}
        """)

    def set_active(self, active: bool):
        if self.active != active:
            self.active = active
            self.update()

    def set_running(self, running: bool):
        if self.running != running:
            if running:
                self.status.setText("Cooling ON")
            else:
                self.status.setText("Cooling OFF")
            self.running = running
            
class Valve(QWidget):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent
        self.id = id
        self.active = False

        # Toggle Button
        self.button = QPushButton(f"{self.id}")
        self.button.setFixedSize(24, 24)

        # Button Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.button)

        self.update()

    def update(self):
        color = "white" if self.active else "black"
        self.button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: #acacac;
                border: none;
                border-radius: 12px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #5c636a;
            }}
            QPushButton:pressed {{
                background-color: #495057;
            }}
        """)

    def set_value(self, active: bool):
        if self.active != active:
            self.active = active
            self.update()

class H2(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        # Colored Header
        self.header = QLabel(f"H2", alignment=Qt.AlignmentFlag.AlignCenter)
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

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.header)

class Vacuum(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        # Colored Header
        self.header = QLabel(f"Vac", alignment=Qt.AlignmentFlag.AlignCenter)
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

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.header)

class He(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        # Colored Header
        self.header = QLabel(f"He", alignment=Qt.AlignmentFlag.AlignCenter)
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: #555555;
                color: white;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 4px;
            }}
        """)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.header)

class Schematic(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        with open("devices_config.json", "r") as f:
            self.config = json.load(f)

        # ----- Widgets -----
        # Valves
        valves = self.config["Valves"]
        self.valve_reactors = [Valve(self, id) for name, id in valves.items() if "Reactor" in name]
        self.valve_lines = [Valve(self, id) for name, id in valves.items() if "Line" in name]
        self.valve_vacuum = Valve(self, valves["Vacuum"])
        self.valve_trap = Valve(self, valves["Trap"])
        self.valve_h2 = Valve(self, valves["H2"])
        self.valve_vortex = Valve(self, valves["Vortex"])
        self.valve_he = Valve(self, valves["He"])
        self.valve_lift = Valve(self, valves["Lift"])
        self.valves = self.valve_reactors + self.valve_lines \
            + [self.valve_vacuum, self.valve_trap, self.valve_h2, self.valve_vortex, self.valve_he, self.valve_lift]

        self.valve_vortex.hide()
        self.valve_lift.hide()

        # Reactors
        self.reactors = [Reactor(self, id) for _, id in self.config["Reactors"].items()]

        # Heaters 
        heaters = self.config["Heaters"]
        self.trap = Trap(self, heaters["Trap"])
        self.ovens = [Oven(self, id) for name, id in heaters.items() if "Oven" in name]
        self.heaters = [self.trap] + self.ovens

        # Coolers
        self.peltiers = [Peltier(self, id) for _, id in self.config["Coolers"].items()]

        # Symbols
        self.h2 = H2(self)
        self.vacuum = Vacuum(self)
        self.he = He(self)

        # ----- Layout ------
        self.grid = QGridLayout(self)
        self.setContentsMargins(20, 20, 20, 20)

        # Valves
        for i, v in enumerate(self.valve_reactors[:5]):
            self.grid.addWidget(v, 9, i + 4, alignment=Qt.AlignmentFlag.AlignCenter)
        for i, v in enumerate(self.valve_reactors[5:10]):
            self.grid.addWidget(v, 1, 8 - i, alignment=Qt.AlignmentFlag.AlignCenter) 
        self.grid.addWidget(self.valve_lines[0], 7, 4, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.valve_lines[1], 3, 4, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.valve_vacuum, 6, 4, alignment=Qt.AlignmentFlag.AlignRight)
        self.grid.addWidget(self.valve_trap, 5, 4, alignment=Qt.AlignmentFlag.AlignLeft)
        self.grid.addWidget(self.valve_h2, 4, 4, alignment=Qt.AlignmentFlag.AlignRight)
        self.grid.addWidget(self.valve_he, 6, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Reactors
        for i, r in enumerate(self.reactors[:5]):
            self.grid.addWidget(r, 10, i + 4, alignment=Qt.AlignmentFlag.AlignCenter)
        for i, r in enumerate(self.reactors[5:]):
            self.grid.addWidget(r, 0, 8 - i, alignment=Qt.AlignmentFlag.AlignCenter)

        # Heaters
        self.grid.addWidget(self.ovens[0], 7, 8, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.ovens[1], 3, 8, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.trap, 4, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Coolers
        self.grid.addWidget(self.peltiers[0], 7, 7, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.peltiers[1], 3, 7, alignment=Qt.AlignmentFlag.AlignCenter)

        # Symbols
        self.grid.addWidget(self.h2, 4, 5, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.vacuum, 6, 5, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.he, 7, 1, alignment=Qt.AlignmentFlag.AlignCenter)

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

            self.smc_worker.update.connect(lambda values: self.update(self.valves, values))
            self.keller_worker.update.connect(lambda values: self.update(self.reactors, values))
            self.tm_worker.update.connect(lambda values: self.update(self.heaters, values))

            self.smc_worker.start()
            self.keller_worker.start()
            self.tm_worker.start()
            self.peltier_worker.start()

    def update(self, objects, values):
        for obj in objects:
            if obj.id <= len(values):
                obj.set_value(values[obj.id - 1])

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor("#555555"), 2)
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
        self.smc_worker.request(self.smc_device.close_all)

        for h in self.heaters:
            h.set_running(False)

        for p in self.peltiers:
            p.set_running(False)

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
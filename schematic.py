
import sys
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QVBoxLayout, QLabel, QSizePolicy, QGridLayout
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtCore import Qt

class Reactor(QWidget):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent

        # Properties
        self.id = id
        self.active = True 

        # Colored Header
        self.color = QColor.fromHslF((self.id - 1) / 10.0, 0.75, 0.45)
        self.header = QLabel(f"Reactor {self.id}", alignment=Qt.AlignmentFlag.AlignCenter)

        # Value Display
        self.display = QLabel("-- mbar", alignment=Qt.AlignmentFlag.AlignRight)

        # Toggle Button
        self.button = QPushButton("Deactivate")
        self.button.clicked.connect(self.toggle)

        # Box Frame
        self.frame = QFrame(self)
        self.frame.setStyleSheet("QFrame { background-color: #ffffff; }")
        self.frame.setFrameShape(QFrame.Shape.Box)
        self.frame.setLineWidth(2)


        # Box Content
        self.content = QVBoxLayout(self.frame)
        self.content.addWidget(self.header)
        self.content.addWidget(self.display)
        self.content.addWidget(self.button)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.frame)

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.update()

    def toggle(self):
        self.active = not self.active
        self.update()

    def update(self):
        # Header
        color = self.color.name() if self.active else "#555555"
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 4px;
            }}
        """)
        
        # Button
        text = "Deactivate" if self.active else "Activate"
        self.button.setText(text)
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

    def set_value(self, val: float):
        if not self.active:
            self.display.setText("")
        elif val is None:
            self.display.setText("-- mbar")
        else:
            p = int(val * 1000)
            self.display.setText(f"{p} mbar")

class Oven(QWidget):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent

        # Properties
        self.id = id
        self.active = True 

        # Colored Header
        self.color = QColor.fromHslF(0, 0.25, 0.45)
        self.header = QLabel(f"Oven {self.id}", alignment=Qt.AlignmentFlag.AlignCenter)

        # Value Display
        self.display = QLabel("-- °C", alignment=Qt.AlignmentFlag.AlignRight)

        # Box Frame
        self.frame = QFrame(self)
        self.frame.setStyleSheet("QFrame { background-color: #ffffff; }")
        self.frame.setFrameShape(QFrame.Shape.Box)
        self.frame.setLineWidth(2)

        # Box Content
        self.content = QVBoxLayout(self.frame)
        self.content.addWidget(self.header)
        self.content.addWidget(self.display)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.frame)

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.update()

    def update(self):
        color = self.color.name() if self.active else "#555555"
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 4px;
            }}
        """)

    def set_value(self, val: float):
        if not self.active:
            self.display.setText("")
        elif val is None:
            self.display.setText("-- °C")
        else:
            self.display.setText(f"{val} °C")

    def set_status(self, status: bool):
        if self.active != status:
            self.active = status
            self.update

class Trap(QWidget):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent

        # Properties
        self.id = id

        # Colored Header
        self.color = QColor.fromHslF(0, 0.25, 0.45)
        self.header = QLabel(f"Trap", alignment=Qt.AlignmentFlag.AlignCenter)

        # Value Display
        self.display = QLabel("-- °C", alignment=Qt.AlignmentFlag.AlignRight)

        # Box Frame
        self.frame = QFrame(self)
        self.frame.setStyleSheet("QFrame { background-color: #ffffff; }")
        self.frame.setFrameShape(QFrame.Shape.Box)
        self.frame.setLineWidth(2)

        # Box Content
        self.content = QVBoxLayout(self.frame)
        self.content.addWidget(self.header)
        self.content.addWidget(self.display)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.frame)

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: {self.color.name()};
                color: white;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 4px;
            }}
        """)

    def set_value(self, val: float):
        if val is None:
            self.display.setText("-- °C")
        else:
            self.display.setText(f"{val} °C")

class Peltier(QWidget):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent

        # Properties
        self.id = id
        self.active = True 

        # Colored Header
        self.color = QColor.fromHslF(0.5, 0.25, 0.45)
        self.header = QLabel(f"Peltier {self.id}", alignment=Qt.AlignmentFlag.AlignCenter)

        # Box Frame
        self.frame = QFrame(self)
        self.frame.setStyleSheet("QFrame { background-color: #ffffff; }")
        self.frame.setFrameShape(QFrame.Shape.Box)
        self.frame.setLineWidth(2)

        # Box Content
        self.content = QVBoxLayout(self.frame)
        self.content.addWidget(self.header)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.frame)

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.update()

    def update(self):
        color = self.color.name() if self.active else "#555555"
        self.header.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 4px;
            }}
        """)

    def set_status(self, status: bool):
        if self.active != status:
            self.active = status
            self.update

class Valve(QWidget):
    def __init__(self, parent, id, request=None):
        super().__init__(parent)
        self.parent = parent
        self.request = request

        # Properties
        self.id = id
        self.active = False

        # Toggle Button
        self.button = QPushButton(f"{self.id}")
        self.button.clicked.connect(self.request_toggle)
        self.button.setFixedSize(20, 20)

        # Button Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.button)

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.update()

    def request_toggle(self):
        if self.request is not None:
            if self.active:
                self.request("close", self.id)
            else:
                self.request("open", self.id)

    def update(self):
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

    def set_status(self, status: bool):
        if self.active != status:
            self.active = status
            self.update

class H2(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        # Colored Header
        self.header = QLabel(f"H2", alignment=Qt.AlignmentFlag.AlignCenter)

        # Box Frame
        self.frame = QFrame(self)
        self.frame.setStyleSheet("QFrame { background-color: #ffffff; }")
        self.frame.setFrameShape(QFrame.Shape.Box)
        self.frame.setLineWidth(2)

        # Box Content
        self.content = QVBoxLayout(self.frame)
        self.content.addWidget(self.header)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.frame)

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
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

class Vacuum(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        # Colored Header
        self.header = QLabel(f"Vacuum", alignment=Qt.AlignmentFlag.AlignCenter)

        # Box Frame
        self.frame = QFrame(self)
        self.frame.setStyleSheet("QFrame { background-color: #ffffff; }")
        self.frame.setFrameShape(QFrame.Shape.Box)
        self.frame.setLineWidth(2)

        # Box Content
        self.content = QVBoxLayout(self.frame)
        self.content.addWidget(self.header)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.frame)

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
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

class Switch(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        # Colored Header
        self.header = QLabel(f"Switch", alignment=Qt.AlignmentFlag.AlignCenter)

        # Box Frame
        self.frame = QFrame(self)
        self.frame.setStyleSheet("QFrame { background-color: #ffffff; }")
        self.frame.setFrameShape(QFrame.Shape.Box)
        self.frame.setLineWidth(2)

        # Box Content
        self.content = QVBoxLayout(self.frame)
        self.content.addWidget(self.header)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.frame)

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
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

class Schematic(QWidget):
    def __init__(self, parent, request=None):
        super().__init__(parent)
        self.parent = parent
        self.request = request

        # ----- Grid Layout -----

        self.grid = QGridLayout(self)

        # Reactor Line 1
        self.reactor_line_1 = [Reactor(self, i + 1) for i in range(5)]
        for i, reactor in enumerate(self.reactor_line_1):
            self.grid.addWidget(reactor, 10, i + 4, alignment=Qt.AlignmentFlag.AlignCenter)

        # Reactor Line 2
        self.reactor_line_2 = [Reactor(self, i + 6) for i in range(5)]
        for i, reactor in enumerate(self.reactor_line_2):
            self.grid.addWidget(reactor, 0, 8 - i, alignment=Qt.AlignmentFlag.AlignCenter)

        # Valve Line 1
        self.valve_line_1 = [Valve(self, i + 1) for i in range(5)]
        for i, valve in enumerate(self.valve_line_1):
            self.grid.addWidget(valve, 9, i + 4, alignment=Qt.AlignmentFlag.AlignCenter)

        # Valve Line 2
        self.valve_line_2 = [Valve(self, i + 11) for i in range(5)]
        for i, valve in enumerate(self.valve_line_2):
            self.grid.addWidget(valve, 1, i + 4, alignment=Qt.AlignmentFlag.AlignCenter)

        # Valve Gate 1
        self.valve_gate_1 = Valve(self, 6)
        self.grid.addWidget(self.valve_gate_1, 7, 4, alignment=Qt.AlignmentFlag.AlignCenter)

        # Valve Gate 2
        self.valve_gate_2 = Valve(self, 10)
        self.grid.addWidget(self.valve_gate_2, 3, 4, alignment=Qt.AlignmentFlag.AlignCenter)

        # Valve Vacuum
        self.valve_vacuum = Valve(self, 7)
        self.grid.addWidget(self.valve_vacuum, 6, 5, alignment=Qt.AlignmentFlag.AlignCenter)

        # Valve Trap
        self.valve_trap = Valve(self, 8)
        self.grid.addWidget(self.valve_trap, 5, 3, alignment=Qt.AlignmentFlag.AlignCenter)

        # Valve H2
        self.valve_h2 = Valve(self, 9)
        self.grid.addWidget(self.valve_h2, 4, 5, alignment=Qt.AlignmentFlag.AlignCenter)

        # Ovens
        self.ovens = [Oven(self, i + 1) for i in range(2)]
        self.grid.addWidget(self.ovens[0], 6, 8, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.ovens[1], 4, 8, alignment=Qt.AlignmentFlag.AlignCenter)

        # Trap
        self.trap = Trap(self, 1)
        self.grid.addWidget(self.trap, 4, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Peltiers
        self.peltiers = [Peltier(self, i + 1) for i in range(2)]
        self.grid.addWidget(self.peltiers[0], 6, 7, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid.addWidget(self.peltiers[1], 4, 7, alignment=Qt.AlignmentFlag.AlignCenter)

        # H2
        self.h2 = H2(self)
        self.grid.addWidget(self.h2, 4, 6, alignment=Qt.AlignmentFlag.AlignCenter)

        # Vacuum
        self.vacuum = Vacuum(self)
        self.grid.addWidget(self.vacuum, 6, 6, alignment=Qt.AlignmentFlag.AlignCenter)

        # Switch
        self.switch = Switch(self)
        self.grid.addWidget(self.switch, 6, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # ----- Collections -----

        # Heaters
        self.heaters = [self.trap] + self.ovens

        # Reactors
        self.reactors = self.reactor_line_1 + self.reactor_line_2

        # Valves
        self.valves = self.valve_line_1 \
            + [self.valve_gate_1, self.valve_vacuum, self.valve_trap, self.valve_h2, self.valve_gate_2] \
            + self.valve_line_2

    def get_active_reactors(self):
        return [r for r in self.reactors if r and r.active]

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
        painter.drawLine(self.grid.cellRect(4, 4).center(), self.grid.cellRect(4, 6).center())
        painter.drawLine(self.grid.cellRect(5, 2).center(), self.grid.cellRect(5, 4).center())
        painter.drawLine(self.grid.cellRect(6, 4).center(), self.grid.cellRect(6, 6).center())

        # Trap Switch Loop
        painter.drawLine(self.grid.cellRect(4, 2).center(), self.grid.cellRect(6, 2).center())
        painter.drawLine(self.grid.cellRect(4, 0).center(), self.grid.cellRect(6, 0).center())
        painter.drawLine(self.grid.cellRect(4, 0).center(), self.grid.cellRect(4, 2).center())
        painter.drawLine(self.grid.cellRect(6, 0).center(), self.grid.cellRect(6, 2).center())

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = QWidget()
    reactor = Schematic(parent=window)

    window.show()
    sys.exit(app.exec())
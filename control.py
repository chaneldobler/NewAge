import sys
import os
import json
from PySide6 import QtWidgets,QtCore
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QVBoxLayout, QLabel, QSizePolicy, QGridLayout, QHBoxLayout, QLineEdit
from PySide6.QtCore import QSize, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QPolygonF, QBrush
import pyqtgraph as pg

# Hardware & Worker Imports
import keller, smc, tm, peltier
import worker
import procedures
import schematic

# adapt to offset yes or no?

class History(QWidget):
    def __init__(self, parent, pressures):
        super().__init__(parent)
        self.parent = parent
        self.pressures = pressures

        # Properties
        self.history = [[] for _ in self.pressures]
        self.dt = 0.1
        self.time = []

        # Graph
        self.graph = pg.PlotWidget()
        self.graph.setLabel('left', 'Pressure', units='bar')
        self.graph.setLabel('bottom', 'Time', units='s') 
        self.graph.setBackground('w')
        self.graph.setYRange(0, 2)
        self.graph.addLegend()

        # Pressure Curves
        self.curves = []
        for p in self.pressures:
            pen = pg.mkPen(color=p.color, width=2)
            curve = self.graph.plot(pen=pen, name=f"R{p.id}")
            self.curves.append(curve)

        # Box Container
        self.container = QVBoxLayout(self)
        self.container.addWidget(self.graph)
        self.setContentsMargins(20, 20, 20, 20)
        self.setFixedSize(1000, 800)

    def update(self, values):
        # History
        for p in self.pressures:
            if p.id <= len(values):
                if not p.active or values[p.id - 1] is None:
                    val = float('nan')
                else: 
                    val = p.get_value()
                self.history[p.id - 1].append(val)

        # Time
        stamp = self.time[-1] + self.dt if len(self.time) > 0 else 0
        self.time.append(stamp)

        # Graph
        for i, curve in enumerate(self.curves):
            if i < len(self.history):
                curve.setData(self.time, self.history[i])

class Procedure(QWidget):
    def __init__(self, parent, name, status, configs):
        super().__init__(parent)
        self.name = name

        # Colored Header
        self.header = QLabel(name, alignment=Qt.AlignmentFlag.AlignCenter)
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
        self.header.setFixedHeight(32)

        # Configurations
        self.config = QGridLayout()
        for i, (key, data) in enumerate(configs.items()):

            cfg = QLabel(key)
            cfg.setStyleSheet(f"""
            QLabel {{
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 0px;
                font-size: 12px;
                padding: 4px 8px;
            }}
            """)

            value = QLineEdit(str(data["Value"]), alignment=Qt.AlignmentFlag.AlignRight)
            value.setStyleSheet(f"""
            QLineEdit {{
                background-color: white;
                color: black;
                border: 1px solid #6c757d;
                border-radius: 0px;
                font-size: 12px;
                padding: 4px 8px;
            }}
            """)
            value.setFixedWidth(64)
            
            unit = QLabel(data["Unit"])
            unit.setStyleSheet(f"""
            QLabel {{
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 0px;
                font-size: 12px;
                padding: 4px 8px;
            }}
            """)
        
            self.config.addWidget(cfg, i, 0)
            self.config.addWidget(value, i, 1)
            self.config.addWidget(unit, i, 2)

        # self.text = ""
        # for key, data in configs.items():
        #     value = data["Value"]
        #     unit = data["Unit"]
        #     self.text += key + " " + str(value) + unit + "\n"

        # self.config = QLabel(self.text, alignment=Qt.AlignmentFlag.AlignCenter)
        # self.config.setStyleSheet(f"""
        #     QLabel {{
        #         background-color: #6c757d;
        #         color: white;
        #         border: none;
        #         border-radius: 0px;
        #         font-size: 12px;
        #         padding: 8px 8px;
        #     }}
        # """)

        self.status = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(f"""
            QLabel {{
                background-color: #555555;
                color: white;
                border: none;
                border-radius: 0px;
                font-size: 12px;
                padding: 4px 16px;
            }}
        """)
        self.status.setFixedHeight(24)
        self.set_status(status)

        self.container = QVBoxLayout(self)
        self.container.addWidget(self.header)
        self.container.addLayout(self.config)
        self.container.addWidget(self.status)
        self.container.addWidget(QWidget())
        self.container.setSpacing(0)

    def set_status(self, status: int):
        # color = QColor.fromHslF(0.25, 0.5, 0.45).name() if status else "#555555"
        # self.header.setStyleSheet(f"""
        #     QLabel {{
        #         background-color: #555555;
        #         color: white;
        #         border: none;
        #         border-radius: 0px;
        #         font-weight: bold;
        #         font-size: 12px;
        #         padding: 8px 16px;
        #     }}
        # """)
        text = "DONE" if status else ""
        self.status.setText(text)

class Status(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        with open("procedures_config.json", "r") as f:
            self.config = json.load(f)

        self.container = QGridLayout(self)
        self.procedures = {}
        self.funcs = []
        self.i = 0

        # Procedures
        for i, name in enumerate(self.config):
            status = self.config[name]["Status"]
            configs = self.config[name]["Configurations"]
            procedure = Procedure(self, name, status, configs)
            self.container.addWidget(procedure, i // 3, i % 3)
            self.procedures[name] = procedure

        # Running Display
        self.display = QLabel("Not Currently Running", alignment=Qt.AlignmentFlag.AlignCenter)
        self.display.setStyleSheet(f"""
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
        self.container.addWidget(self.display)

        self.funcs = self.get_funcs()

        self.setContentsMargins(20, 20, 20, 20) 

    def update(self, status: int, message: str):
        if message in self.config:
            if status == 0:
                self.procedures[message].set_status(1) 
                self.config[message]["Status"] = 1

                with open("procedures_config.json", "w") as f:
                    json.dump(self.config, f, indent=2)

                self.i += 1
                if self.i < len(self.funcs):
                    self.display.setText("Currently Running " + self.funcs[self.i])
                else:
                    self.display.setText("Not Currently Running") # collapse
                    self.i = 0
                    self.parent.stop() # move update up?
            else:
                self.display.setText("Not Currently Running")
                self.i = 0
                self.parent.stop() 

    def start(self):
        with open("procedures_config.json", "r") as f:
            self.config = json.load(f)

        self.funcs = self.get_funcs()
        if self.funcs:
            self.display.setText("Currently Running " + self.funcs[0])

    def get_funcs(self):
        funcs = []
        for name in self.config:
            if self.config[name]["Status"] == 0:
                funcs.append(name)
        return funcs

class Control(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        # Devices
        self.smc_device = smc.SmcDevNet()
        self.smc_device.start()
        self.keller_device = keller.Keller()
        self.tm_device = tm.TMHardware()
        self.peltier_device = peltier.Peltier()

        # Schematic
        self.schematic = schematic.Schematic(self)

        # Graph
        self.graph = History(self, self.schematic.reactors)
        self.schematic.keller_worker.update.connect(self.graph.update)

        # Procedures 
        self.procedures = procedures.Procedures(self)

        # Status
        self.status = Status(self)
        self.procedures.procedures_worker.reply.connect(self.status.update)

        # Start Button
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-size: 16px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

        # Stop Button
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-size: 16px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

        # Reset Button
        self.reset_btn = QPushButton("Reset")
        # self.reset_btn.clicked.connect(self.stop) # TODO
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-size: 16px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

        # Container
        self.container = QVBoxLayout()
        self.container.addWidget(self.start_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        self.container.addWidget(self.stop_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        self.container.addWidget(self.reset_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Grid
        self.grid = QGridLayout(self)
        self.grid.addWidget(self.schematic, 0, 0)
        self.grid.addWidget(self.graph, 0, 1)
        self.grid.addLayout(self.container, 1, 0)
        self.grid.addWidget(self.status, 1, 1)

    def start(self):
        self.procedures.start()
        self.status.start()

        for func in self.status.funcs:
            f = getattr(self.procedures, func.lower().replace(" ", "_"))
            if f is not None:
                self.procedures.procedures_worker.request(f)

    def stop(self):
        self.schematic.stop()
        self.procedures.stop()

        self.smc_device.close_all()
        self.tm_device.stop([h.id for h in self.schematic.heaters])
        self.peltier_device.stop()

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


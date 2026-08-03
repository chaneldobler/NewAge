import sys
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QGridLayout
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
import tm_worker
import tm

class UITemperature:
    def __init__(self, parent, nr):
        self.parent = parent
        self.nr = nr

        self.btn = QPushButton(f"T{nr}\n-- °C", parent)
        self.btn.setFixedSize(QSize(80, 60))
        self.btn.setEnabled(False)

        self.btn.setStyleSheet(f"""
            QPushButton {{
                background-color: red;
                color: white;
                border: 2px solid #444444;
                border-radius: 10px;
                font-weight: bold;
            }}
            QPushButton:pressed {{
                background-color: #222222;
            }}
        """)

    def set_value(self, val: float):
        self.btn.setText(f"Oven {self.nr}\n{val:.2f} °C")

if __name__ == "__main__":
    tm_sensor = tm.TMHardware()
    worker = tm_worker.TMWorker(tm_sensor)

    app = QApplication(sys.argv)
    window = QWidget()
    temperature = UITemperature(window, 1)

    def handle_temperature_update(val: float):
        temperature.set_value(val)

    worker.temperature_update.connect(handle_temperature_update)
    worker.start()

    window.show()
    exit_code = app.exec()

    worker.stop()

    sys.exit(exit_code)
import sys
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QGridLayout
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
import keller_worker
import keller

class UIPressure:
    def __init__(self, parent, nr):
        self.parent = parent
        self.nr = nr

        self.btn = QPushButton(f"P{nr}\n-- bar", parent)
        self.btn.setFixedSize(QSize(80, 60))
        self.btn.setEnabled(False)

        hue = 0.5 + 0.5 * (nr - 1) / 10
        bg_color = QColor.fromHslF(hue, 0.75, 0.45).name()
        self.btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
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
        self.btn.setText(f"{self.nr}\n{val:.2f} bar")

if __name__ == "__main__":
    keller_sensor = keller.Keller()
    worker = keller_worker.KellerWorker(keller_sensor)

    app = QApplication(sys.argv)
    window = QWidget()
    grid = QGridLayout(window)
    pressure = UIPressure(window, grid, 1)

    def handle_pressure_update(val: float):
        pressure.set_value(val)

    worker.pressure_update.connect(handle_pressure_update)
    worker.start()

    window.show()
    exit_code = app.exec()

    worker.stop()

    sys.exit(exit_code)
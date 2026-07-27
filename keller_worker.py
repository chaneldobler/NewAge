import time
from PySide6.QtCore import QThread, Signal

class PressureWorker(QThread):
    # sends (pressure_val) back to the GUI
    pressure_updated = Signal(float)

    def __init__(self, keller, interval_sec=0.5):
        super().__init__()
        self.keller = keller
        self.interval_sec = interval_sec
        self.running = True

    def run(self):
        """Runs in a background thread."""
        while self.running:
            val = self.keller.get_pressure()
            self.pressure_updated.emit(val)
            time.sleep(self.interval_sec)

    def stop(self):
        self.running = False
        self.wait()
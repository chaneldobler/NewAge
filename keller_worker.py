import time
from PySide6.QtCore import QThread, Signal

class KellerWorker(QThread):
    # sends (pressure_val) back to the GUI
    pressure_update = Signal(float)

    def __init__(self, keller, interval_sec=1):
        super().__init__()
        self.keller = keller
        self.interval_sec = interval_sec
        self.running = True

    def run(self):
        """Runs in a background thread."""
        while self.running:
            val = self.keller.get_pressure()
            self.pressure_update.emit(val)
            time.sleep(self.interval_sec)

    def stop(self):
        self.running = False
        self.wait()
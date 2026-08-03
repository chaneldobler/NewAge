import time
from PySide6.QtCore import QThread, Signal

class TMWorker(QThread):
    # sends (temperature_values) back to the GUI
    temperature_update = Signal(list)

    def __init__(self, tm, interval_sec=1):
        super().__init__()
        self.tm = tm
        self.interval_sec = interval_sec
        self.running = True

    def run(self):
        """Runs in a background thread."""
        while self.running:
            values = self.tm.read_all()
            self.temperature_update.emit(values)
            time.sleep(self.interval_sec)

    def stop(self):
        self.running = False
        self.wait()
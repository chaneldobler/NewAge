import time
from PySide6.QtCore import QThread

# All communication to the keller device goes through the keller worker

class KellerWorker(QThread):
    def __init__(self, keller):
        super().__init__()
        self.keller = keller
        self.running = True
        self.cache = None # Store latest values

    def run(self):
        while self.running:
            # Update cache
            self.cache = self.keller.get_pressure_all()
            time.sleep(1)

    def stop(self):
        self.running = False
        self.wait()
import queue
import time
from PySide6.QtCore import QThread, Signal

class TMWorker(QThread):
    def __init__(self, tm):
        super().__init__()
        self.tm = tm
        self.cache = None # Store latest values
        self.requests = queue.Queue() # Thread-safe FIFO queue
        self.running = True

    def run(self):
        while self.running:
            # Process any pending requests 
            while not self.requests.empty():
                cmd_func, args = self.requests.get()
                cmd_func(*args)
            # Update cache
            self.cache = self.tm.get_temperature_all()

            time.sleep(1)

    def send_request(self, func, *args):
        self.requests.put((func, args))

    def stop(self):
        self.running = False
        self.wait()
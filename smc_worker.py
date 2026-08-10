import queue
import time
from PySide6.QtCore import QThread, Signal

class TMWorker(QThread):
    def __init__(self, smc):
        super().__init__()
        self.tm = smc
        self.requests = queue.Queue() # Thread-safe FIFO queue
        self.running = True

    def run(self):
        while self.running:
            # Process any pending requests 
            while not self.requests.empty():
                cmd_func, args = self.requests.get()
                cmd_func(*args)
            time.sleep(1)

    def send_request(self, func, *args):
        self.requests.put((func, args))

    def stop(self):
        self.running = False
        self.wait()
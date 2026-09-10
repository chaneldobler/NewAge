import queue
import time
from PySide6.QtCore import QThread, Signal

class Worker(QThread):
    update = Signal(list)
    
    def __init__(self, get=None, dt=0.2, idx=None):
        super().__init__()
        self.get = get
        self.idx = idx
        self.dt = dt
        self.cache = []
        self.requests = queue.Queue()
        self.running = True

    def run(self):
        while self.running:
            while not self.requests.empty():
                set, args = self.requests.get()
                set(*args)

            if self.get is not None:
                self.cache = self.get(self.idx) if self.idx is not None else self.get()
                self.update.emit(self.cache)

            time.sleep(self.dt)

    def request(self, func, *args):
        self.requests.put((func, args))

    def stop(self):
        self.running = False
        self.wait()
import queue
import time
from PySide6.QtCore import QThread, Signal

class Worker(QThread):
    update = Signal(list)
    
    def __init__(self, object, get=None, idx=None, delta_t=0.2):
        super().__init__()
        self.object = object
        self.get = get
        self.idx = idx
        self.cache = None
        self.requests = queue.Queue()
        self.running = True
        self.delta_t = delta_t

    def run(self):
        while self.running:
            # Set
            while not self.requests.empty():
                func, args = self.requests.get()
                if hasattr(self.object, func):
                    set = getattr(self.object, func)
                    set(*args)

            # Get
            if self.get is not None and hasattr(self.object, self.get):
                get = getattr(self.object, self.get)
                self.cache = get(self.idx) if self.idx is not None else get()
                self.update.emit(self.cache)

            time.sleep(self.delta_t)

    def request(self, func, *args):
        self.requests.put((func, args))

    def stop(self):
        self.running = False
        self.wait()
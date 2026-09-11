from PySide6.QtCore import QThread, Signal
import queue
import time

class Worker(QThread):
    update = Signal(list)
    reply = Signal(int, str)
    
    def __init__(self, dt=1.0, func=None, *args):
        super().__init__()
        self.running = True
        self.dt = dt
        self.func = (lambda: func(*args)) if func is not None else None
        self.requests = queue.Queue()

    def run(self):
        while self.running:
            while not self.requests.empty():
                func, args = self.requests.get()
                self.reply.emit(*func(*args))

            if self.func is not None:
                self.update.emit(self.func())

            time.sleep(self.dt)

    def request(self, func, *args):
        self.requests.put((func, args))

    def stop(self):
        self.running = False
        self.wait()
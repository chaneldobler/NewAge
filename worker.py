import queue
import time
from PySide6.QtCore import QThread, Signal

class Worker(QThread):
    update = Signal(list)
    
    def __init__(self, device, poll_method_name=None, interval=0.2):
        super().__init__()
        self.device = device
        self.poll_method_name = poll_method_name
        self.cache = None 
        self.requests = queue.Queue() # Thread-safe FIFO queue
        self.running = True
        self.interval = interval

    def run(self):
        while self.running:
            # Process any pending requests 
            while not self.requests.empty():
                method_name, args = self.requests.get()
                if hasattr(self.device, method_name):
                    method = getattr(self.device, method_name)
                    method(*args)
            
            # Update values
            if self.poll_method_name and hasattr(self.device, self.poll_method_name):
                poll_method = getattr(self.device, self.poll_method_name)
                self.cache = poll_method()
                self.update.emit(self.cache)

            time.sleep(self.interval)

    def request(self, func, *args):
        self.requests.put((func, args))

    def stop(self):
        self.running = False
        self.wait()
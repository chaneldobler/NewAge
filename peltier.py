import RPi.GPIO as GPIO
import time
from PySide6.QtCore import QMutex, QMutexLocker

class Peltier:
    def __init__(self):
        self.mutex = QMutex()
        self.idx = None

        GPIO.setmode(GPIO.BOARD)

    def set(self, idx: list[int], value: bool):
        locker = QMutexLocker(self.mutex)
        if self.idx is None:
            self.idx = idx
            for id in self.idx:
                GPIO.setup(id, GPIO.OUT)
        
        for id in idx:
            if id not in self.idx:
                GPIO.setup(id, GPIO.OUT)
                self.idx.append(id)
            GPIO.output(id, value)

    def stop(self):
        if self.idx is not None:
            self.set(self.idx, False)

import RPi.GPIO as GPIO
import time

class Peltier:
    def __init__(self, idx: list[int]):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(idx, GPIO.OUT)

    def set(self, idx: int, value: bool):
        GPIO.output(idx, GPIO.LOW)

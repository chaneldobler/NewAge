import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)       # Set numbering scheme to BCM (or GPIO.BOARD for physical pins)
GPIO.setup(15, GPIO.OUT)     # Set pin 17 as output
GPIO.setup(11, GPIO.OUT)     # Set pin 17 as output
GPIO.output(15, GPIO.LOW)    # Set LOW (0V)
GPIO.output(11, GPIO.LOW)     # Set pin 17 as output
GPIO.cleanup()               # Reset GPIO states on script completion
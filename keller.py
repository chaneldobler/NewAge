from smbus2 import SMBus, i2c_msg
import time
import json

class Keller: 
    def __init__(self):
        self.min = 0.0
        self.max = 3.0

        self.request_measurement = 0xAC
        self.address_offset = 0x4F

        self.bus = SMBus(bus=1)

    # ----- Internal -----
    def get_pressure(self, id):
        try:
            addr = id + self.address_offset
            self.bus.write_byte(i2c_addr=addr, value=self.request_measurement)

            time.sleep(0.01) # Wait >= 8ms

            msg = i2c_msg.read(address=addr, length=3)
            self.bus.i2c_rdwr(msg)
            status, p_msb, p_lsb = msg

            p = (p_msb << 8) | p_lsb 
            pressure = (p - 16384) * (self.max - self.min) / 32768 + self.min
            
            if status & 0x04: # Memory errors are indicated at bit 2
                print("Warning: Sensor memory checksum error detected.") 

            return pressure

        except Exception as e:
            return None

    # ----- External -----
    def get(self, idx):
        return [self.get_pressure(id) for id in idx]
        
if __name__ == "__main__":
    keller = Keller()
    try:
        while True:
            print(keller.get([1, 2]))
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Program terminated by user.")
    except Exception as e:
        print(f"Program stopped due to error: {e}")
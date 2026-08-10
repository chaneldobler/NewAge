from smbus2 import SMBus, i2c_msg
import time
import json

class Keller: 
    min = 0.0
    max = 3.0
    request_measurement = 0xAC

    def __init__(self):
        # read configurations
        with open("keller_config.json", "r") as f:
            self.config = json.load(f)

        # initialize
        self.bus = SMBus(bus=self.config["i2c"]["bus_number"])
        self.addresses = [int(reactor["address"], 16) for reactor in self.config["reactors"]]

    def get_pressure(self, addr=0x40):
        try:
            self.bus.write_byte(i2c_addr=addr, value=self.request_measurement)

            time.sleep(0.01) # Wait >= 8ms

            msg = i2c_msg.read(address=addr, length=3)
            self.bus.i2c_rdwr(msg)
            status, p_msb, p_lsb = msg

            p = (p_msb << 8) | p_lsb 
            pressure = (p - 16384) * (self.max - self.min) / 32768 + self.min
            
            if status & 0x04: # memory errors are indicated at bit 2
                print("Warning: Sensor memory checksum error detected.") 

            return pressure

        except Exception as e:
            return None

    def get_pressure_all(self):
        return [self.get_pressure(addr) for addr in self.addresses]
        
if __name__ == "__main__":
    keller = Keller()
    try:
        while True:
            print(keller.get_pressure_all())
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Program terminated by user.")
    except Exception as e:
        print(f"Program stopped due to error: {e}")
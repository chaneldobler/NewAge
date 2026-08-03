from smbus2 import SMBus, i2c_msg
import time

class Keller: 
    min = 0.0
    max = 3.0
    request_measurement = 0xAC

    def __init__(self, addr=0x40, bus=None):
        self.addr = addr
        self.bus = bus or SMBus(bus=1) # Fallback if bus is None

    def get_pressure(self):
        try:
            self.bus.write_byte(i2c_addr=self.addr, value=self.request_measurement)

            time.sleep(0.01) # Wait >= 8ms

            msg = i2c_msg.read(address=self.addr, length=3)
            self.bus.i2c_rdwr(msg)
            status, p_msb, p_lsb = msg

            p = (p_msb << 8) | p_lsb 
            pressure = (p - 16384) * (self.max - self.min) / 32768 + self.min
            
            if status & 0x04: # memory errors are indicated at bit 2
                print("Warning: Sensor memory checksum error detected.") 
            
            print(f"Pressure: {pressure:.4f} bar")
            return pressure

        except Exception as e:
            print(f"An error occured while reading the pressure: {e}")
            raise

class KellerCollection:
    len = 10
    bus = SMBus(bus=1) 

    def __init__(self):
        self.sensors = [Keller(addr=0x40 + i, bus=self.bus) for i in range(self.len)]

    def read_all(self):
        pressures = []
        for i in range(self.len):
            try:
                pressure = self.sensors[i].get_pressure()
                pressures.append(pressure)
            except:
                pressures.append(None)
        return pressures
        
if __name__ == "__main__":
    keller = Keller()
    try:
        while True:
            keller.get_pressure()
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Program terminated by user.")
    except Exception as e:
        print(f"Program stopped due to error: {e}")
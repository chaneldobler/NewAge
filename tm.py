import minimalmodbus
import time
import json

# deactivate channels on destruction?

# with/without error propagation?

class TMHardware:
    def __init__(self):
        # Function Codes
        self.read_coil_status = 1
        self.read_holding_registers = 3
        self.read_input_registers = 4
        self.force_single_coil = 5
        self.preset_single_register = 6 

        # Bus
        self.instrument = minimalmodbus.Instrument(
            port="/dev/ttySC0",
            slaveaddress=1
        ) 
        self.instrument.serial.baudrate = 9600

    # ----- Internal -----
    def get_temperature(self, id):
        try:
            register_value = self.instrument.read_register(
            registeraddress=0x03E8 + 6 * (id - 1),
            number_of_decimals=0, 
            functioncode=self.read_input_registers, 
            signed=True
            ) 
            return register_value
        except Exception as e:
            return None

    def set_temperature(self, id, value):
        try:
            self.instrument.write_register(
            registeraddress=0x03E8 * (id - 1),
            value=value,
            functioncode=self.preset_single_register,
            signed=True
            )
        except Exception as e:
            pass

    def get_set_temperature(self, id):
        try:
            register_value = self.instrument.read_register(
            registeraddress=0x03E8 * (id - 1),
            functioncode=self.read_holding_registers,
            signed=True
            )
            return register_value
        except Exception as e:
            pass

    def get_status(self, id): # 0:RUN, 1:STOP
        try:
            bit_value = self.instrument.read_bit(
                registeraddress=2 * (id - 1),
                functioncode=self.read_coil_status
            )
            return bit_value
        except Exception as e:
            return None

    def run(self, id):
        try:
            self.instrument.write_bit(
                registeraddress=2 * (id - 1), 
                value=0, # RUN
                functioncode=self.force_single_coil
            )
        except Exception as e:
            pass

    def halt(self, id):
        try:
            self.instrument.write_bit(
                registeraddress=2 * (id - 1),
                value=1, # STOP
                functioncode=self.force_single_coil
            )
        except Exception as e:
            pass

    # ----- External -----
    def get(self, idx):
        return [self.get_temperature(id) for id in idx]

    def set(self, idx, value):
        [self.set_temperature(id, value) for id in idx]

    def start(self, idx):
        [self.run(id) for id in idx]

    def stop(self, idx):
        [self.halt(id) for id in idx]

if __name__ == "__main__":
    tm = TMHardware()
    tm.set([2, 3], 50)
    tm.start([2, 3])
    try:
        while True:
            print(tm.get([2, 3]))
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Program terminated by user.")
    except Exception as e:
        print(f"Program stopped due to an error: {e}")
    finally:
        tm.stop([2, 3])
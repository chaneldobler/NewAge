import minimalmodbus
import time
import json

# deactivate channels on destruction?

# with/without error propagation?

class TMHardware:
    # function codes    
    read_coil_status = 1
    read_holding_registers = 3
    read_input_registers = 4
    force_single_coil = 5
    preset_single_register = 6 

    def __init__(self):
        # read config
        with open("tm_config.json", "r") as f:
            self.config = json.load(f)

        # initialize
        self.channels = [int(channel["id"]) for channel in self.config["channels"]]
        self.instrument = minimalmodbus.Instrument(
        port=self.config["instrument"]["port"],
        slaveaddress=self.config["instrument"]["address"]
        ) 
        self.instrument.serial.baudrate = self.config["instrument"]["baudrate"]

    def get_temperature(self, channel):
        try:
            register_value = self.instrument.read_register(
            registeraddress=0x03E8 + 6 * (channel - 1),
            number_of_decimals=0, 
            functioncode=self.read_input_registers, 
            signed=True
            ) 
            return register_value
        except Exception as e:
            return None

    def set_temperature(self, channel, set_value):
        try:
            self.instrument.write_register(
            registeraddress=0x03E8 * (channel - 1),
            value=set_value,
            functioncode=self.preset_single_register,
            signed=True
            )
        except Exception as e:
            pass

    def get_set_temperature(self, channel):
        try:
            register_value = self.instrument.read_register(
            registeraddress=0x03E8 * (channel - 1),
            functioncode=self.read_holding_registers,
            signed=True
            )
            return register_value
        except Exception as e:
            pass

    def get_status(self, channel): # 0:RUN, 1:STOP
        try:
            bit_value = self.instrument.read_bit(
                registeraddress=2 * (channel - 1),
                functioncode=self.read_coil_status
            )
            return bit_value
        except Exception as e:
            return None

    def run(self, channel):
        try:
            self.instrument.write_bit(
                registeraddress=2 * (channel - 1), 
                value=0, # RUN
                functioncode=self.force_single_coil
            )
        except Exception as e:
            pass

    def stop(self, channel):
        try:
            self.instrument.write_bit(
                registeraddress=2 * (channel - 1),
                value=1, # STOP
                functioncode=self.force_single_coil
            )
        except Exception as e:
            pass

    def read_all(self):
        return [self.get_temperature(i) for i in self.channels]

    def write_all(self, values):
        [self.set_temperature(i, values[i-1]) for i in self.channels]

    def run_all(self):
        [self.run(i) for i in self.channels]

    def stop_all(self):
        [self.stop(i) for i in self.channels]

if __name__ == "__main__":
    tm = TMHardware()
    tm.write_all([50, 50, 50])
    tm.run_all()
    try:
        while True:
            print(tm.read_all())
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Program terminated by user.")
    except Exception as e:
        print(f"Program stopped due to an error: {e}")
    finally:
        tm.stop_all()
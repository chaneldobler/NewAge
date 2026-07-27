import minimalmodbus
import time

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
        self.instrument = minimalmodbus.Instrument(
        port='/dev/ttySC0',
        slaveaddress=1, # Read from rotary switch
        ) 
        self.instrument.serial.baudrate = 9600

    def get_temperature(self, channel):
        try:
            register_value = self.instrument.read_register(
            registeraddress=0x03E8 + 6 * (channel - 1),
            number_of_decimals=0, 
            functioncode=self.read_input_registers, 
            signed=True
            ) 
            print(f"Temperature: {register_value} °C")
            return register_value
        except Exception as e:
            print(f"An error occurred while reading the temperature: {e}")
            raise

    def set_temperature(self, channel, set_value):
        try:
            self.instrument.write_register(
            registeraddress=0x03E8 * (channel - 1),
            value=set_value,
            functioncode=self.preset_single_register,
            signed=True
            )
        except Exception as e:
            print(f"An error occurred while writing the set temperature: {e}")
            raise

    def get_set_temperature(self, channel):
        try:
            register_value = self.instrument.read_register(
            registeraddress=0x03E8 * (channel - 1),
            functioncode=self.read_holding_registers,
            signed=True
            )
            return register_value
        except Exception as e:
            print(f"An error occurred while reading the set temperature: {e}")
            raise

    def get_status(self, channel): # 0:RUN, 1:STOP
        try:
            bit_value = self.instrument.read_bit(
                registeraddress=2 * (channel - 1),
                functioncode=self.read_coil_status
            )
            print(f"Channel {channel} has status: {bit_value}")
            return bit_value
        except Exception as e:
            print(f"An error occured while reading the status: {e}")
            raise

    def run(self, channel):
        try:
            self.instrument.write_bit(
                registeraddress=2 * (channel - 1), 
                value=0, # RUN
                functioncode=self.force_single_coil
            )
        except Exception as e:
            print(f"An error occurred while turning on: {e}")
            raise

    def stop(self, channel):
        try:
            self.instrument.write_bit(
                registeraddress=2 * (channel - 1),
                value=1, # STOP
                functioncode=self.force_single_coil
            )
        except Exception as e:
            print(f"An error occurred while turning off: {e}")
            raise

if __name__ == "__main__":
    tm = TMHardware()
    tm.run(2)
    tm.set_temperature(2, 50)
    try:
        while True:
            tm.get_temperature(2)
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Program terminated by user.")
    except Exception as e:
        print(f"Program stopped due to an error: {e}")
    finally:
        tm.stop(2)
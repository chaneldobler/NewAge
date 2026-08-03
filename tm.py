import minimalmodbus
import time

# deactivate channels on destruction?

# with/without error propagation?

class TMHardware:
    len = 3 # channels 1 to 3
    instrument = minimalmodbus.Instrument(
    port='/dev/ttySC0',
    slaveaddress=1, # read from rotary switch
    ) 
    instrument.serial.baudrate = 9600

    # function codes    
    read_coil_status = 1
    read_holding_registers = 3
    read_input_registers = 4
    force_single_coil = 5
    preset_single_register = 6 

    def get_temperature(self, channel):
        try:
            register_value = self.instrument.read_register(
            registeraddress=0x03E8 + 6 * (channel - 1),
            number_of_decimals=0, 
            functioncode=self.read_input_registers, 
            signed=True
            ) 
            print(f"Temperature for channel {channel}: {register_value} °C")
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

    def read_all(self):
        temperatures = []
        for i in range(self.len):
            try:
                temperature = self.get_temperature(i+1)
                temperatures.append(temperature)
            except:
                temperatures.append(None)
                raise
        return temperatures

    def write_all(self, values):
        for i in range(self.len):
            try:
                self.set_temperature(i+1, values[i])
            except:
                raise
    
    def run_all(self):
        for i in range(self.len):
            try:
                self.run(i+1)
            except: 
                raise

    def stop_all(self):
        for i in range(self.len):
            try:
                self.stop(i+1)
            except: 
                raise

if __name__ == "__main__":
    tm = TMHardware()
    tm.write_all([50, 50, 50])
    tm.run_all()
    try:
        while True:
            tm.read_all()
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Program terminated by user.")
    except Exception as e:
        print(f"Program stopped due to an error: {e}")
    finally:
        tm.stop_all()
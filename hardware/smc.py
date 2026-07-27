import can
import subprocess
import time

# error handling

# check vendor id and serial number

class SmcDevNet:
    def __init__(self):
        # DIP switches 3 to 4 (default 125k baud)
        self.bitrate = 125000 

        # DIP switches 5 to 10 (default 63)
        self.smc_id = 63 << 3

        self.pi_id = 0 << 3

        self.gr_2_id = 2 << 9 

        self.bus = None

    def ip_link_up(self):
        try:
            subprocess.run(['sudo', 'ip', 'link', 'set', 'can0', 'up', 'type', 'can', 'bitrate', f'{self.bitrate}'], check=True)
            time.sleep(0.5) 
            print("CAN interface is up.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to bring up CAN interface: {e}")
            raise

    def ip_link_down(self):
        try:
            subprocess.run(['sudo', 'ip', 'link', 'set', 'can0', 'down'], check=True)
            time.sleep(0.5)
            print("CAN interface is down.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to bring down CAN interface: {e}")
            raise

    # Duplicate check must be passed before going on-line
    # to prevent two modules on the same link to be assigned the same MAC ID
    def duplicate_devicenet(self): 
        # Group, Destination, Duplicate MAC ID Check Message
        id = self.gr_2_id | self.pi_id | 7

        # Physical Port Number, Vendor ID 31/7?, Serial Number 127/58?
        data = [0x00, 0x07, 0x00, 0x3A, 0x00, 0x00, 0x00]

        msg = can.Message(arbitration_id=id, data=data, is_extended_id=False)

        # Important: Message must be transmitted two consecutive times without receiving a request or response message
        for attempt in range(2):
            self.bus.send(msg)

            # Wait at least 1 second
            reply = self.bus.recv(1.0)
            if reply is not None and reply.arbitration_id == id:
                print("Duplicate DeviceNet ID detected")
                return 1
        print("No duplicate DeviceNet ID detected.")
        return 0

    def connect_devicenet(self):
        # Group, Destination, Predefined Master/Slave Connection Management Message
        id = self.gr_2_id | self.smc_id | 6

        # [Source MAC ID, Allocate Predefined Master/Slave Connection, Class ID (Message directed at DeviceNet), 
        # Instance ID (Physical attachement to DeviceNet), Allocation Choice (Polled), Allocator's MAC ID]
        data = [self.pi_id, 0x4B, 0x03, 0x01, 0x01, self.pi_id]
        
        msg = can.Message(arbitration_id=id, data=data, is_extended_id=False)
        self.bus.send(msg)
        
        reply = self.bus.recv(1.0)
        if reply is not None:
            print("DeviceNet connected.")
        else:
            print("No response received for DeviceNet connection request.")

    def disconnect_devicenet(self):
        # Group, Destination, Predefined Master/Slave Connection Management Message
        id = self.gr_2_id | self.smc_id | 6

        # Source MAC ID, Release Predefined Master/Slave Connection, Class ID (Message directed at DeviceNet), 
        # Instance ID (Physical attachement to DeviceNet), Allocation Choice (Polled)
        data = [self.pi_id, 0x4C, 0x03, 0x01, 0x01]
        
        msg = can.Message(arbitration_id=id, data=data, is_extended_id=False)
        self.bus.send(msg)
        
        reply = self.bus.recv(1.0)
        if reply is not None:
            print("DeviceNet disconnected.")
        else:
            print("No response received for DeviceNet disconnection request.")
    
    def get_status(self, channel):
        # Group, Destination, Transmit message across explicit connection
        id = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Get_Attribute_Single, Class, Instance, Attribute]
        data = [self.pi_id, 0x0E, 0x09, channel, 0x03]
        msg = can.Message(arbitration_id=id, data=data, is_extended_id=False)
        self.bus.send(msg)
        reply = self.bus.recv(1.0)
        if reply is not None:
            print(f"Channel {channel} has status: {reply.data[2]}")
            return reply.data[2]
        else: 
            print(f"No response received for channel {channel} status request.")
            return -1
        
    def get_status_all(self):
        # Group, Destination, Transmit message across explicit connection
        id = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Get_Attribute_Single, Class, Instance, Attribute]
        data = [self.pi_id, 0x0E, 0x04, 0x25, 0x03]
        msg = can.Message(arbitration_id=id, data=data, is_extended_id=False)
        self.bus.send(msg)
        reply = self.bus.recv(1.0)
        if reply is not None:
            res = int.from_bytes(reply.data[2:], byteorder="little")
            print(f"32 Solenoid Output Points Status: {res:024b}")
            return res
        else: 
            print(f"No response received for status request.")
            return -1       

    def open_valve(self, channel):
        # Group, Destination, Transmit message across explicit connection
        id = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, Value]
        data = [self.pi_id, 0x10, 0x09, channel, 0x03, 0x01]
        msg = can.Message(arbitration_id=id, data=data, is_extended_id=False)
        self.bus.send(msg)
        reply = self.bus.recv(1.0)
        if reply is not None:
            print(f"Channel {channel} activated.")
        else:
            print(f"No response received for channel {channel} activation request.")

    def open_all(self):
        # Group, Destination, Transmit message across explicit connection
        id = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, 3 Value Bytes]
        data = [self.pi_id, 0x10, 0x04, 0x25, 0x03, 0xFF, 0xFF, 0xFF]
        msg = can.Message(arbitration_id=id, data=data, is_extended_id=False)
        self.bus.send(msg)
        reply = self.bus.recv(1.0)
        if reply is not None:
            print(f"Channels activated.")
        else:
            print(f"No response received for channel activation request.")

    def close_valve(self, channel):
        # Group, Destination, Transmit message across explicit connection
        id = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, Value]
        data = [self.pi_id, 0x10, 0x09, channel, 0x03, 0x00]
        msg = can.Message(arbitration_id=id, data=data, is_extended_id=False)
        self.bus.send(msg)
        reply = self.bus.recv(1.0)
        if reply is not None:
            print(f"Channel {channel} deactivated.")
        else:
            print(f"No response received for channel {channel} deactivation request.")

    def close_all(self):
        # Group, Destination, Transmit message across explicit connection
        id = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, 3 Value Bytes]
        data = [self.pi_id, 0x10, 0x04, 0x25, 0x03, 0x00, 0x00, 0x00]
        msg = can.Message(arbitration_id=id, data=data, is_extended_id=False)
        self.bus.send(msg)
        reply = self.bus.recv(1.0)
        if reply is not None:
            print(f"Channels deactivated.")
        else:
            print(f"No response received for channel deactivation request.")

    def start(self):
        self.ip_link_down()
        self.ip_link_up()
        self.bus = can.interface.Bus(
            channel='can0', 
            interface='socketcan', 
            bitrate=self.bitrate)
        if self.duplicate_devicenet():
            print("Failed to start.")
            self.bus.shutdown()
            self.bus = None
            self.ip_link_down()
            return 0
        time.sleep(1.0)
        self.connect_devicenet()
        return 1

    def stop(self):
        self.close_all()
        self.disconnect_devicenet()
        self.bus.shutdown()
        self.bus = None
        self.ip_link_down()

# use case
if __name__ == "__main__":
    smc_devnet = SmcDevNet()
    smc_devnet.start()
    smc_devnet.open_all()
    smc_devnet.get_status_all()
    time.sleep(2.0)
    smc_devnet.stop()

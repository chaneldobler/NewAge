import can
import subprocess
import time
import json

# the connection times out pretty quickly. try to re-establish a connection if communication failed.

# check vendor id and serial number

class SmcDevNet: 
    gr_2_id = 2 << 9 
    bus = None

    def __init__(self):
        # read config
        with open("smc_config.json", "r") as f:
            self.config = json.load(f)

        # DIP switches 3 to 4 (default 125k baud)
        self.bitrate = self.config["devicenet"]["bitrate"]

        # DIP switches 5 to 10 (default 63)
        self.smc_id = self.config["devicenet"]["smc_id"] << 3

        # subject to configuration
        self.pi_id = self.config["devicenet"]["pi_id"] << 3

        # store IDs
        self.reactors = [valve["id"] for valve in self.config["valves"]["reactors"]]
        self.lines = [valve["id"] for valve in self.config["valves"]["lines"]]
        self.h2 = [valve["id"] for valve in self.config["valves"]["h2"]]
        self.vacuum = [valve["id"] for valve in self.config["valves"]["vacuum"]]
        self.trap = [valve["id"] for valve in self.config["valves"]["trap"]]

    # transform a set of indices to a bitmask
    def to_mask(self, idx):
        return list(sum(1 << (i - 1) for i in idx).to_bytes(3, byteorder='little'))

    # transform a bitmask to a set of indices
    def to_list(self, mask):
        mask_int = int.from_bytes(mask, byteorder='little')
        return [i + 1 for i in range(19) if (mask_int >> i) & 1]

    def ip_link_up(self):
        try:
            subprocess.run(['sudo', 'ip', 'link', 'set', 'can0', 'up', 'type', 'can', 'bitrate', f'{self.bitrate}'], check=True)
            time.sleep(0.1) 
        except subprocess.CalledProcessError as e:
            raise

    def ip_link_down(self):
        try:
            subprocess.run(['sudo', 'ip', 'link', 'set', 'can0', 'down'], check=True)
            time.sleep(0.1)
        except subprocess.CalledProcessError as e:
            raise

    # Duplicate check must be passed before going on-line
    # to prevent two modules on the same link to be assigned the same MAC ID
    def duplicate_check(self): 
        # Group, Destination, Duplicate MAC ID Check Message
        cid = self.gr_2_id | self.pi_id | 7

        # Physical Port Number, Vendor ID 31/7?, Serial Number 127/58?
        data = [0x00, 0x07, 0x00, 0x3A, 0x00, 0x00, 0x00]

        msg = can.Message(arbitration_id=cid, data=data, is_extended_id=False)

        # Important: Message must be transmitted two consecutive times without receiving a request or duplicate ID response message
        for attempt in range(2):
            self.bus.send(msg)

            # Wait at least 1 second
            reply = self.bus.recv(1.0)
            if reply is not None and reply.arbitration_id == cid: # check for same id
                raise RuntimeError(f"Duplicate ID detected")

    def send_message(self, id, data):
        msg = can.Message(arbitration_id=id, data=data, is_extended_id=False)
        self.bus.send(msg)
        reply = self.bus.recv(1.0)
        if reply is None:
            raise RuntimeError("No response received. Please check if a connection is established.")
        if reply.data[1] == 0x94:
            raise RuntimeError(f"An error occured. Please check service code: {hex(reply.data[2])}")
        return reply

    def connect(self):
        # Group, Destination, Predefined Master/Slave Connection Management Message
        cid = self.gr_2_id | self.smc_id | 6

        # [Source MAC ID, Allocate Predefined Master/Slave Connection, Class ID (Message directed at DeviceNet), 
        # Instance ID (Physical attachement to DeviceNet), Allocation Choice (Polled), Allocator's MAC ID]
        data = [self.pi_id, 0x4B, 0x03, 0x01, 0x01, self.pi_id]
        
        self.send_message(cid, data)

    def disconnect(self):
        # Group, Destination, Predefined Master/Slave Connection Management Message
        cid = self.gr_2_id | self.smc_id | 6

        # Source MAC ID, Release Predefined Master/Slave Connection, Class ID (Message directed at DeviceNet), 
        # Instance ID (Physical attachement to DeviceNet), Allocation Choice (Polled)
        data = [self.pi_id, 0x4C, 0x03, 0x01, 0x01]

        self.send_message(cid, data)
    
    def get_status(self, id):
        # Group, Destination, Transmit message across explicit connection
        cid = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Get_Attribute_Single, Class, Instance, Attribute]
        data = [self.pi_id, 0x0E, 0x09, id, 0x03]

        reply = self.send_message(cid, data)

        return reply.data[2]
        
    def get_status_all(self):
        # Group, Destination, Transmit message across explicit connection
        cid = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Get_Attribute_Single, Class, Instance, Attribute]
        data = [self.pi_id, 0x0E, 0x04, 0x25, 0x03]

        reply = self.send_message(cid, data)

        return self.to_list(reply.data[2:])
                 
    def open(self, id):
        # Group, Destination, Transmit message across explicit connection
        cid = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, Value]
        data = [self.pi_id, 0x10, 0x09, id, 0x03, 0x01]

        self.send_message(cid, data)

    def open_multiple(self, idx):
        # Group, Destination, Transmit message across explicit connection
        cid = self.gr_2_id | self.smc_id | 4

        # Retrieve current status, Set target bits
        current = int.from_bytes(bytes(self.get_status_all), byteorder='little')
        additional = int.from_bytes(bytes(self.to_mask(idx)), byteorder='little')
        mask = current | additional
        payload = list(mask.to_bytes(3, byteorder='little'))

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, 3 Value Bytes]
        data = [self.pi_id, 0x10, 0x04, 0x25, 0x03] + payload

        self.send_message(cid, data)

    def open_all(self):
        # Group, Destination, Transmit message across explicit connection
        cid = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, 3 Value Bytes]
        data = [self.pi_id, 0x10, 0x04, 0x25, 0x03, 0xFF, 0xFF, 0xFF]

        self.send_message(cid, data)

    def close(self, id):
        # Group, Destination, Transmit message across explicit connection
        cid = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, Value]
        data = [self.pi_id, 0x10, 0x09, id, 0x03, 0x00]

        self.send_message(cid, data)

    def close_multiple(self, idx):
        # Group, Destination, Transmit message across explicit connection
        cid = self.gr_2_id | self.smc_id | 4

        # Retrieve current status, Clear target bits
        current = int.from_bytes(bytes(self.get_status_all), byteorder='little')
        additional = int.from_bytes(bytes(self.to_mask(idx)), byteorder='little')
        mask = current & ~additional
        payload = list(mask.to_bytes(3, byteorder='little'))

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, 3 Value Bytes]
        data = [self.pi_id, 0x10, 0x04, 0x25, 0x03] + payload

        self.send_message(cid, data)

    def close_all(self):
        # Group, Destination, Transmit message across explicit connection
        cid = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, 3 Value Bytes]
        data = [self.pi_id, 0x10, 0x04, 0x25, 0x03, 0x00, 0x00, 0x00]

        self.send_message(cid, data)

    def start(self):
        try:
            self.ip_link_down()
            self.ip_link_up()
            self.bus = can.interface.Bus(
                channel='can0', 
                interface='socketcan', 
                bitrate=self.bitrate)
            self.duplicate_check()
            self.connect()
            time.sleep(1.0)
        except Exception as e:
            self.stop()
            print(e)

    def stop(self):
        try:
            self.close_all()
            self.disconnect()
            self.bus.shutdown()
            self.bus = None
            self.ip_link_down()
        except Exception as e:
            print(e)


if __name__ == "__main__":
    smc = SmcDevNet()
    smc.start()
    smc.open(19)
    time.sleep(2)
    smc.open(18)
    print(smc.get_status_all())
    time.sleep(30)
    smc.start()
    smc.stop()

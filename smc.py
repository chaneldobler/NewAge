import can
import subprocess
import time
import json
import numpy as np

# the connection times out pretty quickly. try to re-establish a connection if communication failed.

# check vendor id and serial number

class SmcDevNet: 
    gr_2_id = 2 << 9 
    bus = None

    def __init__(self):
        # DIP switches 3 to 4 (default 125k baud)
        self.bitrate = 125000

        # DIP switches 5 to 10 (default 63)
        self.smc_id = 63 << 3

        # Subject to configuration
        self.pi_id = 0 << 3

    # ----- Internal -----
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
             
    def open(self, id):
        # Group, Destination, Transmit message across explicit connection
        cid = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, Value]
        data = [self.pi_id, 0x10, 0x09, id, 0x03, 0x01]

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

    def close_all(self):
        # Group, Destination, Transmit message across explicit connection
        cid = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, 3 Value Bytes]
        data = [self.pi_id, 0x10, 0x04, 0x25, 0x03, 0x00, 0x00, 0x00]

        self.send_message(cid, data)

    # ----- External -----
    def get(self):
        # Group, Destination, Transmit message across explicit connection
        cid = self.gr_2_id | self.smc_id | 4

        # [Source MAC ID, Get_Attribute_Single, Class, Instance, Attribute]
        data = [self.pi_id, 0x0E, 0x04, 0x25, 0x03]

        reply = self.send_message(cid, data)

        return [(int.from_bytes(reply.data[2:], byteorder='little') >> i) & 1 for i in range(19)]

    def set(self, idx, value):
        # Group, Destination, Transmit message across explicit connection
        cid = self.gr_2_id | self.smc_id | 4

        status = self.get()
        for i in idx:
            if i <= len(status):
                status[i - 1] = value

        # [Source MAC ID, Set_Attribute_Single, Class, Instance, Attribute, 3 Value Bytes]
        data = [self.pi_id, 0x10, 0x04, 0x25, 0x03] + np.packbits(status, bitorder="little").tolist()

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
    time.sleep(1)
    smc.set([1,2,3,19], 1)
    print(smc.get())
    time.sleep(1)
    smc.set([1,2,3,19], 0)
    time.sleep(1)
    smc.stop()

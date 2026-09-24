import socket
import time

class TcpIp:
    def __init__(self):
        self.EA_IP = "10.236.4.193"
        self.PORT = 1984
        self.TIMEOUT = 6.0

    def send_command(self, command: str) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.TIMEOUT)
                s.connect((self.EA_IP, self.PORT))
                
                formatted_cmd = (command.strip() + "\r\n").encode('utf-8')
                s.sendall(formatted_cmd)
                
                data = s.recv(512)
                if data:
                    return data.decode('utf-8', errors='ignore').strip()
                return ""

        # TODO if reply is none 
        
        except socket.timeout:
            print(f"Timeout sending command: '{command}'")
            return ""
        except Exception as e:
            print(f"Communication Error: {e}")
            return ""

    def get_index(self) -> int:
        return self.send_command("?SINX")

    def get_name(self, index: int = 1) -> str:
        return self.send_command(f"?NAM {index}")

    def get_weight(self, index: int = 1) -> float:
        return self.send_command(f"?WGH {index}")

    def get_c(self, index: int = 1) -> float:
        return self.send_command(f"?PCT {index} C")

    def get_n(self, index: int = 1) -> float:
        return self.send_command(f"?PCT {index} N")

    def get_process_status(self) -> str:
        return self.send_command("SEQ")

    def start_processing(self) -> str:
        return self.send_command("SEQON")

    def stop_processing(self) -> str:
        return self.send_command("SEQOFF")

    def get_status(self) -> str:
        return self.send_command("?STS")

    def start(self) -> str:
        return self.send_command("STRT")

    def sleep(self) -> str:
        return self.send_command("SLEEPON")

if __name__ == "__main__":
    tcpip = TcpIp()
    # tcpip.start_processing()
    # print(tcpip.get_status())
    print(tcpip.get_process_status())
    # tcpip.sleep()

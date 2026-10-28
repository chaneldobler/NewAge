import socket
from PySide6.QtCore import QMutex, QMutexLocker

class TcpIp:
    def __init__(self, ip="10.236.4.193", port=1984, timeout=6.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.mutex = QMutex()
        self.socket = None

    def _ensure_connected(self) -> bool:
        if self.socket is not None:
            return True
    
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.ip, self.port))
            return True
        except Exception as e:
            self.socket = None
            return False

    def send_command(self, command: str) -> str:
        locker = QMutexLocker(self.mutex)
        
        if not self._ensure_connected():
            return ""

        try:
            formatted_cmd = (command.strip() + "\r\n").encode('utf-8')
            self.socket.sendall(formatted_cmd)

            data = self.socket.recv(2048)
            if data:
                return data.decode('utf-8', errors='ignore').strip()
            
            self._close_socket()
            return ""

        except socket.timeout:
            self._close_socket()
            return ""
        except Exception as e:
            self._close_socket()
            return ""

    def _close_socket(self):
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def get_status(self) -> str:
        return self.send_command("?STS")

    def get_index(self) -> str:
        return self.send_command("?SINX")

    def get_name(self, index: int) -> str:
        return self.send_command(f"?NAM {index}")

    def get_weight(self, index: int) -> str:
        return self.send_command(f"?WGH {index}")

    def get_c(self, index: int) -> float:
        return self.send_command(f"?PCT {index} C")

    def get_n(self, index: int) -> float:
        return self.send_command(f"?PCT {index} N")

    def get_process_status(self) -> str:
        return self.send_command("SEQ")

    def start_processing(self) -> str:
        return self.send_command("SEQON")

    def stop_processing(self) -> str:
        return self.send_command("SEQOFF")

    def start(self) -> str:
        return self.send_command("STRT")

    def sleep(self) -> str:
        return self.send_command("SLEEPON")

if __name__ == "__main__":
    tcpip = TcpIp()
    print(tcpip.sleep())
import socket

EA_IP = "10.236.4.222"
PORT = 1984
TIMEOUT = 3.0

def send_ea_command(command: str) -> str:
    """Sends a raw command string to the EA over TCP and returns the raw text response."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect((EA_IP, PORT))
            
            # Format command with mandatory \r\n line termination
            formatted_cmd = (command.strip() + "\r\n").encode('utf-8')
            s.sendall(formatted_cmd)
            
            # Receive response
            data = s.recv(512)
            if data:
                return data.decode('utf-8', errors='ignore').strip()
            return ""
            
    except socket.timeout:
        print(f"Timeout sending command: '{command}'")
        return ""
    except Exception as e:
        print(f"Communication Error: {e}")
        return ""

def get_sample_name(index: int = 1) -> str:
    return send_ea_command(f"?NAM {index}")

def get_sample_weight(index: int = 1) -> float:
    return send_ea_command(f"?WGH {index}")

def get_status() -> str:
    """Gets current status of the EA instrument."""
    return send_ea_command("?STS")

def start_ea() -> str:
    """Triggers the Start EA sequence."""
    return send_ea_command("STRT")

def trap_co2_on() -> str:
    """Starts CO2 trapping sequence."""
    return send_ea_command("SEQON")

def trap_co2_off() -> str:
    """Stops CO2 trapping sequence."""
    return send_ea_command("SEQOFF")

def sleep_ea() -> str:
    """Puts EA into sleep mode."""
    return send_ea_command("SLEEPON")

if __name__ == "__main__":
    print(get_sample_name(1))
    print(get_sample_weight(1))

    print(get_sample_name(2))
    print(get_sample_weight(2))

    print(get_status())
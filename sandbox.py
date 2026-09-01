import sys
import threading
from PySide6.QtCore import QCoreApplication
import smc, tm, keller, worker

def command(smc_worker, keller_worker, tm_worker, app):
    print("Enter your desired function get/set temperature/pressure/valve (id) (value).")

    while True:

        cmd = input().strip().lower().split()

        match cmd:
            case ["exit"]:
                break

            case ["get", "temperature"]:
                print(tm_worker.cache)
            case ["set", "temperature", id, value]:
                tm_worker.request("set_temperature", int(id), int(value))

            case ["get", "pressure"]:
                print(keller_worker.cache)

            case ["get", "valve"]:
                print(smc_worker.cache)
            case ["set", "valve", id, value]:
                if int(value) == 0:
                    smc_worker.request("close", int(id))
                elif int(value) == 1:
                    smc_worker.request("open", int(id))

    app.quit()

if __name__ == "__main__":
    # ----- Setup -----
    app = QCoreApplication(sys.argv)

    smc_device = smc.SmcDevNet()
    smc_device.start()
    smc_worker = worker.Worker(smc_device, "get_status_all", 1)
    smc_worker.start()

    keller_device = keller.Keller()
    keller_worker = worker.Worker(keller_device, "get_pressure_all", 1)
    keller_worker.start()

    tm_device = tm.TMHardware()
    tm_worker = worker.Worker(tm_device, "get_temperature_all", 1)
    tm_worker.start()

    client = threading.Thread(
        target=command,
        args=(smc_worker, keller_worker, tm_worker, app),
        daemon=True,
    )
    client.start()

    exit_code = app.exec()
        
    # ----- Cleanup -----
    keller_worker.stop()
    tm_worker.stop()
    smc_worker.stop()
    smc_device.stop()
    sys.exit(exit_code)
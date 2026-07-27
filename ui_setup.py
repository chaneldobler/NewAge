import sys
import PySide6.QtWidgets as QtWidgets
import ui_valve as valve
import ui_pressure as pressure
from keller_worker import PressureWorker
from keller import Keller
import smc

# object to hold 10 keller sensors

# one worker for multiple sensors

if __name__ == "__main__":
    smcdevnet = smc.SmcDevNet()
    smcdevnet.start()

    keller_sensor = Keller()
    worker = PressureWorker(keller_sensor)

    app = QtWidgets.QApplication(sys.argv)

    # Main window setup
    window = QtWidgets.QWidget()

    # Frame/Container for the valves
    grid_container = QtWidgets.QFrame(window)
    grid_layout = QtWidgets.QGridLayout(grid_container)
    grid_layout.setSpacing(10)
    
    # Outer layout to apply padding around the frame
    main_layout = QtWidgets.QVBoxLayout(window)
    main_layout.setContentsMargins(20, 20, 20, 20)
    main_layout.addWidget(grid_container)

    valves = []
    pressures = []
    for i in range(10):
        v = valve.UIValve(grid_container, grid_layout, smcdevnet, i + 1)
        valves.append(v)
        p = pressure.UIPressure(grid_container, grid_layout, i + 1)
        pressures.append(p)

    def handle_pressure_update(val: float):
        pressures[0].set_value(val)

    worker.pressure_updated.connect(handle_pressure_update)
    worker.start()

    window.show()
    exit_code = app.exec()

    worker.stop()
    smcdevnet.stop()
    sys.exit(exit_code)
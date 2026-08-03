import sys
import PySide6.QtWidgets as QtWidgets
import PySide6.QtCore as QtCore
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtCore import QPoint
import pyqtgraph as pg

import ui_valve, ui_pressure, ui_temperature
import keller_worker, keller, smc, tm_worker, tm


# =============================================================================
# 1. SCHEMATIC CANVAS FRAME
# =============================================================================
class SchematicFrame(QtWidgets.QFrame):
    def __init__(self, smcdevnet, parent=None):
        super().__init__(parent)
        self.smcdevnet = smcdevnet
        
        self.valves = []
        self.pressures = []
        self.temperatures = []
        
        self._setup_widgets()

    def _setup_widgets(self):
        """Encapsulate the creation and placement of valve/sensor UI components."""
        START_X = 120
        COL_SPACING = 90

        Y_ROW1_PRESSURE = 25   
        Y_ROW2_VALVES   = 120  
        Y_MID_V11       = 230  
        Y_MID_V12       = 410  
        Y_ROW3_VALVES   = 520  
        Y_ROW4_PRESSURE = 595  

        # 1. Row 1: Pressure Row (Top)
        for i in range(5):
            x = START_X + (i * COL_SPACING)
            p = ui_pressure.UIPressure(self, i + 1)
            p.btn.move(x, Y_ROW1_PRESSURE)
            self.pressures.append(p)

        # 2. Row 2: Valve Row (Top)
        for i in range(5):
            x = START_X + (i * COL_SPACING)
            v = ui_valve.UIValve(self, self.smcdevnet, i + 1)
            v.btn.move(x + 20, Y_ROW2_VALVES)
            self.valves.append(v)

        # 3. Middle Isolation Valves
        col1_valve_x = START_X + 20
        v11 = ui_valve.UIValve(self, self.smcdevnet, 11)
        v11.btn.move(col1_valve_x, Y_MID_V11)
        v12 = ui_valve.UIValve(self, self.smcdevnet, 12)
        v12.btn.move(col1_valve_x, Y_MID_V12)
        self.valves.extend([v11, v12])

        # Branch Valves
        v13 = ui_valve.UIValve(self, self.smcdevnet, 13)
        v13.btn.move(col1_valve_x + 90, 305 - 20)
        v14 = ui_valve.UIValve(self, self.smcdevnet, 14)
        v14.btn.move(col1_valve_x - 50, 340 - 20)
        v15 = ui_valve.UIValve(self, self.smcdevnet, 15)
        v15.btn.move(col1_valve_x + 90, 375 - 20)
        self.valves.extend([v13, v14, v15])

        # Temperature Sensors
        col5_sensor_x = START_X + (4 * COL_SPACING) + 20
        t1 = ui_temperature.UITemperature(self, 1)
        t1.btn.move(col5_sensor_x, Y_MID_V11)
        t2 = ui_temperature.UITemperature(self, 2)
        t2.btn.move(col5_sensor_x, Y_MID_V12 - 20)

        col0_sensor_x = START_X - 100
        t3 = ui_temperature.UITemperature(self, 3)
        t3.btn.move(col0_sensor_x, Y_MID_V11)
        self.temperatures.extend([t1, t2, t3])

        # Bottom Rows
        for i in range(5):
            x = START_X + (i * COL_SPACING)
            v = ui_valve.UIValve(self, self.smcdevnet, i + 6)
            v.btn.move(x + 20, Y_ROW3_VALVES)
            self.valves.append(v)

            p = ui_pressure.UIPressure(self, i + 6)
            p.btn.move(x, Y_ROW4_PRESSURE)
            self.pressures.append(p)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(0, 0, 0), 2)
        painter.setPen(pen)
        painter.setBrush(QColor(0, 0, 0))

        START_X = 120
        COL_SPACING = 90
        TOP_BUS_Y, BOT_BUS_Y = 195, 485

        for i in range(5):
            cx = START_X + (i * COL_SPACING) + 40
            painter.drawLine(QPoint(cx, 85), QPoint(cx, 120))
            painter.drawLine(QPoint(cx, 160), QPoint(cx, TOP_BUS_Y))
            if i > 0:
                painter.drawEllipse(QPoint(cx, TOP_BUS_Y), 3, 3)
                painter.drawEllipse(QPoint(cx, BOT_BUS_Y), 3, 3)
            painter.drawLine(QPoint(cx, BOT_BUS_Y), QPoint(cx, 520))
            painter.drawLine(QPoint(cx, 560), QPoint(cx, 595))

        c1_x = START_X + 40
        painter.drawLine(QPoint(c1_x, TOP_BUS_Y), QPoint(c1_x, 230))
        painter.drawLine(QPoint(c1_x, 270), QPoint(c1_x, 410))
        painter.drawLine(QPoint(c1_x, 450), QPoint(c1_x, BOT_BUS_Y))

        Y_BRANCH1, Y_BRANCH2, Y_BRANCH3 = 305, 340, 375
        RIGHT_STUB_X, LEFT_STUB_X = c1_x + 90, c1_x - 50

        painter.drawEllipse(QPoint(c1_x, Y_BRANCH1), 3, 3)
        painter.drawLine(QPoint(c1_x, Y_BRANCH1), QPoint(RIGHT_STUB_X, Y_BRANCH1))
        painter.drawLine(QPoint(c1_x, Y_BRANCH2), QPoint(LEFT_STUB_X, Y_BRANCH2))
        painter.drawEllipse(QPoint(c1_x, Y_BRANCH2), 3, 3)
        painter.drawEllipse(QPoint(c1_x, Y_BRANCH3), 3, 3)
        painter.drawLine(QPoint(c1_x, Y_BRANCH3), QPoint(RIGHT_STUB_X, Y_BRANCH3))

        c5_x = START_X + (4 * COL_SPACING) + 40
        painter.drawLine(QPoint(c1_x, TOP_BUS_Y), QPoint(c5_x, TOP_BUS_Y))
        painter.drawLine(QPoint(c1_x, BOT_BUS_Y), QPoint(c5_x, BOT_BUS_Y))


# =============================================================================
# 2. TAB 1: CONTROL VIEW
# =============================================================================
class ControlTab(QtWidgets.QWidget):
    def __init__(self, smcdevnet, parent=None):
        super().__init__(parent)
        self.smcdevnet = smcdevnet

        # Layout for Tab 1
        layout = QtWidgets.QHBoxLayout(self)

        # Schematic
        self.schematic = SchematicFrame(self.smcdevnet, self)
        self.schematic.setFixedSize(620, 660)
        layout.addWidget(self.schematic)

        # Plot Widget
        self.plot_widget = pg.PlotWidget(title="Pressure History")
        self.plot_widget.setLabel('left', 'Pressure', units='bar')
        self.plot_widget.setLabel('bottom', 'Time', units='s')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setBackground('w')
        self.plot_widget.setYRange(0, 2)
        self.curve = self.plot_widget.plot(pen=pg.mkPen(color='c', width=2))
        layout.addWidget(self.plot_widget)

    def update_pressure(self, value, data_history):
        if self.schematic.pressures:
            self.schematic.pressures[0].set_value(value)
        self.curve.setData(data_history)

    def update_temperatures(self, values):
        for i, val in enumerate(values):
            if i < len(self.schematic.temperatures):
                self.schematic.temperatures[i].set_value(val)


# =============================================================================
# 3. TAB 2: PARAMETERS / SETTINGS VIEW
# =============================================================================
class ParametersTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QFormLayout(self)

        # Example Parameter Inputs
        self.pressure_limit_spin = QtWidgets.QDoubleSpinBox()
        self.pressure_limit_spin.setRange(0.0, 10.0)
        self.pressure_limit_spin.setValue(2.0)

        self.temp_alarm_spin = QtWidgets.QDoubleSpinBox()
        self.temp_alarm_spin.setRange(-50.0, 150.0)
        self.temp_alarm_spin.setValue(80.0)

        self.save_btn = QtWidgets.QPushButton("Apply Settings")

        layout.addRow("Max Pressure Limit (bar):", self.pressure_limit_spin)
        layout.addRow("Temp Alarm Threshold (°C):", self.temp_alarm_spin)
        layout.addRow(self.save_btn)


# =============================================================================
# 4. MAIN WINDOW WITH QTABWIDGET
# =============================================================================
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, smcdevnet):
        super().__init__()
        self.setWindowTitle("Valve & Pressure Controller")
        self.resize(1420, 720)

        self.pressure_data = []

        # Central Tab Container
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create Tabs
        self.control_tab = ControlTab(smcdevnet)
        self.parameters_tab = ParametersTab()

        self.tabs.addTab(self.control_tab, "Control & Schematic")
        self.tabs.addTab(self.parameters_tab, "Parameters & Configuration")

    def handle_pressure_update(self, val: float):
        self.pressure_data.append(val)
        self.control_tab.update_pressure(val, list(self.pressure_data))

    def handle_temperature_update(self, vals: list):
        self.control_tab.update_temperatures(vals)


# =============================================================================
# 5. APPLICATION ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    smcdevnet = smc.SmcDevNet()
    smcdevnet.start()

    keller_sensor = keller.Keller()
    keller_worker = keller_worker.KellerWorker(keller_sensor)

    tm_sensor = tm.TMHardware()
    tm_worker = tm_worker.TMWorker(tm_sensor)

    app = QtWidgets.QApplication(sys.argv)

    window = MainWindow(smcdevnet)

    # Wire up signals to main window methods
    keller_worker.pressure_update.connect(window.handle_pressure_update)
    keller_worker.start()

    tm_worker.temperature_update.connect(window.handle_temperature_update)
    tm_worker.start()

    window.show()
    exit_code = app.exec()

    # Cleanup
    keller_worker.stop()
    tm_worker.stop()
    smcdevnet.stop()
    sys.exit(exit_code)
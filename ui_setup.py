import sys
import PySide6.QtWidgets as QtWidgets
import PySide6.QtCore as QtCore
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtCore import QPoint
import pyqtgraph as pg

import ui_valve, ui_pressure, ui_temperature
import keller_worker, keller, smc, tm_worker, tm

class SchematicFrame(QtWidgets.QFrame):
    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(0, 0, 0), 2)
        painter.setPen(pen)
        painter.setBrush(QColor(0, 0, 0))

        # Horizontal alignment (Shifted to 120 to leave space for T3 on the left)
        START_X = 120
        COL_SPACING = 90

        # Bus Y Positions
        TOP_BUS_Y = 195
        BOT_BUS_Y = 485

        # --- Draw Vertical Lines for Columns 1..5 ---
        for i in range(5):
            cx = START_X + (i * COL_SPACING) + 40  # Center X of each column

            # Row 1 (Pressure) down to Row 2 (Valve): 35px line (85 -> 120)
            painter.drawLine(QPoint(cx, 85), QPoint(cx, 120))

            # Row 2 (Valve) down to Top Bus: 35px line (160 -> 195)
            painter.drawLine(QPoint(cx, 160), QPoint(cx, TOP_BUS_Y))
            
            # Junction dots for columns 2..5
            if i > 0:
                painter.drawEllipse(QPoint(cx, TOP_BUS_Y), 3, 3)
                painter.drawEllipse(QPoint(cx, BOT_BUS_Y), 3, 3)

            # Bottom Bus down to Row 3 (Valve): 35px line (485 -> 520)
            painter.drawLine(QPoint(cx, BOT_BUS_Y), QPoint(cx, 520))

            # Row 3 (Valve) down to Row 4 (Pressure): 35px line (560 -> 595)
            painter.drawLine(QPoint(cx, 560), QPoint(cx, 595))

        # --- Draw Straight Vertical Connection through V11 and V12 (Column 1) ---
        c1_x = START_X + 40
        
        # Top Bus into V11: 35px line (195 -> 230)
        painter.drawLine(QPoint(c1_x, TOP_BUS_Y), QPoint(c1_x, 230))
        
        # Open center line between V11 (bottom at 270) and V12 (top at 410)
        painter.drawLine(QPoint(c1_x, 270), QPoint(c1_x, 410))
        
        # V12 out into Bottom Bus: 35px line (450 -> 485)
        painter.drawLine(QPoint(c1_x, 450), QPoint(c1_x, BOT_BUS_Y))

        # --- Draw 3 Branch Lines & Junction Dots Between V11 and V12 ---
        Y_BRANCH1 = 305  # Right
        Y_BRANCH2 = 340  # Left
        Y_BRANCH3 = 375  # Right

        RIGHT_STUB_X = c1_x + 90
        LEFT_STUB_X  = c1_x - 50

        # Branch 1 (Right)
        painter.drawEllipse(QPoint(c1_x, Y_BRANCH1), 3, 3)
        painter.drawLine(QPoint(c1_x, Y_BRANCH1), QPoint(RIGHT_STUB_X, Y_BRANCH1))

        # Branch 2 (Left)
        painter.drawLine(QPoint(c1_x, Y_BRANCH2), QPoint(LEFT_STUB_X, Y_BRANCH2))
        painter.drawEllipse(QPoint(c1_x, Y_BRANCH2), 3, 3)

        # Branch 3 (Right)
        painter.drawEllipse(QPoint(c1_x, Y_BRANCH3), 3, 3)
        painter.drawLine(QPoint(c1_x, Y_BRANCH3), QPoint(RIGHT_STUB_X, Y_BRANCH3))

        # --- Draw Top and Bottom Horizontal Bus Lines ---
        c5_x = START_X + (4 * COL_SPACING) + 40

        painter.drawLine(QPoint(c1_x, TOP_BUS_Y), QPoint(c5_x, TOP_BUS_Y))
        painter.drawLine(QPoint(c1_x, BOT_BUS_Y), QPoint(c5_x, BOT_BUS_Y))


if __name__ == "__main__":
    smcdevnet = smc.SmcDevNet()
    smcdevnet.start()

    keller_sensor = keller.Keller()
    keller_worker = keller_worker.KellerWorker(keller_sensor)

    tm_sensor = tm.TMHardware()
    tm_worker = tm_worker.TMWorker(tm_sensor)

    app = QtWidgets.QApplication(sys.argv)

    # Main Window Setup (Widened window to 1400px to fit everything comfortably)
    window = QtWidgets.QWidget()
    window.setWindowTitle("Valve & Pressure Controller")
    window.setFixedSize(1400, 700) 

    # Expanded frame width to 620px for left-side sensor clearance
    grid_container = SchematicFrame(window)
    grid_container.setGeometry(20, 20, 620, 660)

    # Data Graph on the Right (Shifted to X=660)
    plot_widget = pg.PlotWidget(window, title="Pressure History")
    plot_widget.setGeometry(660, 20, 720, 660)
    plot_widget.setLabel('left', 'Pressure', units='bar')
    plot_widget.setLabel('bottom', 'Time', units='s')
    plot_widget.showGrid(x=True, y=True)
    plot_widget.setBackground('w')
    plot_widget.setYRange(0, 2)
    curve = plot_widget.plot(pen=pg.mkPen(color='c', width=2))

    valves = []
    pressures = []
    temperatures = []

    # --- Vertical Stacking Coordinates ---
    Y_ROW1_PRESSURE = 25   
    Y_ROW2_VALVES   = 120  
    
    Y_MID_V11       = 230  
    Y_MID_V12       = 410  
    
    Y_ROW3_VALVES   = 520  
    Y_ROW4_PRESSURE = 595  

    START_X = 120  # Shifted right to accommodate left temperature button (T3)
    COL_SPACING = 90

    # 1. Row 1: Pressure Row (Top)
    for i in range(5):
        x = START_X + (i * COL_SPACING)
        p = ui_pressure.UIPressure(grid_container, i + 1)
        p.btn.move(x, Y_ROW1_PRESSURE)
        pressures.append(p)

    # 2. Row 2: Valve Row (Top)
    for i in range(5):
        x = START_X + (i * COL_SPACING)
        v = ui_valve.UIValve(grid_container, smcdevnet, i + 1)
        v.btn.move(x + 20, Y_ROW2_VALVES)
        valves.append(v)

    # 3. Middle Isolation Valves (Column 1)
    col1_valve_x = START_X + 20  # X = 140

    v11 = ui_valve.UIValve(grid_container, smcdevnet, 11)
    v11.btn.move(col1_valve_x, Y_MID_V11)
    valves.append(v11)

    v12 = ui_valve.UIValve(grid_container, smcdevnet, 12)
    v12.btn.move(col1_valve_x, Y_MID_V12)
    valves.append(v12)

    # --- 3.1 Middle Branch Valves ---
    v13 = ui_valve.UIValve(grid_container, smcdevnet, 13)
    v13.btn.move(col1_valve_x + 90, 305 - 20)  # Right branch 1

    v14 = ui_valve.UIValve(grid_container, smcdevnet, 14)
    v14.btn.move(col1_valve_x - 50, 340 - 20)  # Left branch

    v15 = ui_valve.UIValve(grid_container, smcdevnet, 15)
    v15.btn.move(col1_valve_x + 90, 375 - 20)  # Right branch 2

    valves.extend([v13, v14, v15])

    # --- 3.5 Temperature Sensors ---
    # Right-side Temperature Sensors (Column 5)
    col5_sensor_x = START_X + (4 * COL_SPACING) + 20  # X = 500

    t1 = ui_temperature.UITemperature(grid_container, 1)
    t1.btn.move(col5_sensor_x, Y_MID_V11)  # Strictly at Y = 230
    temperatures.append(t1)

    t2 = ui_temperature.UITemperature(grid_container, 2)
    t2.btn.move(col5_sensor_x, Y_MID_V12-20)  # Strictly at Y = 410
    temperatures.append(t2)

    # Left-side Temperature Sensor (T3)
    col0_sensor_x = START_X - 100  # X = 20

    t3 = ui_temperature.UITemperature(grid_container, 3)
    t3.btn.move(col0_sensor_x, Y_MID_V11)  # Strictly at Y = 230
    temperatures.append(t3)

    # 4. Row 3: Valve Row (Bottom)
    for i in range(5):
        x = START_X + (i * COL_SPACING)
        v = ui_valve.UIValve(grid_container, smcdevnet, i + 6)
        v.btn.move(x + 20, Y_ROW3_VALVES)
        valves.append(v)

    # 5. Row 4: Pressure Row (Bottom)
    for i in range(5):
        x = START_X + (i * COL_SPACING)
        p = ui_pressure.UIPressure(grid_container, i + 6)
        p.btn.move(x, Y_ROW4_PRESSURE)
        pressures.append(p)

    # Sensor updates
    pressure_data = []
    def handle_pressure_update(val: float):
        pressures[0].set_value(val)
        pressure_data.append(val)
        curve.setData(list(pressure_data))

    def handle_temperature_update(vals: list):
        if len(vals) >= 1: temperatures[0].set_value(vals[0])
        if len(vals) >= 2: temperatures[1].set_value(vals[1])
        if len(vals) >= 3: temperatures[2].set_value(vals[2])

    keller_worker.pressure_update.connect(handle_pressure_update)
    keller_worker.start()

    tm_worker.temperature_update.connect(handle_temperature_update)
    tm_worker.start()

    window.show()
    exit_code = app.exec()

    keller_worker.stop()
    tm_worker.stop()
    smcdevnet.stop()
    sys.exit(exit_code)
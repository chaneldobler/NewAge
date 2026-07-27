import sys
import PySide6.QtWidgets as QtWidgets
import PySide6.QtCore as QtCore
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtCore import QPoint
import pyqtgraph as pg

import ui_valve, ui_pressure
import keller_worker, keller, smc

class SchematicFrame(QtWidgets.QFrame):
    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(0, 0, 0), 2)
        painter.setPen(pen)
        painter.setBrush(QColor(0, 0, 0))

        # Horizontal alignment
        START_X = 20
        COL_SPACING = 90

        # Uniform vertical line length: 35px across all segments
        TOP_BUS_Y = 195
        BOT_BUS_Y = 405

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

            # Bottom Bus down to Row 3 (Valve): 35px line (405 -> 440)
            painter.drawLine(QPoint(cx, BOT_BUS_Y), QPoint(cx, 440))

            # Row 3 (Valve) down to Row 4 (Pressure): 35px line (480 -> 515)
            painter.drawLine(QPoint(cx, 480), QPoint(cx, 515))

        # --- Draw Straight Vertical Connection through V11 and V12 (Column 1) ---
        c1_x = START_X + 40
        
        # Top Bus into V11: 35px line (195 -> 230)
        painter.drawLine(QPoint(c1_x, TOP_BUS_Y), QPoint(c1_x, 230))
        
        # Open center line between V11 and V12
        painter.drawLine(QPoint(c1_x, 270), QPoint(c1_x, 330))
        
        # V12 out into Bottom Bus: 35px line (370 -> 405)
        painter.drawLine(QPoint(c1_x, 370), QPoint(c1_x, BOT_BUS_Y))

        # --- Draw Top and Bottom Horizontal Bus Lines ---
        c5_x = START_X + (4 * COL_SPACING) + 40

        painter.drawLine(QPoint(c1_x, TOP_BUS_Y), QPoint(c5_x, TOP_BUS_Y))
        painter.drawLine(QPoint(c1_x, BOT_BUS_Y), QPoint(c5_x, BOT_BUS_Y))


if __name__ == "__main__":
    smcdevnet = smc.SmcDevNet()
    smcdevnet.start()

    keller_sensor = keller.Keller()
    worker = keller_worker.KellerWorker(keller_sensor)

    app = QtWidgets.QApplication(sys.argv)

    # Main Window Setup
    window = QtWidgets.QWidget()
    window.setWindowTitle("Valve & Pressure Controller")
    window.setFixedSize(1300, 620) 

    grid_container = SchematicFrame(window)
    grid_container.setGeometry(20, 20, 520, 580)

    # Data Graph on the Right
    plot_widget = pg.PlotWidget(window, title="Pressure History")
    plot_widget.setGeometry(560, 20, 720, 580)
    plot_widget.setLabel('left', 'Pressure', units='bar')
    plot_widget.setLabel('bottom', 'Time', units='s')
    plot_widget.showGrid(x=True, y=True)
    plot_widget.setBackground('w')
    plot_widget.setYRange(0, 2)
    curve = plot_widget.plot(pen=pg.mkPen(color='c', width=2))

    valves = []
    pressures = []

    # --- Vertical Stacking Coordinates (Symmetric 35px gaps) ---
    Y_ROW1_PRESSURE = 25   # Row 1: Top Pressure Sensors (Height: 60px -> 25 to 85)
    Y_ROW2_VALVES   = 120  # Row 2: Top Valves (Height: 40px -> 120 to 160)
    
    Y_MID_V11       = 230  # Isolation Valve 11 (Height: 40px -> 230 to 270)
    Y_MID_V12       = 330  # Isolation Valve 12 (Height: 40px -> 330 to 370)
    
    Y_ROW3_VALVES   = 440  # Row 3: Bottom Valves (Height: 40px -> 440 to 480)
    Y_ROW4_PRESSURE = 515  # Row 4: Bottom Pressure Sensors (Height: 60px -> 515 to 575)

    START_X = 20
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
    col1_valve_x = START_X + 20

    v11 = ui_valve.UIValve(grid_container, smcdevnet, 11)
    v11.btn.move(col1_valve_x, Y_MID_V11)
    valves.append(v11)

    v12 = ui_valve.UIValve(grid_container, smcdevnet, 12)
    v12.btn.move(col1_valve_x, Y_MID_V12)
    valves.append(v12)

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

    worker.pressure_update.connect(handle_pressure_update)
    worker.start()

    window.show()
    exit_code = app.exec()

    worker.stop()
    smcdevnet.stop()
    sys.exit(exit_code)
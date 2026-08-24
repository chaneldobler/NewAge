import sys
import os
import json
from PySide6 import QtWidgets,QtCore
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame
from PySide6.QtCore import QSize, QPoint
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath
import pyqtgraph as pg

# Hardware & Worker Imports
import keller, smc, tm
import worker
import procedures


# =============================================================================
# 1. UI COMPONENTS
# =============================================================================
class UIPressure(QWidget):
    def __init__(self, parent, nr, toggle_cb=None):
        super().__init__(parent)
        self.parent = parent
        self.nr = nr # id
        self.is_on = True # holds status
        self.toggle_cb = toggle_cb # connects pressure display to toggle button

        # coloring from range
        hue = ((nr - 1) / 10) % 1.0
        self.color = QColor.fromHslF(hue, 0.75, 0.45)

        # layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # display
        self.display = QtWidgets.QLabel(f"Reactor {nr}\n-- bar")
        self.display.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.display.setFixedSize(86, 56)

        # toggle button 
        self.toggle_btn = QPushButton("ON")
        self.toggle_btn.setFixedSize(86, 22)
        self.toggle_btn.clicked.connect(self.toggle)

        # add to layout
        layout.addWidget(self.display)
        layout.addWidget(self.toggle_btn)
        self.setFixedSize(86, 80)

        self._apply_style()

    def toggle(self):
        self.is_on = not self.is_on
        self._apply_style()
        if self.toggle_cb:
            self.toggle_cb(self.nr, self.is_on)

    def _apply_style(self):
        display_bg = self.color.name() if self.is_on else "#555555"
        
        btn_bg = "#ffffff" if self.is_on else "#666666"
        btn_fg = "#000000" if self.is_on else "#ffffff"
        btn_pressed = "#e0e0e0" if self.is_on else "#444444"
        btn_text = "ON" if self.is_on else "OFF"

        self.display.setStyleSheet(f"""
            QLabel {{
                background-color: {display_bg};
                color: white;
                border: 2px solid #444444;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }}
        """)
        
        self.toggle_btn.setText(btn_text)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {btn_fg};
                border: 1px solid #444444;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:pressed {{
                background-color: {btn_pressed};
            }}
        """)

    def set_value(self, val: float):
        if not self.is_on:
            self.display.setText(f"Reactor {self.nr}\nOFF")
        elif val is None:
            self.display.setText(f"Reactor {self.nr}\n-- bar")
        else:
            self.display.setText(f"Reactor {self.nr}\n{val:.4f} bar")

class UITemperature:
    def __init__(self, parent, nr, label=None):
        self.parent = parent
        self.nr = nr # id
        self.label = label

        self.btn = QPushButton(f"{self.label}\n-- °C", parent)
        self.btn.setFixedSize(QSize(80, 42))
        self.btn.setEnabled(False)

        self.btn.setStyleSheet("""
            QPushButton {
                background-color: red;
                color: white;
                border: 2px solid #444444;
                border-radius: 10px;
                font-weight: bold;
            }
        """)

    def set_value(self, val: float):
        if val is None:
            self.btn.setText(f"{self.label}\n-- °C")
        else:
            self.btn.setText(f"{self.label}\n{val:.2f} °C")

class UIValve:
    def __init__(self, parent, nr, request_cb):
        self.parent = parent
        self.nr = nr # id
        self.status = 0 # closed/open
        self.request_cb = request_cb # connects toggle button to device

        # toggle button
        self.btn = QPushButton(f"{self.nr}", parent)
        self.btn.setFixedSize(QSize(40, 40))
        self.btn.clicked.connect(self.request_toggle)

        self._apply_closed_style()

    # requests worker to open/ close valve
    def request_toggle(self):
        if self.status == 0:
            self.request_cb("open", self.nr)
        else:
            self.request_cb("close", self.nr)

    # signal from worker when valve was opened/ closed
    def set_status(self, current_status):
        if self.status == current_status:
            return  
        self.status = current_status
        if self.status == 0:
            self._apply_closed_style()
        else:
            self._apply_open_style()

    def _apply_closed_style(self):
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: black;
                color: white;
                border: 2px solid #444444;
                border-radius: 20px;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
        """)

    def _apply_open_style(self):
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: black;
                border: 2px solid #cccccc;
                border-radius: 20px;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """)


# =============================================================================
# 2. SCHEMATIC CANVAS FRAME
# =============================================================================
class SchematicFrame(QFrame):
    def __init__(self, valve_request_cb, pressure_toggle_cb=None, parent=None):     
        super().__init__(parent)
        self.valve_request_cb = valve_request_cb
        self.pressure_toggle_cb = pressure_toggle_cb

        # store valve status, pressures and temperatures
        self.valves = {}
        self.pressures = [None] * 10
        self.temperatures = [None] * 3

        # Pressure, Valve and Temperature sizes, TODO: connect as parameters to ui components
        self.P_WIDTH = 86
        self.P_HEIGHT = 80
        self.V_SIZE = 40
        self.T_WIDTH = 80
        self.T_HEIGHT = 42
        
        self._setup_widgets()

    def get_active_reactors(self) -> list[int]:
        return [p.nr for p in self.pressures if p and p.is_on]

    def get_inactive_reactors(self) -> list[int]:
        return [p.nr for p in self.pressures if p and not p.is_on]

    def _setup_widgets(self):
        START_X = 190
        COL_SPACING = 90

        self.Y_TOP_P = 20
        self.Y_TOP_V = 105
        self.Y_TOP_BUS = 165

        self.Y_MID_V11     = 185  
        self.Y_BRANCH_H2   = 245   
        self.Y_BRANCH_TRAP = 295  
        self.Y_BRANCH_PUMP = 345 
        self.Y_MID_V12     = 375 

        self.Y_BOT_BUS = 435
        self.Y_BOT_V   = 455
        self.Y_BOT_P   = 515

        # Reactors 10 -> 6 (Left to Right) with corresponding valves
        top_reactors = [10, 9, 8, 7, 6]
        for i, nr in enumerate(top_reactors):
            cx = START_X + (i * COL_SPACING)
            p = UIPressure(self, nr, self.pressure_toggle_cb)
            p.move(cx - self.P_WIDTH // 2, self.Y_TOP_P)
            self.pressures[nr - 1] = p

            v = UIValve(self, nr, self.valve_request_cb)
            v.btn.move(cx - self.V_SIZE // 2, self.Y_TOP_V)
            self.valves[nr] = v

        # Reactors 1 -> 5 (Left to Right)  with corresponding valves
        bot_reactors = [1, 2, 3, 4, 5]
        for i, nr in enumerate(bot_reactors):
            cx = START_X + (i * COL_SPACING)
            v = UIValve(self, nr, self.valve_request_cb)
            v.btn.move(cx - self.V_SIZE // 2, self.Y_BOT_V)
            self.valves[nr] = v

            p = UIPressure(self, nr, self.pressure_toggle_cb)
            p.move(cx - self.P_WIDTH // 2, self.Y_BOT_P)
            self.pressures[nr - 1] = p

        # Other valves
        col0_x = START_X
        v11 = UIValve(self, 11, self.valve_request_cb)
        v11.btn.move(col0_x - self.V_SIZE // 2, self.Y_MID_V11)
        self.valves[11] = v11

        v12 = UIValve(self, 12, self.valve_request_cb)
        v12.btn.move(col0_x - self.V_SIZE // 2, self.Y_MID_V12)
        self.valves[12] = v12

        v13 = UIValve(self, 13, self.valve_request_cb)
        v13.btn.move(col0_x + 35, self.Y_BRANCH_H2 - self.V_SIZE // 2)
        self.valves[13] = v13

        v14 = UIValve(self, 14, self.valve_request_cb)
        v14.btn.move(col0_x - 75, self.Y_BRANCH_TRAP - self.V_SIZE // 2)
        self.valves[14] = v14

        v15 = UIValve(self, 15, self.valve_request_cb)
        v15.btn.move(col0_x + 35, self.Y_BRANCH_PUMP - self.V_SIZE // 2)
        self.valves[15] = v15

        # Temperature Sensors (Oven 1, Oven 2, Trap)
        t2 = UITemperature(self, 2, label="Oven 2")
        t2.btn.move(START_X + (3 * COL_SPACING), self.Y_TOP_BUS + 20)
        self.temperatures[0] = t2

        t1 = UITemperature(self, 1, label="Oven 1")
        t1.btn.move(START_X + (3 * COL_SPACING), self.Y_BOT_BUS - 60)
        self.temperatures[1] = t1

        t3 = UITemperature(self, 3, label="Trap")
        t3.btn.move(col0_x - 180, self.Y_BRANCH_TRAP - (self.T_HEIGHT // 2))
        self.temperatures[2] = t3

        self.temperatures = [t1, t2, t3]

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        pen = QPen(QColor(0, 0, 0), 2)
        painter.setPen(pen)
        painter.setBrush(QColor(0, 0, 0))

        START_X = 190
        COL_SPACING = 90
        col0_x = START_X
        col_end_x = START_X + (4 * COL_SPACING)

        # --- Top and Bottom Bus Bars ---
        painter.drawLine(QPoint(col0_x, self.Y_TOP_BUS), QPoint(col_end_x, self.Y_TOP_BUS))
        painter.drawLine(QPoint(col0_x, self.Y_BOT_BUS), QPoint(col_end_x, self.Y_BOT_BUS))

        # --- Vertical Column Pipes ---
        for i in range(5):
            cx = START_X + (i * COL_SPACING)

            # Top Column: P -> Valve -> Bus
            painter.drawLine(QPoint(cx, self.Y_TOP_P + self.P_HEIGHT), QPoint(cx, self.Y_TOP_V))
            painter.drawLine(QPoint(cx, self.Y_TOP_V + self.V_SIZE), QPoint(cx, self.Y_TOP_BUS))

            # Bottom Column: Bus -> Valve -> P
            painter.drawLine(QPoint(cx, self.Y_BOT_BUS), QPoint(cx, self.Y_BOT_V))
            painter.drawLine(QPoint(cx, self.Y_BOT_V + self.V_SIZE), QPoint(cx, self.Y_BOT_P))

            # Junction Nodes
            painter.drawEllipse(QPoint(cx, self.Y_TOP_BUS), 3, 3)
            painter.drawEllipse(QPoint(cx, self.Y_BOT_BUS), 3, 3)

        # --- Central Trunk Line (Column 0) ---
        painter.drawLine(QPoint(col0_x, self.Y_TOP_BUS), QPoint(col0_x, self.Y_MID_V11))
        painter.drawLine(QPoint(col0_x, self.Y_MID_V11 + self.V_SIZE), QPoint(col0_x, self.Y_MID_V12))
        painter.drawLine(QPoint(col0_x, self.Y_MID_V12 + self.V_SIZE), QPoint(col0_x, self.Y_BOT_BUS))

        # --- Branch Piping ---
        # 1. H2 Branch
        h2_end_x = col0_x + 105
        painter.drawEllipse(QPoint(col0_x, self.Y_BRANCH_H2), 3, 3)
        painter.drawLine(QPoint(col0_x, self.Y_BRANCH_H2), QPoint(h2_end_x, self.Y_BRANCH_H2))

        # 2. Trap Branch & Bypass Line
        trap_left_x = col0_x - 180
        trap_right_x = col0_x - 100
        painter.drawEllipse(QPoint(col0_x, self.Y_BRANCH_TRAP), 3, 3)
        painter.drawLine(QPoint(col0_x, self.Y_BRANCH_TRAP), QPoint(trap_right_x, self.Y_BRANCH_TRAP))

        # Trap bypass piping loop
        loop_pen = QPen(QColor(0, 0, 0), 2)
        painter.setPen(loop_pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        
        path = QPainterPath()
        path.moveTo(trap_right_x, self.Y_BRANCH_TRAP)
        path.lineTo(trap_right_x - 10, self.Y_BRANCH_TRAP + 15)
        path.lineTo(trap_left_x + 10, self.Y_BRANCH_TRAP + 15)
        path.lineTo(trap_left_x, self.Y_BRANCH_TRAP)
        painter.drawPath(path)

        # 3. Vacuum Pump Branch
        pump_end_x = col0_x + 105
        painter.setBrush(QColor(0, 0, 0))
        painter.drawEllipse(QPoint(col0_x, self.Y_BRANCH_PUMP), 3, 3)
        painter.drawLine(QPoint(col0_x, self.Y_BRANCH_PUMP), QPoint(pump_end_x, self.Y_BRANCH_PUMP))

        # --- Vector Graphic Schematics ---
        # H2 Cylinder
        h2_rect = QtCore.QRect(h2_end_x, self.Y_BRANCH_H2 - 35, 36, 70)
        painter.setPen(QPen(QColor("#222222"), 2))
        painter.setBrush(QColor("#6c757d"))
        painter.drawRoundedRect(h2_rect, 14, 14)
        painter.setPen(QPen(QColor("white")))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(h2_rect, QtCore.Qt.AlignmentFlag.AlignCenter, "H₂")

        # Vacuum Pump
        pump_center = QPoint(pump_end_x + 18, self.Y_BRANCH_PUMP)
        painter.setPen(QPen(QColor("#222222"), 2))
        painter.setBrush(QColor("#e0e0e0"))
        painter.drawEllipse(pump_center, 18, 18)
        
        painter.setBrush(QColor("#222222"))
        triangle = [
            QPoint(pump_center.x() - 10, pump_center.y() + 8),
            QPoint(pump_center.x() + 10, pump_center.y() + 8),
            QPoint(pump_center.x(), pump_center.y() - 10)
        ]
        painter.drawPolygon(triangle)

# =============================================================================
# 3. TAB 1: CONTROL VIEW
# =============================================================================
class ControlTab(QtWidgets.QWidget):
    def __init__(self, valve_request_cb, oxidize_request_cb, pressure_toggle_cb=None, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)

        # Schematic
        left_container = QtWidgets.QVBoxLayout()
        self.schematic = SchematicFrame(valve_request_cb, pressure_toggle_cb, self)
        self.schematic.setFixedSize(620, 660)
        left_container.addWidget(self.schematic)

        # Add Oxidize Iron action button underneath schematic
        self.oxidize_btn = QPushButton("Start Iron Oxidation")
        self.oxidize_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
        """)
        self.oxidize_btn.clicked.connect(self.handle_oxidize_click)
        left_container.addWidget(self.oxidize_btn)

        self.oxidize_request_cb = oxidize_request_cb
        layout.addLayout(left_container)

        # Plot Widget
        self.plot_widget = pg.PlotWidget(title="Pressure History")
        self.plot_widget.setLabel('left', 'Pressure', units='bar')
        self.plot_widget.setLabel('bottom', 'Time Steps') #TODO: adapt to Time s
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setBackground('w')
        self.plot_widget.setYRange(0, 2)
        self.plot_widget.addLegend()

        # Create plot curve per pressure
        self.curves = []
        for p in self.schematic.pressures:
            pen = pg.mkPen(color=p.color, width=2)
            curve = self.plot_widget.plot(pen=pen, name=f"P{p.nr}")
            self.curves.append(curve)

        layout.addWidget(self.plot_widget)

    def handle_oxidize_click(self):
        # Retrieve non-disabled reactors from schematic canvas # TODO: Move Button in separate class and what is this function?
        if self.oxidize_request_cb:
            self.oxidize_request_cb()

    def update_pressure(self, values: list, data_history: list):
        # Update pressure UI button values
        for i, val in enumerate(values):
            if i < len(self.schematic.pressures):
                self.schematic.pressures[i].set_value(val)

        # Update curve data for each sensor
        for i, curve in enumerate(self.curves):
            if i < len(data_history):
                formatted_history = [float('nan') if v is None else v for v in data_history[i]]
                curve.setData(formatted_history)

    def update_temperatures(self, values):
        for i, val in enumerate(values):
            if i < len(self.schematic.temperatures):
                self.schematic.temperatures[i].set_value(val)

# =============================================================================
# 4. TAB 2: PARAMETERS / SETTINGS VIEW (JSON CONFIG EDITOR)
# =============================================================================
class JSONConfigFileTab(QtWidgets.QWidget):
    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.config_data = {}
        self.widgets_map = {} 

        layout = QtWidgets.QVBoxLayout(self)

        # Scrollable area for dynamically sized forms
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(self.container)

        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)

        # Save Button
        self.save_btn = QtWidgets.QPushButton(f"Save '{os.path.basename(filepath)}'")
        self.save_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        self.save_btn.clicked.connect(self.save_config)
        layout.addWidget(self.save_btn)

        self.load_config()

    def load_config(self):
        if not os.path.exists(self.filepath):
            lbl = QtWidgets.QLabel(f"Configuration file not found: {self.filepath}")
            self.container_layout.addWidget(lbl)
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.config_data = json.load(f)
            self._build_ui(self.config_data, self.container_layout)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error Loading File", f"Could not read {self.filepath}:\n{e}")

    def _build_ui(self, data, parent_layout, path=()):
        if isinstance(data, dict):
            form = QtWidgets.QFormLayout()
            for key, val in data.items():
                current_path = path + (key,)
                if isinstance(val, (dict, list)):
                    group = QtWidgets.QGroupBox(str(key).replace("_", " ").title())
                    group_layout = QtWidgets.QVBoxLayout(group)
                    self._build_ui(val, group_layout, current_path)
                    parent_layout.addWidget(group)
                else:
                    widget = self._create_widget_for_val(val, current_path)
                    form.addRow(str(key).replace("_", " ").title() + ":", widget)
            if form.rowCount() > 0:
                parent_layout.addLayout(form)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = path + (i,)
                group = QtWidgets.QGroupBox(f"Item {i + 1}")
                group_layout = QtWidgets.QVBoxLayout(group)
                self._build_ui(item, group_layout, current_path)
                parent_layout.addWidget(group)

    def _create_widget_for_val(self, val, path):
        if isinstance(val, bool):
            widget = QtWidgets.QCheckBox()
            widget.setChecked(val)
        elif isinstance(val, int):
            widget = QtWidgets.QSpinBox()
            widget.setRange(-2147483648, 2147483647)
            widget.setValue(val)
        elif isinstance(val, float):
            widget = QtWidgets.QDoubleSpinBox()
            widget.setRange(-1000000.0, 1000000.0)
            widget.setDecimals(4)
            widget.setValue(val)
        else:
            widget = QtWidgets.QLineEdit(str(val))

        self.widgets_map[path] = (widget, type(val))
        return widget

    def save_config(self):
        for path, (widget, val_type) in self.widgets_map.items():
            if val_type == bool:
                val = widget.isChecked()
            elif val_type == int:
                val = widget.value()
            elif val_type == float:
                val = widget.value()
            else:
                val = widget.text()

            # Traverse data structure to update target key/index
            target = self.config_data
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = val

        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2)
            QtWidgets.QMessageBox.information(
                self, "Success", f"Successfully saved modifications to:\n{os.path.basename(self.filepath)}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error Saving File", f"Failed to save {self.filepath}:\n{e}")


class ParametersTab(QtWidgets.QWidget):
    def __init__(self, config_files=None, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        self.sub_tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.sub_tabs)

        if config_files is None:
            config_files = [
                "conditioning_config.json",
                "keller_config.json",
                "smc_config.json",
                "tm_config.json"
            ]

        for filepath in config_files:
            tab_title = os.path.basename(filepath).replace(".json", "").replace("_", " ").title()
            editor_tab = JSONConfigFileTab(filepath, self)
            self.sub_tabs.addTab(editor_tab, tab_title)


# =============================================================================
# 5. MAIN WINDOW
# =============================================================================
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, smc_worker, procedures, proc_worker):
        super().__init__()
        self.setWindowTitle("New Age")
        self.resize(1420, 760)

        self.pressure_history = [[]]
        self.smc_worker = smc_worker
        self.procedures = procedures
        self.proc_worker = proc_worker

        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        self.control_tab = ControlTab(
            valve_request_cb=self.smc_worker.send_request,
            oxidize_request_cb=self.request_oxidize_iron
        )
        self.parameters_tab = ParametersTab()

        self.tabs.addTab(self.control_tab, "Control & Schematic")
        self.tabs.addTab(self.parameters_tab, "Parameters & Configuration")

    def request_oxidize_iron(self):
        self.proc_worker.send_request("oxidise_iron")

    def handle_pressure_update(self, vals: list):
        masked_vals = []
        for i, val in enumerate(vals):
            if i < len(self.control_tab.schematic.pressures):
                p_btn = self.control_tab.schematic.pressures[i]
                # If reactor toggle is off, force value to None
                if not p_btn.is_on:
                    masked_vals.append(None)
                    continue
            masked_vals.append(val)

        for i, val in enumerate(masked_vals):
            if i < len(self.pressure_history):
                self.pressure_history[i].append(val)
                
        self.control_tab.update_pressure(masked_vals, self.pressure_history)

    def handle_temperature_update(self, vals: list):
        self.control_tab.update_temperatures(vals)

    def handle_valve_status_update(self, valves: list):
        schematic = self.control_tab.schematic
        active_set = set(valves)

        for valve_nr, valve in schematic.valves.items(): 
            if valve is not None:
                status = 1 if valve_nr in active_set else 0
                valve.set_status(status)


# =============================================================================
# 6. APPLICATION ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    smcdevnet = smc.SmcDevNet()
    smcdevnet.start()
    smc_worker_thread = worker.Worker(smcdevnet,"get_status_all")

    keller_sensor = keller.Keller()
    keller_worker_thread = worker.Worker(keller_sensor, "get_pressure_all")

    tm_sensor = tm.TMHardware()
    tm_worker_thread = worker.Worker(tm_sensor, "get_temperature_all")

    proc = procedures.Procedures(keller_worker_thread, tm_worker_thread, smc_worker_thread)
    proc_worker_thread = worker.Worker(procedures)

    window = MainWindow(smc_worker_thread, proc, proc_worker_thread)

    # Connect Asynchronous Worker Threads to the GUI
    keller_worker_thread.data_update.connect(window.handle_pressure_update)
    tm_worker_thread.data_update.connect(window.handle_temperature_update)
    smc_worker_thread.data_update.connect(window.handle_valve_status_update)

    # Start Workers
    keller_worker_thread.start() 
    tm_worker_thread.start() 
    smc_worker_thread.start()
    proc_worker_thread.start()

    window.show()
    exit_code = app.exec()

    # Stop Workers
    keller_worker_thread.stop()
    tm_worker_thread.stop()
    smc_worker_thread.stop()
    proc_worker_thread.stop()

    smcdevnet.stop()
    sys.exit(exit_code)
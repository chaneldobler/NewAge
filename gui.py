import sys
import os
import json
from PySide6 import QtWidgets,QtCore
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame
from PySide6.QtCore import QSize, QPoint
from PySide6.QtGui import QColor, QPainter, QPen
import pyqtgraph as pg

# Hardware & Worker Imports
import keller, smc, tm
import worker


# =============================================================================
# 1. UI COMPONENTS
# =============================================================================
class UIPressure:
    def __init__(self, parent, nr):
        self.parent = parent
        self.nr = nr

        self.btn = QPushButton(f"P{nr}\n-- bar", parent)
        self.btn.setFixedSize(QSize(80, 60))
        self.btn.setEnabled(False)

        hue = 0.5 + 0.5 * (nr - 1) / 10
        bg_color = QColor.fromHslF(hue, 0.75, 0.45).name()
        self.btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: 2px solid #444444;
                border-radius: 10px;
                font-weight: bold;
            }}
            QPushButton:pressed {{
                background-color: #222222;
            }}
        """)

    def set_value(self, val: float):
        self.btn.setText(f"Reactor {self.nr}\n{val:.4f} bar")


class UITemperature:
    def __init__(self, parent, nr):
        self.parent = parent
        self.nr = nr

        self.btn = QPushButton(f"T{nr}\n-- °C", parent)
        self.btn.setFixedSize(QSize(80, 60))
        self.btn.setEnabled(False)

        self.btn.setStyleSheet(f"""
            QPushButton {{
                background-color: red;
                color: white;
                border: 2px solid #444444;
                border-radius: 10px;
                font-weight: bold;
            }}
            QPushButton:pressed {{
                background-color: #222222;
            }}
        """)

    def set_value(self, val: float):
        self.btn.setText(f"Oven {self.nr}\n{val:.2f} °C")


class UIValve:
    def __init__(self, parent, nr, request_cb):
        self.parent = parent
        self.nr = nr
        self.status = 0
        self.request_cb = request_cb # Callback to queue requests to the worker

        self.btn = QPushButton(f"{self.nr}", parent)
        self.btn.setFixedSize(QSize(40, 40))
        self._apply_closed_style()

        self.btn.clicked.connect(self.request_toggle)

    def request_toggle(self):
        # We don't change the hardware here. We ask the worker to do it.
        if self.status == 0:
            self.request_cb("open", self.nr)
        else:
            self.request_cb("close", self.nr)

    def set_status(self, current_status):
        # Called by the GUI thread when the worker confirms the hardware state
        if self.status == current_status:
            return # Avoid redundant UI updates
            
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
    def __init__(self, valve_request_cb, parent=None):
        super().__init__(parent)
        self.valve_request_cb = valve_request_cb
        
        self.valves = {} # Dictionary mapping valve_nr -> UIValve instance
        self.pressures = []
        self.temperatures = []
        
        self._setup_widgets()

    def _setup_widgets(self):
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
            p = UIPressure(self, i + 1)
            p.btn.move(x, Y_ROW1_PRESSURE)
            self.pressures.append(p)

        # 2. Row 2: Valve Row (Top)
        for i in range(5):
            nr = i + 1
            x = START_X + (i * COL_SPACING)
            v = UIValve(self, nr, self.valve_request_cb)
            v.btn.move(x + 20, Y_ROW2_VALVES)
            self.valves[nr] = v

        # 3. Middle Isolation Valves
        col1_valve_x = START_X + 20
        v11 = UIValve(self, 11, self.valve_request_cb)
        v11.btn.move(col1_valve_x, Y_MID_V11)
        v12 = UIValve(self, 12, self.valve_request_cb)
        v12.btn.move(col1_valve_x, Y_MID_V12)
        self.valves[11] = v11
        self.valves[12] = v12

        # Branch Valves
        v13 = UIValve(self, 13, self.valve_request_cb)
        v13.btn.move(col1_valve_x + 90, 305 - 20)
        v14 = UIValve(self, 14, self.valve_request_cb)
        v14.btn.move(col1_valve_x - 50, 340 - 20)
        v15 = UIValve(self, 15, self.valve_request_cb)
        v15.btn.move(col1_valve_x + 90, 375 - 20)
        self.valves[13] = v13
        self.valves[14] = v14
        self.valves[15] = v15

        # Temperature Sensors
        col5_sensor_x = START_X + (4 * COL_SPACING) + 20
        t1 = UITemperature(self, 1)
        t1.btn.move(col5_sensor_x, Y_MID_V11)
        t2 = UITemperature(self, 2)
        t2.btn.move(col5_sensor_x, Y_MID_V12 - 20)

        col0_sensor_x = START_X - 100
        t3 = UITemperature(self, 3)
        t3.btn.move(col0_sensor_x, Y_MID_V11)
        self.temperatures.extend([t1, t2, t3])

        # Bottom Rows
        for i in range(5):
            nr = i + 6
            x = START_X + (i * COL_SPACING)
            v = UIValve(self, nr, self.valve_request_cb)
            v.btn.move(x + 20, Y_ROW3_VALVES)
            self.valves[nr] = v

            p = UIPressure(self, nr)
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
# 3. TAB 1: CONTROL VIEW
# =============================================================================
class ControlTab(QtWidgets.QWidget):
    def __init__(self, valve_request_cb, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QHBoxLayout(self)

        # Schematic
        self.schematic = SchematicFrame(valve_request_cb, self)
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
# 4. TAB 2: PARAMETERS / SETTINGS VIEW (JSON CONFIG EDITOR)
# =============================================================================
class JSONConfigFileTab(QtWidgets.QWidget):
    """Generates an interactive form UI for a given JSON configuration file."""
    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.config_data = {}
        self.widgets_map = {}  # Maps key paths to (widget, original_type)

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
        """Loads JSON file data and constructs form inputs."""
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
        """Recursively parses dicts and lists to construct input controls."""
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
        """Creates standard inputs according to JSON data types."""
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
        """Reads input values from UI widgets and overwrites the JSON file."""
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
    """Tab container hosting dynamic settings tabs for each JSON file."""
    def __init__(self, config_files=None, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        self.sub_tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.sub_tabs)

        # Default paths to your configuration files
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
# 5. MAIN WINDOW WITH QTABWIDGET
# =============================================================================
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, smc_worker):
        super().__init__()
        self.setWindowTitle("Valve & Pressure Controller")
        self.resize(1420, 720)

        self.pressure_data = []
        self.smc_worker = smc_worker # Save reference to the worker

        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # Pass the worker's send_request method down into the UI logic
        self.control_tab = ControlTab(valve_request_cb=self.smc_worker.send_request)
        self.parameters_tab = ParametersTab()

        self.tabs.addTab(self.control_tab, "Control & Schematic")
        self.tabs.addTab(self.parameters_tab, "Parameters & Configuration")

    def handle_pressure_update(self, val: list):
        self.pressure_data.append(val[0])
        self.control_tab.update_pressure(val[0], list(self.pressure_data))

    def handle_temperature_update(self, vals: list):
        self.control_tab.update_temperatures(vals)

    def handle_valve_status_update(self, valves: list):
        schematic = self.control_tab.schematic
        active_set = set(valves)

        for valve_nr, valve in schematic.valves.items():
            status = 1 if valve_nr in active_set else 0
            valve.set_status(status)    


# =============================================================================
# 6. APPLICATION ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    # 1. Initialize SMC Hardware & Worker
    smcdevnet = smc.SmcDevNet()
    smcdevnet.start()

    smc_worker_thread = worker.Worker(smcdevnet,"get_status_all")

    # 2. Initialize Other Hardware & Workers
    keller_sensor = keller.Keller()
    keller_worker_thread = worker.Worker(keller_sensor, "get_pressure_all")

    tm_sensor = tm.TMHardware()
    tm_worker_thread = worker.Worker(tm_sensor, "get_temperature_all")

    # 3. Main GUI App initialization
    window = MainWindow(smc_worker_thread)

    # 4. Connect Asynchronous Worker Threads to the GUI
    keller_worker_thread.data_update.connect(window.handle_pressure_update)
    tm_worker_thread.data_update.connect(window.handle_temperature_update)
    smc_worker_thread.data_update.connect(window.handle_valve_status_update)

    # 5. Start Workers
    keller_worker_thread.start() 
    tm_worker_thread.start() 
    smc_worker_thread.start()

    window.show()
    exit_code = app.exec()

    # 6. Cleanup
    keller_worker_thread.stop()
    tm_worker_thread.stop()
    smc_worker_thread.stop()
    smcdevnet.stop()
    sys.exit(exit_code)
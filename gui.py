import sys
import os
import json
from PySide6 import QtWidgets,QtCore
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import QSize, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QPolygonF, QBrush
import pyqtgraph as pg

# Hardware & Worker Imports
import keller, smc, tm
import worker
import procedures


# sizes as parameters to pass in arguments
# lengths as well

# =============================================================================
# 1. UI COMPONENTS
# =============================================================================
class UIPressure(QWidget):
    def __init__(self, parent, id):
        super().__init__(parent)
        self.parent = parent
        self.id = id
        self.active = True 

        # Reactor Color
        hue = (self.id - 1) / 10.0
        self.color = QColor.fromHslF(hue, 0.75, 0.45)

        # Outer Layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Main Frame 
        self.main_frame = QFrame()
        outer_layout.addWidget(self.main_frame)

        frame_layout = QVBoxLayout(self.main_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Header 
        self.header_display = QLabel(f"Reactor {self.id}")
        self.header_display.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.header_display.setFixedHeight(30) 

        # Body Container 
        self.body_widget = QWidget()
        self.body_widget.setObjectName("bodyWidget") 
        
        body_layout = QVBoxLayout(self.body_widget)
        body_layout.setContentsMargins(6, 6, 6, 6) 
        body_layout.setSpacing(6)

        # Value Display
        self.value_label = QLabel("-- mbar")
        self.value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Toggle Button 
        self.toggle_btn = QPushButton("Deactivate")
        self.toggle_btn.setFixedHeight(20)
        self.toggle_btn.clicked.connect(self.toggle)

        # Layout Assembly
        body_layout.addWidget(self.value_label)
        body_layout.addWidget(self.toggle_btn)

        frame_layout.addWidget(self.header_display)
        frame_layout.addWidget(self.body_widget)

        self.setFixedSize(120, 100)
        self._apply_style()

    def toggle(self):
        self.active = not self.active
        self._apply_style()

    def set_value(self, val: float):
        if not self.active:
            self.value_label.setText("")
        elif val is None:
            self.value_label.setText("-- mbar")
        else:
            self.value_label.setText(f"{int(val*1000)} mbar")

    def _apply_style(self):
        header_bg = self.color.name() if self.active else "#555555"
        btn_text = "Deactivate" if self.active else "Activate"

        # Outer Frame
        self.main_frame.setStyleSheet("""
            QFrame {
                border: 2px solid #333333;
                border-radius: 0px;
            }
            #bodyWidget {
                background-color: #e0e0e0; 
            }
        """)

        # Header
        self.header_display.setStyleSheet(f"""
            QLabel {{
                background-color: {header_bg};
                color: white;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
            }}
        """)

        # Value 
        value_fg = "#212529" if self.active else "#a0a0a0"
        self.value_label.setStyleSheet(f"""
            QLabel {{
                color: {value_fg};
                border: none;
                background: transparent;
                font-weight: bold;
                font-size: 12px;
            }}
        """)
        
        # Button
        self.toggle_btn.setText(btn_text)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: #ffffff;
                border: 1px solid #545b62;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5c636a;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)

class UITemperature(QWidget):
    def __init__(self, parent, id, label):
        super().__init__(parent)
        self.parent = parent
        self.id = id
        self.label = label

        self.header_color = "#8F6060"

        # Outer Layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Main Frame 
        self.main_frame = QFrame()
        outer_layout.addWidget(self.main_frame)

        frame_layout = QVBoxLayout(self.main_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Header 
        self.header_display = QLabel(self.label)
        self.header_display.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.header_display.setFixedHeight(20) 

        # Body Container 
        self.body_widget = QWidget()
        self.body_widget.setObjectName("bodyWidget") 
        
        body_layout = QVBoxLayout(self.body_widget)
        body_layout.setContentsMargins(6, 6, 6, 6) 
        body_layout.setSpacing(0)

        # Value Display
        self.value_label = QLabel("-- °C")
        self.value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Layout Assembly
        body_layout.addWidget(self.value_label)

        frame_layout.addWidget(self.header_display)
        frame_layout.addWidget(self.body_widget)

        self.setFixedSize(90, 50)
        self._apply_style()

    def set_value(self, val: float):
        if val is None:
            self.value_label.setText("-- °C")
        else:
            self.value_label.setText(f"{int(val)} °C")

    def _apply_style(self):
        # Outer Frame
        self.main_frame.setStyleSheet("""
            QFrame {
                border: 2px solid #333333;
                border-radius: 0px;
            }
            #bodyWidget {
                background-color: #e0e0e0; 
            }
        """)

        # Header
        self.header_display.setStyleSheet(f"""
            QLabel {{
                background-color: {self.header_color};
                color: white;
                border: none;
                border-radius: 0px;
                font-weight: bold;
                font-size: 12px;
            }}
        """)

        # Value
        self.value_label.setStyleSheet("""
            QLabel {
                color: #212529;
                border: none;
                background: transparent;
                font-weight: bold;
                font-size: 12px;
            }
        """)

class UIValve(QWidget):
    def __init__(self, parent, id, request_cb, orientation='vertical'):
        super().__init__(parent)
        self.parent = parent
        self.id = id
        self.open = True
        self.orientation = orientation
        self.request_cb = request_cb

        self.setFixedSize(30, 30)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.request_toggle()

    def request_toggle(self):
        if self.open:
            self.request_cb("close", self.id)
        else:
            self.request_cb("open", self.id)

    def set_status(self, status):
        if self.open != status:
            self.open = status
            self.update()  # Trigger repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0

        if self.orientation == 'vertical':
            tri1 = QPolygonF([QPointF(2, 2), QPointF(w - 2, 2), QPointF(cx, cy)])
            tri2 = QPolygonF([QPointF(2, h - 2), QPointF(w - 2, h - 2), QPointF(cx, cy)])
        else:
            tri1 = QPolygonF([QPointF(2, 2), QPointF(2, h - 2), QPointF(cx, cy)])
            tri2 = QPolygonF([QPointF(w - 2, 2), QPointF(w - 2, h - 2), QPointF(cx, cy)])

        pen = QPen(QColor("#000000"), 2)
        brush = QBrush(QColor("#ffffff")) if self.open else QBrush(QColor("#000000"))
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawPolygon(tri1)
        painter.drawPolygon(tri2)


# =============================================================================
# 2. SCHEMATIC CANVAS FRAME
# =============================================================================
class SchematicFrame(QFrame):
    def __init__(self, valve_request_cb, parent=None):     
        super().__init__(parent)
        self.valve_request_cb = valve_request_cb

        self.valves = [UIValve(self, i + 1, self.valve_request_cb) for i in range(19)]
        self.pressures = [UIPressure(self, i + 1) for i in range(10)]
        self.temperatures = [UITemperature(self, 1, label="Trap"), UITemperature(self, 2, label="Oven 1"), UITemperature(self, 3, label="Oven 2")]

        self.P_WIDTH = 120 // 2
        self.P_HEIGHT = 95 // 2
        self.V_SIZE = 30 // 2
        self.T_WIDTH = 90 // 2
        self.T_HEIGHT = 55 // 2

        self.START_X = 200
        self.COL_SPACING = 150
        self.X_OFFSETS = [self.START_X + (i * self.COL_SPACING) for i in range(5)] 

        self.Y_TOP_P = 100
        self.Y_TOP_V = 175
        self.Y_TOP_BUS = 200

        self.Y_LINE_2 = 250  
        self.Y_H2 = 300   
        self.Y_TRAP = 350  
        self.Y_VACUUM = 400 
        self.Y_LINE_1 = 450 

        self.Y_BOT_BUS = 500
        self.Y_BOT_V   = 525
        self.Y_BOT_P   = 600
        
        self._setup_widgets()

    def get_active_reactors(self) -> list[int]:
        return [p.id for p in self.pressures if p and p.active]

    def get_inactive_reactors(self) -> list[int]:
        return [p.id for p in self.pressures if p and not p.active]

    def _setup_widgets(self):
        for i, x in enumerate(self.X_OFFSETS):
            # Bottom Rows
            self.pressures[i].move(x - self.P_WIDTH, self.Y_BOT_P - self.P_HEIGHT)
            self.valves[i].move(x - self.V_SIZE, self.Y_BOT_V - self.V_SIZE)

            # Top Rows
            self.pressures[-(i + 1)].move(x - self.P_WIDTH, self.Y_TOP_P - self.P_HEIGHT)
            self.valves[i + 10].move(x - self.V_SIZE, self.Y_TOP_V - self.V_SIZE)

        # Valve Line 1
        self.valves[5].move(self.START_X - self.V_SIZE, self.Y_LINE_1 - self.V_SIZE)

        # Valve Line 2
        self.valves[9].move(self.START_X - self.V_SIZE, self.Y_LINE_2 - self.V_SIZE)
        
        # Valve Vacuum
        self.valves[6].move(self.START_X - self.V_SIZE + 50, self.Y_VACUUM - self.V_SIZE)

        # Valve Trap
        self.valves[7].move(self.START_X - self.V_SIZE - 50, self.Y_TRAP - self.V_SIZE)

        # Valve H2
        self.valves[8].move(self.START_X - self.V_SIZE + 50, self.Y_H2 - self.V_SIZE)

        # Trap
        self.temperatures[0].move(self.START_X - self.T_WIDTH - self.COL_SPACING, self.Y_TRAP - self.T_HEIGHT)

        # Oven 1
        self.temperatures[1].move(self.X_OFFSETS[-2] - self.T_WIDTH, self.Y_LINE_1 - self.T_HEIGHT)

        # Oven 2
        self.temperatures[2].move(self.X_OFFSETS[-2] - self.T_WIDTH, self.Y_LINE_2 - self.T_HEIGHT)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        pen = QPen(QColor(0, 0, 0), 2)
        painter.setPen(pen)
        painter.setBrush(QColor(0, 0, 0))

        col_start_x = self.START_X
        col_end_x = self.X_OFFSETS[-1]

        # Horizontal Connections
        painter.drawLine(QPoint(col_start_x, self.Y_TOP_BUS), QPoint(col_end_x, self.Y_TOP_BUS))
        painter.drawLine(QPoint(col_start_x, self.Y_BOT_BUS), QPoint(col_end_x, self.Y_BOT_BUS))

        painter.drawLine(QPoint(col_start_x, self.Y_TOP_BUS), QPoint(col_start_x, self.Y_LINE_2 - self.V_SIZE))
        painter.drawLine(QPoint(col_start_x, self.Y_LINE_2 + self.V_SIZE), QPoint(col_start_x, self.Y_LINE_1 - self.V_SIZE))
        painter.drawLine(QPoint(col_start_x, self.Y_LINE_1 + self.V_SIZE), QPoint(col_start_x, self.Y_BOT_BUS))

        # Vertical Connections
        for x in self.X_OFFSETS:
            # Top Row
            painter.drawLine(QPoint(x, self.Y_TOP_P), QPoint(x, self.Y_TOP_V))
            painter.drawLine(QPoint(x, self.Y_TOP_V + self.V_SIZE), QPoint(x, self.Y_TOP_BUS))

            # Bottom Row
            painter.drawLine(QPoint(x, self.Y_BOT_BUS), QPoint(x, self.Y_BOT_V))
            painter.drawLine(QPoint(x, self.Y_BOT_V + self.V_SIZE), QPoint(x, self.Y_BOT_P))

            # Junctions
            painter.drawEllipse(QPoint(x, self.Y_TOP_BUS), 3, 3)
            painter.drawEllipse(QPoint(x, self.Y_BOT_BUS), 3, 3)

        # H2 

        painter.drawEllipse(QPoint(col_start_x, self.Y_H2), 3, 3)
        painter.drawLine(QPoint(col_start_x, self.Y_H2), QPoint(self.X_OFFSETS[1] - 30, self.Y_H2))

        # Trap
        painter.drawEllipse(QPoint(col_start_x, self.Y_TRAP), 3, 3)
        painter.drawLine(QPoint(col_start_x, self.Y_TRAP), QPoint(col_start_x - 50, self.Y_TRAP))

        # Vacuum
        painter.drawEllipse(QPoint(col_start_x, self.Y_VACUUM), 3, 3)
        painter.drawLine(QPoint(col_start_x, self.Y_VACUUM), QPoint(self.X_OFFSETS[1] - 30, self.Y_VACUUM))

        # H2 Drawing
        h2_height = 80
        h2_width = 30
        h2_rect = QtCore.QRect(self.X_OFFSETS[1] - 30 - h2_width // 2, self.Y_H2 - h2_height // 2, h2_width, h2_height)
        painter.setPen(QPen(QColor("#222222"), 2))
        painter.setBrush(QColor("#6c757d"))
        painter.drawRoundedRect(h2_rect, 10, 10)
        painter.setPen(QPen(QColor("white")))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(h2_rect, QtCore.Qt.AlignmentFlag.AlignCenter, "H₂")

        # Vacuum Drawing
        vac_size = 16
        pump_center = QPoint(self.X_OFFSETS[1] - 30 , self.Y_VACUUM)
        painter.setPen(QPen(QColor("#222222"), 2))
        painter.setBrush(QColor("#e0e0e0"))
        painter.drawEllipse(pump_center, vac_size, vac_size)
        
        painter.setBrush(QColor("#222222"))
        triangle = [
            QPoint(pump_center.x() - 10, pump_center.y() + 6),
            QPoint(pump_center.x() + 10, pump_center.y() + 6),
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
        self.schematic = SchematicFrame(valve_request_cb, self)
        self.schematic.setFixedSize(1000, 750)
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
            curve = self.plot_widget.plot(pen=pen, name=f"P{p.id}")
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
            valve_request_cb=self.smc_worker.request,
            oxidize_request_cb=self.request_oxidize_iron
        )
        self.parameters_tab = ParametersTab()

        self.tabs.addTab(self.control_tab, "Control & Schematic")
        self.tabs.addTab(self.parameters_tab, "Parameters & Configuration")

    def request_oxidize_iron(self):
        self.proc_worker.request("oxidise_iron")

    def handle_pressure_update(self, vals: list):
        masked_vals = []
        for i, val in enumerate(vals):
            if i < len(self.control_tab.schematic.pressures):
                p_btn = self.control_tab.schematic.pressures[i]
                # If reactor toggle is off, force value to None
                if not p_btn.active:
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
    keller_worker_thread.update.connect(window.handle_pressure_update)
    tm_worker_thread.update.connect(window.handle_temperature_update)
    smc_worker_thread.update.connect(window.handle_valve_status_update)

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
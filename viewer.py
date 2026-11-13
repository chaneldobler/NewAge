import sys
import json
import time
import os
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QFrame, QComboBox, QFileDialog, QGridLayout, QTableView, QHeaderView, QMessageBox
from PySide6.QtGui import QStandardItem, QStandardItemModel, QFont, QColor
from PySide6.QtCore import Qt
import pyqtgraph as pg
import keller, smc, tm, peltier, tcpip
import worker
import procedures
import schematic
import components as c
import database as db
import control

class Viewer(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.graph = control.History(self)
        self.table = control.Table(self)
        self.logging = control.Logging(self)

        self.logging.save.clicked.connect(lambda: self.save(time.time()))
        self.logging.load.clicked.connect(self.load)
        self.logging.store.clicked.connect(self.table.store)

        self.logging.default.clicked.connect(self.graph.default)
        self.logging.auto.clicked.connect(self.graph.auto)

        self.container = QGridLayout(self)
        self.container.addWidget(self.graph, 0, 0)
        self.container.addWidget(self.table, 1, 0)
        self.container.addWidget(self.logging, 0, 1, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    def load(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Data Folder",
            "", 
            QFileDialog.Option.ShowDirsOnly,
        )

        if path:
            self.table.load(path)
            self.graph.load(path)
    
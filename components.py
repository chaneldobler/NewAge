import sys

from PySide6.QtWidgets import QLabel, QPushButton, QFrame, QGridLayout, QWidget, QApplication, QSizePolicy
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

styleSheet = f"""
    QPushButton {{
        border: 1px solid grey;
    }}
    QPushButton:hover {{
        color: white;
        background-color: grey;
    }}
    QPushButton:pressed {{
        color: white;
        background-color: grey;
    }}
    QFrame {{
        background-color: white;
    }}
    QWidget {{
        margin: 6px;
        padding: 6px;
        font-size: 20px
    }}
    Title {{
        color: white;
        background-color: grey;
        padding: 12px;
        font-size: 22px;
        font-weight: bold;
    }}
"""

class Title(QLabel):
    pass

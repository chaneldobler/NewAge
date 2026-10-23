import sys

from PySide6.QtWidgets import QLabel, QPushButton, QFrame, QGridLayout, QWidget, QApplication, QSizePolicy
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

styleSheet = f"""
    QWidget {{
        margin: 4px;
        padding: 8px;
        font-size: 20px
    }}
    QFrame {{
        background-color: white;
    }}
    QPushButton {{
        color: black;
        background-color: white;
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
    QLabel {{
        color: black;
        background-color: white;
        border: 1px solid grey;
    }}
    Title {{
        color: white;
        background-color: grey;
        font-size: 22px;
        font-weight: bold;
    }}
"""

class Title(QLabel):
    pass

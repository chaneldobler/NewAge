from PySide6.QtWidgets import QLabel, QFrame, QPushButton, QGridLayout

styleSheet = """
    QWidget {
        margin: 1px;
        padding: 4px;
        font-size: 16px;
    }
    QFrame {
        background-color: white;
    }
    QPushButton {
        color: black;
        background-color: #eeeeee;
        border: 1px solid grey;
    }
    QPushButton:hover {
        color: white;
        background-color: grey;
    }
    QPushButton:pressed {
        color: white;
        background-color: grey;
    }
    QLabel {
        color: black;
        background-color: white;
    }
    QLineEdit {
        border: 1px solid grey;
        background-color: #eeeeee;
    }
    Title {
        color: white;
        background-color: grey;
        font-size: 18px;
        font-weight: bold;
    }
    Body {
        border: 1px solid grey;
    }
"""

class Title(QLabel):
    pass

class Body(QLabel):
    pass

class Button(QFrame):
    def __init__(self, parent=None, name="Button"):
        super().__init__(parent)
        self.parent = parent
        self.name = name

        self.button = QPushButton(self.name)

        self.container = QGridLayout(self)
        self.container.addWidget(self.button, 0, 0)

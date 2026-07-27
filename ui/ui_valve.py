import sys
from hardware import smc
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QGridLayout
from PySide6.QtCore import QSize, Qt

class UIValve:
    def __init__(self, parent, layout, smcdevnet, nr):
        self.parent = parent
        self.smcdevnet = smcdevnet
        self.nr = nr
        self.status = smcdevnet.get_status(self.nr)

        self.btn = QPushButton(f"{self.nr}", parent)
        self.btn.setFixedSize(QSize(40, 40))
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

        self.btn.clicked.connect(self.toggle_on_off)

        row = ((nr - 1) // 5) + 1
        col = (nr - 1) % 5
        layout.addWidget(self.btn, row, col, Qt.AlignmentFlag.AlignCenter)

    def toggle_on_off(self):
        self.status = self.smcdevnet.get_status(self.nr)
        if self.status == 0:
            self.smcdevnet.open_valve(self.nr)
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
        else:
            self.smcdevnet.close_valve(self.nr)
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
        
if __name__ == "__main__":
    smcdevnet = smc.SmcDevNet()
    smcdevnet.start()

    app = QApplication(sys.argv)
    window = QWidget()
    grid = QGridLayout(window)
    valve = UIValve(window, grid, smcdevnet, 1)

    window.show()
    app.exec()

    smcdevnet.stop()
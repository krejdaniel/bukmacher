from PySide6.QtWidgets import QApplication
from windows.home import HomeWindow

import sys

app = QApplication(sys.argv)

window = HomeWindow()
window.show()

app.exec()
import sys
from PyQt5.QtWidgets import QApplication
from rfn_app.oapp.mon.rfn_mon_viewer import RfnMonWindow

app = QApplication(sys.argv)
w = RfnMonWindow("test-config.json")
w.show()
sys.exit(app.exec_())
import os
import sys
from PyQt5.QtWidgets import QApplication
from rfn_app.oapp.mon.rfn_mon_viewer import RfnMonWindow, tango_host

if "TANGO_HOST" not in os.environ:
    os.environ["TANGO_HOST"] = tango_host

app = QApplication(sys.argv)
w = RfnMonWindow("RfnMonViewer-config.json")
w.show()
sys.exit(app.exec_())
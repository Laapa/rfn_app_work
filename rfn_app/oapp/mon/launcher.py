"""
Start of the RF monitor (Монитор ВЧ2) as a separate program.

After "pip install" this is what the rfn-mon-viewer.exe launcher runs.

Work folder: Documents\\RfnMonViewer of the current user, created on the first start.
  - RfnMonViewer-config.json  config; on the first start the default config
                              from the package is copied here, then this copy is used
  - data\\                     measurement files
  - *-lines.json              saved line selection
  - RfnMonViewer-errors.log   unexpected errors
The installed package itself is never written to.
"""
import os
import shutil
import sys
import traceback
from datetime import datetime

from PyQt5.QtWidgets import QApplication, QMessageBox

from rfn_app.oapp.mon.rfn_mon_viewer import RfnMonWindow, tango_host

CONFIG_NAME = "RfnMonViewer-config.json"
# default config shipped inside the package, next to this file
DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_NAME)
WORK_DIR_NAME = "RfnMonViewer"
ERROR_LOG_NAME = "RfnMonViewer-errors.log"


def work_dir():
    """Documents\\RfnMonViewer, or the home folder if there is no Documents"""
    home = os.path.expanduser("~")
    docs = os.path.join(home, "Documents")
    if not os.path.isdir(docs):
        docs = home
    return os.path.join(docs, WORK_DIR_NAME)


def install_error_handler(log_name):
    """
    Unexpected errors: write them to the log and show a message once,
    instead of closing the program (there is no console window to see them).
    """
    seen = set()

    def handler(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        if text in seen:        # the same error every second: report it once
            return
        seen.add(text)
        try:
            with open(log_name, "a", encoding="utf-8") as f:
                f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S}\n{text}\n")
        except OSError:
            pass
        if sys.stderr is not None:      # no console when started from the .exe
            sys.stderr.write(text)
        QMessageBox.critical(None, "Ошибка программы",
                             f"{exc_type.__name__}: {exc}\n\nПрограмма продолжает работу.\n"
                             f"Подробности записаны в файл:\n{log_name}")

    sys.excepthook = handler


def main():
    if "TANGO_HOST" not in os.environ:
        os.environ["TANGO_HOST"] = tango_host

    app = QApplication(sys.argv)

    folder = work_dir()
    config = os.path.join(folder, CONFIG_NAME)
    first_start = False
    try:
        os.makedirs(folder, exist_ok=True)
        if not os.path.exists(config):
            shutil.copyfile(DEFAULT_CONFIG, config)
            first_start = True
    except OSError as e:
        QMessageBox.critical(None, "Монитор ВЧ2",
                             f"Не удалось подготовить рабочую папку:\n{folder}\n\n{e}")
        return 1

    # "data/" from the config and the error log go to the work folder
    os.chdir(folder)
    install_error_handler(os.path.join(folder, ERROR_LOG_NAME))

    w = RfnMonWindow(config)
    w.show()
    w.statusBar().showMessage(f"Ready. Рабочая папка: {folder}")
    if first_start:
        QMessageBox.information(w, "Монитор ВЧ2",
                                f"Создана рабочая папка:\n{folder}\n\n"
                                f"В ней конфиг {CONFIG_NAME} (его можно править),\n"
                                f"папка data с файлами измерений и сохранённый выбор линий.")
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())

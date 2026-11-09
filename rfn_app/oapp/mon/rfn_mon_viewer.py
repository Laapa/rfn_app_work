import os
import sys
import argparse
import traceback
import pyqtgraph as pg
import numpy as np
import time
from datetime import datetime, timedelta
import json
import tango

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QGroupBox, QGridLayout, \
    QLabel, QLineEdit, QApplication, QCheckBox, QMainWindow, QHBoxLayout, QComboBox, \
    QFileDialog, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtCore import QTimer, QDateTime
from PyQt5.QtWidgets import QWidget, QPushButton

from rfn_app.oapp.mon.rfn_mon_data import RfnMonData, TangoConnError, TangoErr
from rfn_app.oapp.mon.rfn_mon_plot_dialog import PlotLinesDialog

tango_host = "10.18.113.66:10000"

# стиль линии по порядку на графике: сплошная, штрих, точки, штрих-точка, штрих-две точки
LINE_STYLES = [Qt.SolidLine, Qt.DashLine, Qt.DotLine, Qt.DashDotLine, Qt.DashDotDotLine]
# цвет кривых по резонатору (яркие, под чёрный фон графиков)
RES_COLORS = ["#4da6ff", "#ff9933", "#66dd66", "#ff5555",
              "#bb88ff", "#ffee55", "#ff77cc", "#44ddcc"]

class RfnMonState(object):
    Idle = 0
    Mon = 1


class RfnMonWindow(QMainWindow):
    def __init__(self, cfg_name_json, parent = None):
        super(RfnMonWindow, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)  

        vbox_plots = QVBoxLayout()

        self.guiplots = []
        self.date_axises = []
        self.dlines = []
        self.curve_keys = []        
        self.file_data = None
        self.devices = None
        self.devices_attr = None

        self.f_name_templ_date = "%Y-%m-%d_%H-%M-%S.dat"
        self.f_names = []   # file per resonator, None for inactive ones
        self.active = []    # active[r] = True if resonator r is polled
        self.statusMsg = "Start: "
        self.state = RfnMonState.Idle

        self.read_cfg(cfg_name_json)

        # создаем требуемое количество графиков (PlotWidget)
        for i in range(self.plot_qty):
            date_axis = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation = 'bottom')
            lines_n = len(self.plot_data_cfg[i])
            legend_col_count = ((lines_n-1) // 4) + 1

            guiplot = pg.PlotWidget()
            guiplot.showGrid(x=True, y=True)
            guiplot.setTitle(self.plot_titles[i], color='b', size='14pt')
            guiplot.setAxisItems(axisItems = {'bottom': date_axis})
            guiplot.setYRange(self.plot_scale[i][0], self.plot_scale[i][1]) 
            guiplot.addLegend(colCount=legend_col_count)
            guiplot.setClipToView(True)
            self.set_x_range(guiplot)
            # график с маленькой кнопкой настроек в правом верхнем углу
            plot_box = QGridLayout()
            plot_box.setContentsMargins(0, 0, 0, 0)
            plot_box.addWidget(guiplot, 0, 0)
            btn_cfg = QPushButton("⚙")
            btn_cfg.setFixedSize(28, 28)
            btn_cfg.setToolTip("Линии на графике")
            btn_cfg.clicked.connect(lambda checked, p=i: self.edit_plot_lines(p))
            plot_box.addWidget(btn_cfg, 0, 0, Qt.AlignTop | Qt.AlignRight)
            vbox_plots.addLayout(plot_box)

            self.dlines.append([])
            self.curve_keys.append([])            
            self.guiplots.append(guiplot)
            self.date_axises.append(date_axis)

        gb_plots = QGroupBox("Пример компоновки Grid Layout")
        gb_plots.setLayout(vbox_plots)
        self.rebuild_lines()

        # top row: number of resonators, Mon: Start / Mon: Stop, read from file
        self.lbl_cav_info = QLabel("Резонаторы: ---")
        self.lbl_cav_info.setStyleSheet('''font: 14pt "MS Shell Dlg 2"''')

        self.btn_mon_start = QPushButton("Mon: Start")
        self.btn_mon_start.clicked.connect(self.mon_start)

        self.btn_mon_stop = QPushButton("Mon: Stop")
        self.btn_mon_stop.clicked.connect(self.mon_stop)

        self.btn_read_file = QPushButton("Read from file")
        self.btn_read_file.clicked.connect(self.read_file)

        hbox_sys = QHBoxLayout()
        hbox_sys.addWidget(self.lbl_cav_info)
        hbox_sys.addWidget(self.btn_mon_start)
        hbox_sys.addWidget(self.btn_mon_stop)
        hbox_sys.addWidget(self.btn_read_file)

        # создаем главное окно
        container = QWidget()

        vbox = QVBoxLayout(container)
        vbox.addLayout(hbox_sys)
        vbox.addWidget(gb_plots)

        self.setCentralWidget(container)
        self.setWindowTitle("Монитор ВЧ2")
        self.statusBar().showMessage('Ready')

        # Создаем класс с данными и таймер для получения данных и отрисовки              
        # по одному объекту данных на каждый резонатор, в том же порядке, что в json
        self.datas = [RfnMonData(self.x_len, self.devices_attr) for _ in self.res_names]

        self.timer = QTimer()  
        self.timer.timeout.connect(self.timerEvent)

    def read_cfg(self, config_file):
        with open(config_file, 'r') as file:
            cfg_json = json.load(file)        

        self.x_len = cfg_json["x_len"] # количество точек
        self.timer_tick = cfg_json["timer_tick"]    # время опроса
        data_lines_cfg_raw = cfg_json["data_lines"]
        self.data_lines_cfg = list(data_lines_cfg_raw.values())
        plot_titles_raw = cfg_json["plots"]
        self.plot_titles = [val[0] for val in plot_titles_raw]
        self.plot_scale = [val[1] for val in plot_titles_raw]
        self.plot_data_cfg = [val[2] for val in plot_titles_raw]
        self.plot_qty = len(self.plot_titles) # количество виджетов для графиков
        self.f_dir = cfg_json["dir"]        
        self.devices = cfg_json["devices"]
        self.devices_attr = cfg_json["tango_attr"]
        # файл с выбором лежит рядом с конфигом: <имя конфига>-lines.json
        self.lines_file = os.path.splitext(os.path.abspath(config_file))[0] + "-lines.json"
        # имена резонаторов в порядке json и короткие названия для легенды ("rf2-1e1" -> "1e1")
        self.res_names = list(self.devices.keys())
        self.res_short = [name.split("-")[-1] for name in self.res_names]

        # выбор линий: selection[график][резонатор] = список номеров линий.
        # По умолчанию линии из json относятся только к первому резонатору
        self.selection = [[list(self.plot_data_cfg[p]) if r == 0 else []
                           for r in range(len(self.res_names))]
                          for p in range(self.plot_qty)]       
        # если есть сохранённый выбор, он заменяет выбор по умолчанию
        self.load_lines()
        # группы линий для столбцов в окне настроек: берём из "tango_attr", линии нумеруются подряд
        self.line_groups = []
        first = 0
        for group_name, attrs in self.devices_attr.items():
            self.line_groups.append((group_name, list(range(first, first + len(attrs)))))
            first = first + len(attrs)    

    def lines_ok(self, saved):
        """Проверяем, что прочитанное из файла похоже на правду"""
        if not isinstance(saved, list) or len(saved) != self.plot_qty:
            return False

        for plot_sel in saved:
            if not isinstance(plot_sel, dict):
                return False
            for res_name, mask in plot_sel.items():
                if not isinstance(mask, list):
                    return False
                for n in mask:
                    if not isinstance(n, int) or not 0 <= n < len(self.data_lines_cfg):
                        return False
                if len(mask) != len(set(mask)):
                    return False
        return True


    def load_lines(self):
        """Читаем сохранённый выбор. Если файла нет или он испорчен, остаётся выбор по умолчанию"""
        if not os.path.exists(self.lines_file):
            return

        try:
            with open(self.lines_file, "r") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            return

        if not self.lines_ok(saved):
            return

        # раскладываем по резонаторам из json; кого в файле нет, у того пусто
        self.selection = [[list(plot_sel.get(name, [])) for name in self.res_names]
                          for plot_sel in saved]


    def save_lines(self):
        """Записываем текущий выбор: для каждого графика словарь {резонатор: [линии]}"""
        data = [dict(zip(self.res_names, plot_sel)) for plot_sel in self.selection]
        try:
            with open(self.lines_file, "w") as f:
                json.dump(data, f)
        except OSError as e:
            self.show_error_window("Не удалось сохранить выбор линий", str(e))

    def rebuild_lines(self):
        """Убираем старые кривые и создаем заново по текущему выбору self.selection"""
        for i in range(self.plot_qty):
            for dline in self.dlines[i]:
                self.guiplots[i].removeItem(dline)

            idlines = []
            keys = []
            for r in range(len(self.res_names)):
                color = RES_COLORS[r % len(RES_COLORS)]
                for k, n_dat in enumerate(self.selection[i][r]):
                    line_cfg = self.data_lines_cfg[n_dat]
                    pen = pg.mkPen(color=color, width=2, style=LINE_STYLES[k % len(LINE_STYLES)])
                    dline = self.guiplots[i].plot(pen=pen,
                                                  symbolSize=line_cfg[1],
                                                  symbolBrush=color,
                                                  name=f"{self.res_short[r]}: {line_cfg[3]}")
                    idlines.append(dline)
                    keys.append((r, n_dat))
            self.dlines[i] = idlines
            self.curve_keys[i] = keys

            # legend: up to 4 entries per column, as at start
            legend = self.guiplots[i].getPlotItem().legend
            if legend is not None and hasattr(legend, "setColumnCount"):
                legend.setColumnCount(max(1, (len(idlines) - 1) // 4 + 1))


    def edit_plot_lines(self, p):
        """Настройка линий одного графика: p - номер графика"""
        line_names = [line_cfg[3] for line_cfg in self.data_lines_cfg]
        dlg = PlotLinesDialog(self.plot_titles[p], self.res_short, line_names,
                              self.line_groups, self.selection[p], self)
        if not dlg.exec_():
            return

        self.selection[p] = dlg.get_selection()
        self.rebuild_lines()
        self.redraw_all()
        self.save_lines()

    def set_x_range_all(self):
        for guiplot in self.guiplots:
            self.set_x_range(guiplot)


    def set_x_range(self, guiplot):
        # задаем макс и мин значения на оси X
        cur = datetime.now()
        x = []
        x.append(cur.timestamp())
        for i in range(self.x_len-1):
            x.append(cur.timestamp() + i*(self.timer_tick))
        guiplot.setXRange(x[0], x[self.x_len - 1])


    def timerEvent(self):
        # poll only active resonators; inactive ones keep empty buffers.
        # A failure of one resonator must not stop the others.
        lost_now = []   # list of (resonator name, short reason) lost in this tick
        for r, data in enumerate(self.datas):
            if not self.active[r]:
                continue
            try:
                data.get_data()
            except Exception as e:
                self.drop_partial_sample(data)
                self.active[r] = False
                lost_now.append((self.res_names[r], self.short_reason(self.error_text(e))))

        all_dat = [[data.xt, data.y] for data in self.datas]
        for i in range(self.plot_qty):
            self.plot_graph(i, all_dat)
        self.updateStatusBar()
        for r, data in enumerate(self.datas):
            if self.active[r]:
                data.add_to_file_last(self.f_names[r])

        if lost_now:
            self.on_resonators_lost(lost_now)


    def drop_partial_sample(self, data):
        """
        Undo the half-written sample after get_data() failed in the middle.

        get_data() appends the time to xt first and then appends values to y
        one by one (y[0], y[1], ...). data.dump holds [time, values read so far],
        so len(dump) - 1 is how many y lists got a new value before the failure.
        """
        n_read = max(len(data.dump) - 1, 0)
        if data.xt:
            data.xt.pop()
        for i in range(min(n_read, len(data.y))):
            if data.y[i]:
                data.y[i].pop()
        # when the buffer was full, the lists that were not read still keep one
        # older point at the front: cut every list to the length of xt
        n = len(data.xt)
        for i in range(len(data.y)):
            if len(data.y[i]) > n:
                data.y[i] = data.y[i][len(data.y[i]) - n:]


    def error_text(self, e):
        """Readable text of an exception; for Tango errors join the descriptions"""
        if isinstance(e, tango.DevFailed):
            return "\n".join(err.desc for err in e.args)
        return f"{type(e).__name__}: {e}"


    def on_resonators_lost(self, lost_now):
        """Resonators stopped answering during monitoring: update label, warn once"""
        n_ok = sum(self.active)
        n_all = len(self.res_names)
        lost_text = "\n".join(f"{name}: {reason}" for name, reason in lost_now)

        if n_ok == 0:
            # nobody left to poll: stop monitoring
            self.timer.stop()
            self.state = RfnMonState.Idle
            self.lbl_cav_info.setText("Резонаторы: ---")
            self.statusBar().showMessage("Monitor stop: нет доступных резонаторов")
            self.show_warning(f"Потеряна связь со всеми резонаторами, мониторинг остановлен:"
                              f"\n\n{lost_text}")
            return

        self.lbl_cav_info.setText(f"Резонаторы: {n_ok} из {n_all}")
        self.show_warning(f"Потеряна связь с резонаторами, они больше не опрашиваются "
                          f"(до перезапуска Mon: Start):\n\n{lost_text}")


    def show_warning(self, text):
        """Non-modal warning: the timer keeps working while the window is open"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("Warning")
        msg_box.setText(text)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.setAttribute(Qt.WA_DeleteOnClose)
        msg_box.setModal(False)
        msg_box.show()


    def plot_graph(self, index, all_dat):
        """
        Обновляем данные для всех кривых одного графика

        index   - какой график отрисовывать
        all_dat - список [время, ряды] по каждому резонатору
        """
        # resonator 0 may be unavailable, so look at the longest time axis
        if max(len(dat[0]) for dat in all_dat) >= self.x_len:
            self.guiplots[index].enableAutoRange(axis='x', enable=True)

        for curve, (r, n_dat) in zip(self.dlines[index], self.curve_keys[index]):
            t, y = all_dat[r]
            curve.setData(x=t, y=y[n_dat])


    def current_data(self):
        """Что сейчас показывать: данные из файла или накопленные данные всех резонаторов"""
        if self.file_data is not None:
            return self.file_data
        return [[data.xt, data.y] for data in self.datas]


    def redraw_all(self):
        """Перерисовать все графики текущими данными"""
        all_dat = self.current_data()
        for i in range(self.plot_qty):
            self.plot_graph(i, all_dat)
    def updateStatusBar(self):
        now = datetime.now()
        delta_ts = round(now.timestamp() - self.start.timestamp())
        delta_str = time.strftime("%H:%M:%S", time.gmtime(delta_ts))
        self.statusBar().showMessage(self.statusMsg + " [{0}]".format(delta_str))


    def mon_start(self):
        if (self.state == RfnMonState.Idle):
            # try every resonator; a failed one is remembered, not fatal
            self.active = []
            failed = []     # list of (resonator name, short reason)
            for name, data in zip(self.res_names, self.datas):
                try:
                    data.connect(self.devices[name])
                    self.active.append(True)
                except (TangoConnError, TangoErr) as e:
                    self.active.append(False)
                    failed.append((name, self.short_reason(str(e))))

            n_ok = sum(self.active)
            n_all = len(self.res_names)
            failed_text = "\n".join(f"{name}: {reason}" for name, reason in failed)
            if n_ok == 0:
                self.show_error_window("Нет доступных резонаторов, мониторинг не запущен",
                                       failed_text)
                return

            for data in self.datas:
                data.rst_data()
            self.file_data = None
            self.set_x_range_all()

            self.start = datetime.now()
            start_str = self.start.strftime("%Y-%m-%d %H:%M:%S")

            # each active resonator has its own file; inactive ones get None
            self.f_names = []
            for r, (name, data) in enumerate(zip(self.res_names, self.datas)):
                if self.active[r]:
                    f_name = self.get_full_path(name)
                    data.write_file_head(self.start, f_name, name)
                    self.f_names.append(f_name)
                else:
                    self.f_names.append(None)

            self.lbl_cav_info.setText(f"Резонаторы: {n_ok} из {n_all}")
            self.statusMsg = "Start at {0}".format(start_str, 0)
            self.statusBar().showMessage(self.statusMsg)
            self.timer.start(int(self.timer_tick * 1000))
            self.state = RfnMonState.Mon

            # one window for all unavailable resonators, after the timer is started
            if failed:
                self.show_info_window(f"Недоступны резонаторы ({n_all - n_ok} из {n_all}), "
                                      f"мониторинг идёт без них:\n\n{failed_text}")
        else:
            self.show_info_window("Мониторинг уже запущен")


    def short_reason(self, msg):
        """Short reason from a Tango error text: prefer the line naming the device
        ("Failed to connect to device rf2/1e1/mod"), otherwise the first line"""
        lines = [line.strip() for line in msg.splitlines() if line.strip()]
        if not lines:
            return "нет ответа"
        reason = lines[0]
        for line in lines:
            if "device" in line.lower():
                reason = line
                break
        if len(reason) > 120:
            reason = reason[:117] + "..."
        return reason


    def mon_stop(self):
        if (self.state == RfnMonState.Mon):
            self.timer.stop()
            self.statusBar().showMessage("Monitor stop.")
            self.state = RfnMonState.Idle
            self.lbl_cav_info.setText(f"Резонаторы: ---")
        else:
            self.show_info_window("Мониторинг не запущен")


    def get_full_path(self, res_name):
        f_dir = self.f_dir
        if self.f_dir != "":
            if (self.f_dir[-1] != "/"):
                f_dir = self.f_dir + "/"
            os.makedirs(f_dir, exist_ok=True)

        return f_dir + f"{res_name}_" + self.start.strftime(self.f_name_templ_date)

    
    def read_file(self):
        if (self.state == RfnMonState.Idle):
            # several files can be selected: one per resonator
            fnames = QFileDialog.getOpenFileNames(self, 'Open files', self.f_dir,
                                                  "Data files (*.dat);;All files (*)")[0]
            if not fnames:
                return

            n_lines = len(self.data_lines_cfg)
            empty = [[], [[] for _ in range(n_lines)]]
            file_data = [empty for _ in self.res_names]
            loaded = {}     # resonator name -> file name
            problems = []   # list of "file: reason"
            for fname in fnames:
                base = os.path.basename(fname)
                # the resonator is the beginning of the file name: "rf2-1e1_2026-10-30_11-07-15.dat"
                res_name = base.split("_")[0]
                if res_name not in self.res_names:
                    problems.append(f"{base}: не удалось определить резонатор по имени файла")
                    continue
                try:
                    # reading does not depend on the resonator, any data object will do
                    xt, y = self.datas[0].read_from_file(fname)
                except (OSError, ValueError, IndexError) as e:
                    problems.append(f"{base}: не удалось прочитать ({type(e).__name__}: {e})")
                    continue
                # a file with fewer columns: the missing lines stay empty
                while len(y) < n_lines:
                    y.append([])
                if res_name in loaded:
                    problems.append(f"{base}: для {res_name} уже выбран "
                                    f"{os.path.basename(loaded[res_name])}, берём этот")
                file_data[self.res_names.index(res_name)] = [xt, y]
                loaded[res_name] = fname

            if not loaded:
                self.show_info_window("Ни один файл не прочитан:\n\n" + "\n".join(problems))
                return

            self.file_data = file_data
            self.redraw_all()
            for i in range(self.plot_qty):
                self.guiplots[i].enableAutoRange(axis='x', enable=True)

            self.lbl_cav_info.setText(f"Из файлов: {len(loaded)} из {len(self.res_names)}")
            if len(loaded) == 1:
                self.statusBar().showMessage("Read from file {}".format(list(loaded.values())[0]))
            else:
                self.statusBar().showMessage("Read from {} files".format(len(loaded)))
            if problems:
                self.show_info_window("Не все файлы прочитаны:\n\n" + "\n".join(problems))
        else:
            self.show_info_window("Для чтения из файла необходимо остановить мониторинг")


    def show_info_window(self, info):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Information")
        msg_box.setText(info)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()


    def show_error_window(self, info, msg):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Critical")
        msg_box.setText(info)
        msg_box.setInformativeText(msg)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()        

# config file name used when none is given on the command line
DEFAULT_CONFIG = "RfnMonViewer-config.json"
# project folder: rfn_app/oapp/mon/rfn_mon_viewer.py -> three levels up
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def find_config(name):
    """Config path: as given, else in the current folder, else in the project folder"""
    if name:
        return os.path.abspath(name)
    for folder in (os.getcwd(), PROJECT_DIR):
        path = os.path.join(folder, DEFAULT_CONFIG)
        if os.path.exists(path):
            return path
    return None


def install_error_handler(log_name):
    """
    Unexpected errors: write them to a log file and show a message once,
    instead of closing the program. Used only for the standalone start
    (main), the bigger window that imports RfnMonWindow is not affected.
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
        if sys.stderr is not None:      # pythonw has no console
            sys.stderr.write(text)
        QMessageBox.critical(None, "Ошибка программы",
                             f"{exc_type.__name__}: {exc}\n\nПрограмма продолжает работу.\n"
                             f"Подробности записаны в файл:\n{log_name}")

    sys.excepthook = handler


def main():
    """Standalone start: python -m rfn_app.oapp.mon.rfn_mon_viewer [config] [--tango-host HOST]"""
    parser = argparse.ArgumentParser(description="Монитор ВЧ2")
    parser.add_argument("config", nargs="?", default=None,
                        help=f"конфиг (по умолчанию {DEFAULT_CONFIG} в текущей папке или в папке программы)")
    parser.add_argument("--tango-host", default=None,
                        help=f"TANGO_HOST (по умолчанию из окружения или {tango_host})")
    args = parser.parse_args()

    if args.tango_host:
        os.environ["TANGO_HOST"] = args.tango_host
    elif "TANGO_HOST" not in os.environ:
        os.environ["TANGO_HOST"] = tango_host

    app = QApplication(sys.argv)

    config = find_config(args.config)
    if config is None or not os.path.exists(config):
        QMessageBox.critical(None, "Монитор ВЧ2",
                             f"Не найден файл конфигурации:\n{config or DEFAULT_CONFIG}")
        sys.exit(1)

    # work next to the config: the "data/" folder and the log go there,
    # whatever folder the program was started from (e.g. from a shortcut)
    os.chdir(os.path.dirname(config))
    install_error_handler(os.path.join(os.path.dirname(config), "RfnMonViewer-errors.log"))

    w = RfnMonWindow(config)
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

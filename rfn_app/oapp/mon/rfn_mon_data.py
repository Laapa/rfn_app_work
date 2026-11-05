import sys
import pyqtgraph as pg
import numpy as np
import math
import time
from datetime import datetime, timedelta
import random
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QGroupBox, QGridLayout, \
    QLabel, QLineEdit, QApplication, QCheckBox, QMainWindow, QHBoxLayout, QComboBox, \
    QFileDialog, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtCore import QTimer, QDateTime
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox, QVBoxLayout, QPushButton

import json
import tango


class TangoConnError(Exception):
    pass


class TangoErr(Exception):
    pass


class RfnMonData():
    def __init__(self, x_len, devices_attr):
        self.attr_list = [list(x) for x in devices_attr.values()]

        self.tango_ds = []
        self.xt_size = x_len
        self.xt = []
        self.y = []

        tot_len = 0
        for val in self.attr_list:
            tot_len = tot_len + len(val)

        for _ in range(tot_len):
            self.y.append([])        

        self.dump_str = ""
        self.dump = []


    def connect(self, devices_path):
        # удаляем tango объекты если список tango_ds не пуст
        if self.tango_ds:
            for dev in self.tango_ds:
                del dev

            self.tango_ds.clear()

        # подключаемся к device server-ам
        try:
            for path in devices_path:
                tango_ds = tango.DeviceProxy(path)
                tango_ds.ping()
                self.tango_ds.append(tango_ds)
        # except tango.ConnectionFailed as df:
        #     raise TangoConnError("Unable connect to tango: {0}".format(path))
        except tango.DevFailed as df:
            msg = ""
            for error in df.args:
                msg = msg + f'{error.desc}\n'
            raise  TangoErr(msg)


    def get_attr(self, tdev, index, attr):
            read_attr = tdev.read_attribute(attr)
            val = read_attr.value
            self.y[index].append(val)
            self.y[index] = self.y[index][-self.xt_size:]
            self.dump.append(val)


    def get_data(self):
        self.dump.clear()

        cur = datetime.now().timestamp()
        self.xt.append(cur)
        self.xt = self.xt[-self.xt_size:]
        self.dump.append(cur)

        offset = 0
        for j in range(len(self.attr_list)):
            for i in range(len(self.attr_list[j])):
                self.get_attr(self.tango_ds[j], i + offset, self.attr_list[j][i])
            offset = offset + len(self.attr_list[j])

        self.dump_str = ";".join([str(val) for val in self.dump])

        return [self.xt, self.y]


    def rst_data(self):
        self.xt.clear()

        for val in self.y:
            val.clear()


    def write_file_head(self, date, f_name, tango_dev):
        with open(f_name, 'w') as file:
            attr_list_single_list = []
            for val in self.attr_list:
                attr_list_single_list = attr_list_single_list + val

            file.write("// [{}] Start at {} \n".format(tango_dev, date.strftime("%Y-%m-%d %H:%M:%S")))
            head = "// time; " + "; ".join(attr_list_single_list) + '\n'
            file.write (head)


    def add_to_file_last(self, f_name):
        with open(f_name, 'a') as file:
            file.write(self.dump_str + '\n')
        

    def read_from_file(self, f_name):
        with open(f_name, 'r') as file:
            lines = file.readlines()

        xt = []
        # определяем по первой стоке в файле количество столбцов с данными
        # и создаем пустой список списков
        y = []
        y_qty = len(lines[1].replace("\n", "").split(";"))
        for i in range(1, y_qty):
            y.append([])

        # пропускаем строки с заголовком и обрабатываем данные
        for line in lines[2:]:
            x = line.replace("\n", "").split(";")
            xt.append(float(x[0]))

            for i in range(1, y_qty):
                y[i-1].append(float(x[i]))

        return [xt, y]
        
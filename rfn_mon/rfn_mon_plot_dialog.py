from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
                             QTabWidget, QWidget, QPushButton, QDialogButtonBox)


class PlotLinesDialog(QDialog):
    """
    Окно настройки одного графика: какие линии каких резонаторов на нём рисовать.

    plot_title - название графика
    res_names  - короткие названия резонаторов (по вкладке на каждый)
    line_names - названия всех линий (по номеру линии)
    groups     - группы для столбцов: список (название группы, [номера линий])
    selection  - текущий выбор: selection[резонатор] = список номеров линий
    """
    def __init__(self, plot_title, res_names, line_names, groups, selection, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Настройка графика: {plot_title}")

        self.checks = []    # checks[r][n] = галочка линии n у резонатора r
        tabs = QTabWidget()
        for r, res_name in enumerate(res_names):
            page, checks = self.make_page(line_names, groups, selection[r])
            self.checks.append(checks)
            tabs.addTab(page, res_name)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        vbox = QVBoxLayout(self)
        vbox.addWidget(tabs)
        vbox.addWidget(buttons)


    def make_page(self, line_names, groups, chosen):
        """Одна вкладка: столбцы-группы с галочками и кнопки "Все" / "Ничего" """
        checks = {}
        columns = QHBoxLayout()
        for group_name, line_ids in groups:
            box = QGroupBox(group_name)
            col = QVBoxLayout(box)
            for n in line_ids:
                check = QCheckBox(line_names[n])
                check.setChecked(n in chosen)
                col.addWidget(check)
                checks[n] = check
            col.addStretch()
            columns.addWidget(box)

        btn_all = QPushButton("Все")
        btn_none = QPushButton("Ничего")
        btn_all.clicked.connect(lambda: self.set_all(checks, True))
        btn_none.clicked.connect(lambda: self.set_all(checks, False))
        row = QHBoxLayout()
        row.addWidget(btn_all)
        row.addWidget(btn_none)
        row.addStretch()

        page = QWidget()
        vbox = QVBoxLayout(page)
        vbox.addLayout(row)
        vbox.addLayout(columns)
        return page, checks


    def set_all(self, checks, state):
        for check in checks.values():
            check.setChecked(state)


    def get_selection(self):
        # для каждого резонатора номера отмеченных линий по возрастанию
        return [[n for n, check in checks.items() if check.isChecked()]
                for checks in self.checks]
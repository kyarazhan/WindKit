"""机型库：机型数据 + 扫风面积自动计算 + 增删改。"""

import pandas as pd
from PySide6.QtWidgets import (QGridLayout, QMessageBox, QPushButton, QWidget)

from core.turbine import TurbineDB
from ui.base_tab import ModuleTab
from ui.widgets import DataTableWithActions


class TurbineDbTab(ModuleTab):
    TITLE = '机型库'

    def __init__(self):
        super().__init__(hint='S = π(D/2)²，s = S/P；内置机型可增删改')

        self.db = TurbineDB()

        add_form = QGridLayout()
        w0, _ = self.add_input('vendor', '厂商', '金风')
        w1, _ = self.add_input('model', '机型', 'GW191-5000')
        w2, _ = self.add_input('d', '叶轮直径', 191)
        w3, _ = self.add_input('p', '容量', 5000)
        add_btn = QPushButton('添加机型')
        add_btn.setProperty('primaryBtn', True)
        add_btn.clicked.connect(self.add)
        add_form.addWidget(w0, 0, 0)
        add_form.addWidget(w1, 0, 1)
        add_form.addWidget(w2, 0, 2)
        add_form.addWidget(w3, 0, 3)
        add_form.addWidget(add_btn, 0, 4)
        wrap = QWidget()
        wrap.setLayout(add_form)
        self.root_lay.addWidget(wrap)

        del_btn = QPushButton('删除选中行（输入行号）')
        del_btn.setProperty('secondaryBtn', True)
        del_btn.clicked.connect(self.remove)
        w_idx, _ = self.add_input('idx', '行号', '')
        del_row = QGridLayout()
        del_row.addWidget(w_idx, 0, 0)
        del_row.addWidget(del_btn, 0, 1)
        wrap2 = QWidget()
        wrap2.setLayout(del_row)
        self.root_lay.addWidget(wrap2)

        self.table = DataTableWithActions()
        self.root_lay.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        df = pd.DataFrame(self.db.turbines)
        df = df.rename(columns={'vendor': '厂商', 'model': '机型', 'd': '叶轮直径',
                                'p': '容量', 's': '扫风面积(m²)', 'sp': '单位扫风(m²/kW)'})
        self.table.show_df(df)
        self.db.save()

    def add(self):
        try:
            d = self.get_float('d')
            p = self.get_float('p')
        except ValueError:
            QMessageBox.warning(self, '输入无效', '直径与容量必须是数字')
            return
        self.db.add(self.get_input('vendor'), self.get_input('model'), d, p)
        self.refresh()

    def remove(self):
        try:
            idx = int(self.get_input('idx')) - 1
        except ValueError:
            return
        if 0 <= idx < len(self.db.turbines):
            self.db.remove(idx)
            self.refresh()


TAB = TurbineDbTab

"""湍流曲线：1m/s bin TI 表 + IEC A/B 类对比。"""

import json
import os

import pandas as pd

from core.paths import resource_path
from ui.base_tab import ModuleTab
from ui.widgets import CsvImportButton, DataTableWithActions, MetricCard

SRC = resource_path('data', 'samples', 'turb_sample.json')


class TurbulenceTab(ModuleTab):
    TITLE = '湍流曲线'

    def __init__(self):
        super().__init__(hint='1m/s bin：Mean/Std/Characteristic/Peak TI + σ1/Vhub A/B 类对比')

        from PySide6.QtWidgets import QGridLayout, QWidget
        top = QGridLayout()
        self.import_btn = CsvImportButton()
        self.import_btn.clicked.connect(self._on_import)
        top.addWidget(self.import_btn, 0, 0)
        wrap = QWidget()
        wrap.setLayout(top)
        self.root_lay.addWidget(wrap)

        self.c_15 = MetricCard('TI @15m/s')
        self.c_class = MetricCard('IEC 湍流等级')
        cards = QGridLayout()
        cards.addWidget(self.c_15, 0, 0)
        cards.addWidget(self.c_class, 0, 1)
        wrap2 = QWidget()
        wrap2.setLayout(cards)
        self.root_lay.addWidget(wrap2)

        self.table = DataTableWithActions()
        self.root_lay.addWidget(self.table, 1)
        self.rows = None
        if os.path.exists(SRC):
            self.rows = json.load(open(SRC))
        self.compute()

    def _on_import(self):
        if hasattr(self.import_btn, 'pairs') and getattr(self.import_btn, 'pairs', None):
            self.rows = [[p[0], 0, 0, p[1], 0, 0, 0, 0] for p in self.import_btn.pairs]
            self.import_btn.pairs = None
            self.compute()

    def compute(self):
        if not self.rows:
            return
        cols = ['Bin 中值 (m/s)', '样本数', '频率 (%)', 'Mean TI', 'Std TI',
                'Char TI', 'Peak TI', 'Mean TI 标准误']
        df = pd.DataFrame(self.rows, columns=cols)
        df['σ1/Vhub [A]'] = df['Std TI']
        df['σ1[B]/Vhub'] = (df['Std TI'] * 0.7059).round(4)
        self.table.show_df(df)
        tis = {r[0]: r[3] for r in self.rows if r[0] is not None}
        if tis:
            keys = sorted(tis)
            v_lo = max(k for k in keys if k <= 15)
            v_hi = min(k for k in keys if k >= 15)
            if v_lo == v_hi:
                ti15 = tis[v_lo]
            else:
                t = (15 - v_lo) / (v_hi - v_lo)
                ti15 = tis[v_lo] * (1 - t) + tis[v_hi] * t
            self.c_15.set_value(f'{ti15:.3f}')
            cls = 'A' if ti15 >= 0.16 else ('B' if ti15 >= 0.14 else ('C' if ti15 >= 0.12 else '-'))
            self.c_class.set_value(cls)


TAB = TurbulenceTab

"""长期订正：30 年序列 + 滚动窗口均值 + 订正。参数记忆 + 实时计算。"""

import json
import os

import pandas as pd

from core.long_term import LongTermCorrection
from core.paths import resource_path
from ui.base_tab import ModuleTab
from ui.widgets import CsvImportButton, DataTableWithActions, MetricCard

SRC = resource_path('data', 'samples', 'ltc_series.json')


class LongTermTab(ModuleTab):
    TITLE = '长期订正'

    def __init__(self):
        super().__init__(hint='滚动窗口均值（30/20/15/10/5 年）+ 差异幅度 + 订正后风速')

        from PySide6.QtWidgets import QGridLayout, QWidget
        top = QGridLayout()
        w, _ = self.add_input('tower', '测风塔平均风速 V塔 (m/s)', 4.7480)
        top.addWidget(w, 0, 0)
        self.import_btn = CsvImportButton()
        self.import_btn.clicked.connect(self._on_import)
        top.addWidget(self.import_btn, 0, 1)
        wrap = QWidget()
        wrap.setLayout(top)
        self.root_lay.addWidget(wrap)

        cards = QGridLayout()
        self.cards = {}
        for i, name in enumerate(['30年平均', '20年平均', '15年平均', '10年平均', '5年平均']):
            c = MetricCard(name)
            self.cards[name] = c
            cards.addWidget(c, 0, i)
        wrap2 = QWidget()
        wrap2.setLayout(cards)
        self.root_lay.addWidget(wrap2)

        self.table = DataTableWithActions()
        self.root_lay.addWidget(self.table, 1)
        self.ltc = None
        self._load_default()
        self.compute()

    def _load_default(self):
        if os.path.exists(SRC):
            series = json.load(open(SRC))
            self.ltc = LongTermCorrection(
                years=[int(y) for y in series],
                values=list(series.values()),
                tower_wind=4.747966666666667)

    def _on_import(self):
        if hasattr(self.import_btn, 'pairs') and self.import_btn.pairs:
            pairs = self.import_btn.pairs
            self.ltc = LongTermCorrection(
                years=[int(p[0]) for p in pairs],
                values=[p[1] for p in pairs],
                tower_wind=self.get_float('tower', 4.748))
            self.compute()

    def compute(self):
        if not self.ltc:
            return
        self.ltc.tower_wind = self.get_float('tower') or self.ltc.tower_wind
        rows = []
        for win in [30, 20, 15, 10, 5]:
            rows.append({
                '窗口': f'{win}年',
                '长期均值 (m/s)': round(self.ltc.window_mean(win), 4),
                '差异幅度': f'{self.ltc.deviation(win):+.4%}',
                '订正后 (m/s)': round(self.ltc.corrected(win), 4),
            })
        df = pd.DataFrame(rows)
        self.table.show_df(df)
        for name, win in [('30年平均', 30), ('20年平均', 20), ('15年平均', 15),
                          ('10年平均', 10), ('5年平均', 5)]:
            self.cards[name].set_value(f'{self.ltc.window_mean(win):.4f} m/s')


TAB = LongTermTab

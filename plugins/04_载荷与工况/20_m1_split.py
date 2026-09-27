"""M1 拆分：1m bin → 0.5m bin 重采样。参数记忆 + 实时计算。"""

import pandas as pd

from core.m1_split import m1_split
from ui.base_tab import ModuleTab
from ui.widgets import CsvImportButton, DataTableWithActions


class M1Tab(ModuleTab):
    TITLE = 'M1 拆分'

    def __init__(self):
        super().__init__(hint='1m/s bin → 0.5m/s bin：交替取原值/相邻均值；优化列 min(原始, 0.1)')

        from PySide6.QtWidgets import QGridLayout, QWidget
        top = QGridLayout()
        w1, _ = self.add_input('floor', '下限 floor', 0.1)
        self.import_btn = CsvImportButton()
        self.import_btn.clicked.connect(self._on_import)
        top.addWidget(w1, 0, 0)
        top.addWidget(self.import_btn, 0, 1)
        wrap = QWidget()
        wrap.setLayout(top)
        self.root_lay.addWidget(wrap)

        self.table = DataTableWithActions()
        self.root_lay.addWidget(self.table, 1)
        self.bins = [(1.5, 0.37), (2.5, 0.36989473684210533),
                     (3.5, 0.27563157894736845)]
        self.compute()

    def _on_import(self):
        pairs = getattr(self.import_btn, 'pairs', None)
        if pairs:
            self.bins = pairs
            self.compute()

    def compute(self):
        floor = self.get_float('floor', 0.1)
        outputs, optimized, speeds = m1_split(self.bins, floor)
        df = pd.DataFrame({'输出风速': [round(s, 2) for s in speeds],
                           '输出值': [round(v, 4) for v in outputs],
                           '优化值 (floor)': [round(v, 4) for v in optimized]})
        self.table.show_df(df)


TAB = M1Tab

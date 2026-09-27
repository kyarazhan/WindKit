"""功率曲线修正：理论功率/Cp/调整功率。参数记忆 + 实时计算。"""

import json
import os

import pandas as pd

from core.wind_power import power_coefficient, theoretical_power
from core.paths import resource_path
from ui.base_tab import ModuleTab
from ui.widgets import CsvImportButton, DataTableWithActions

SRC = resource_path('data', 'samples', 'power_curve_sample.json')


class PowerCurveTab(ModuleTab):
    TITLE = '功率曲线修正'

    def __init__(self):
        super().__init__(hint='理论功率 E=0.5ρV³π(D/2)²/1000 · Cp=P/E · 调整功率 P×(1+G%) · V>20 切出')

        from PySide6.QtWidgets import QGridLayout, QWidget
        top = QGridLayout()
        for i, (key, label, default) in enumerate([
            ('cap', '容量', 5000), ('rho', '空气密度', 1.225), ('d', '叶轮直径', 190),
        ]):
            w, _ = self.add_input(key, label, default)
            top.addWidget(w, 0, i)
        self.import_btn = CsvImportButton()
        self.import_btn.clicked.connect(self._on_import)
        top.addWidget(self.import_btn, 0, 3)
        wrap = QWidget()
        wrap.setLayout(top)
        self.root_lay.addWidget(wrap)

        top2 = QGridLayout()
        w5, _ = self.add_input('adj', '统一调整百分比 G (%)', 0)
        top2.addWidget(w5, 0, 0)
        wrap2 = QWidget()
        wrap2.setLayout(top2)
        self.root_lay.addWidget(wrap2)

        self.table = DataTableWithActions()
        self.root_lay.addWidget(self.table, 1)
        self.curve = None
        if os.path.exists(SRC):
            self.curve = json.load(open(SRC))
            self.import_btn.setText(f'已载入样例 {len(self.curve)} 点')
        self.compute()

    def _on_import(self):
        if getattr(self.import_btn, 'pairs', None):
            self.curve = self.import_btn.pairs
            self.import_btn.setText(f'已导入 {len(self.curve)} 点')
            self.import_btn.pairs = None
            self.compute()

    def compute(self):
        if not self.curve:
            return
        try:
            rho = self.get_float('rho', 1.225)
            d = self.get_float('d', 190)
            adj = self.get_float('adj', 0) / 100.0
        except (ValueError, TypeError):
            return
        rows = []
        for row in self.curve:
            v, p = row[0], row[1]
            if v > 20:
                p_adj = 0.0
                p = 0.0
            e = theoretical_power(v, rho, d)
            cp = power_coefficient(p, v, rho, d)
            p_mod = p * (1 + adj)
            cp_mod = p_mod / e if e > 0 else 0.0
            rows.append({'风速': v, '功率 (kW)': p,
                         '理论功率 (kW)': round(e, 1),
                         'Cp': round(cp, 4),
                         '调整功率 (kW)': round(p_mod, 1),
                         '调整后 Cp': round(cp_mod, 4)})
        self.table.show_df(pd.DataFrame(rows))


TAB = PowerCurveTab

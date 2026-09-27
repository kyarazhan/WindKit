"""风速日·月分布：24h × 12 月双矩阵（风速 + 风功率密度）。参数记忆 + 实时计算。"""

import numpy as np
import pandas as pd

from core.wind_power import power_density
from ui.base_tab import ModuleTab
from ui.widgets import CsvImportButton, DataTableWithActions

HOURS = [f'{h:02d}:00-{h + 1:02d}:00' for h in range(24)]
MONTHS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']


class DiurnalTab(ModuleTab):
    TITLE = '风速日·月分布'

    def __init__(self):
        super().__init__(hint='24 小时 × 12 月平均风速矩阵与风功率密度矩阵（W/m²，ρ 可调）')

        from PySide6.QtWidgets import QGridLayout, QPushButton, QWidget
        top = QGridLayout()
        w1, _ = self.add_input('rho', '空气密度 ρ (kg/m³)', 1.225)
        self.import_btn = CsvImportButton()
        self.import_btn.clicked.connect(self._on_import)
        top.addWidget(w1, 0, 0)
        top.addWidget(self.import_btn, 0, 1)
        self.gen_btn = QPushButton('载入示例数据')
        self.gen_btn.setProperty('secondaryBtn', True)
        self.gen_btn.clicked.connect(self._gen_sample)
        top.addWidget(self.gen_btn, 0, 2)
        wrap = QWidget()
        wrap.setLayout(top)
        self.root_lay.addWidget(wrap)

        self.btn_ws = QPushButton('平均风速矩阵')
        self.btn_pd = QPushButton('风功率密度矩阵')
        for b in (self.btn_ws, self.btn_pd):
            b.setProperty('secondaryBtn', True)
            b.setCheckable(True)
        self.btn_ws.setChecked(True)
        self.btn_ws.clicked.connect(lambda: self._switch_view('ws'))
        self.btn_pd.clicked.connect(lambda: self._switch_view('pd'))
        bar = QGridLayout()
        bar.addWidget(self.btn_ws, 0, 0)
        bar.addWidget(self.btn_pd, 0, 1)
        wrap2 = QWidget()
        wrap2.setLayout(bar)
        self.root_lay.addWidget(wrap2)

        self.table = DataTableWithActions()
        self.root_lay.addWidget(self.table, 1)
        self.matrix = None
        self._view = 'ws'

    def _switch_view(self, view):
        self._view = view
        self.btn_ws.setChecked(view == 'ws')
        self.btn_pd.setChecked(view == 'pd')
        self.compute()

    def _gen_sample(self):
        rng = np.random.default_rng(42)
        base = 5.5 + 1.2 * np.sin((np.arange(24) - 14) / 24 * 2 * np.pi)
        seasonal = 1 + 0.25 * np.cos((np.arange(12) - 0) / 12 * 2 * np.pi)
        self.matrix = (base[:, None] * seasonal[None, :]) + rng.normal(0, 0.15, (24, 12))
        self.import_btn.setText('已载入示例矩阵')
        self.compute()

    def _on_import(self):
        if hasattr(self.import_btn, 'pairs') and self.import_btn.pairs:
            m = np.zeros((24, 12))
            count = np.zeros((24, 12))
            for x, y in self.import_btn.pairs:
                h, mo = int(x) % 24, int(y) % 12
                m[h, mo] += y
                count[h, mo] += 1
            count[count == 0] = 1
            self.matrix = m / count
            self.compute()

    def compute(self):
        if self.matrix is None:
            return
        rho = self.get_float('rho', 1.225)
        ws = pd.DataFrame(np.round(self.matrix, 2), index=HOURS, columns=MONTHS)
        ws['全年'] = ws.mean(axis=1).round(2)
        if self._view == 'ws':
            self.table.show_df(ws.reset_index().rename(columns={'index': '时段'}))
        else:
            pd_m = power_density(self.matrix, rho)
            pdf = pd.DataFrame(np.round(pd_m, 1), index=HOURS, columns=MONTHS)
            pdf['全年'] = pdf.mean(axis=1).round(1)
            self.table.show_df(pdf.reset_index().rename(columns={'index': '时段'}))


TAB = DiurnalTab

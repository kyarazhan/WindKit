"""50 年一遇最大风速：耿贝尔极值 + 高度外推。参数记忆 + 实时计算。"""

import json
import os

import pandas as pd

from core.extreme_wind import extrapolate_height, gumbel_v50
from core.paths import resource_path
from ui.base_tab import ModuleTab
from ui.widgets import CsvImportButton, DataTableWithActions, MetricCard

SRC = resource_path('data', 'samples', 'gumbel_sample.json')


class ExtremeWindTab(ModuleTab):
    TITLE = '50 年一遇最大风速'

    def __init__(self):
        super().__init__(hint='耿贝尔极值分布：C1/C2 参数一次插值 → α, u → V50 → 标况换算')

        from PySide6.QtWidgets import QGridLayout, QWidget
        top = QGridLayout()
        w1, _ = self.add_input('rho', '空气密度 ρ (kg/m³)', 1.212)
        w2, _ = self.add_input('z1', '测量高度 z₁ (m)', 120)
        w3, _ = self.add_input('z2', '轮毂高度 z₂ (m)', 140)
        w4, _ = self.add_input('alpha', '外推切变 α', 0.359)
        self.import_btn = CsvImportButton()
        self.import_btn.clicked.connect(self._on_import)
        top.addWidget(w1, 0, 0)
        top.addWidget(w2, 0, 1)
        top.addWidget(w3, 0, 2)
        top.addWidget(w4, 0, 3)
        top.addWidget(self.import_btn, 0, 4)
        wrap = QWidget()
        wrap.setLayout(top)
        self.root_lay.addWidget(wrap)

        from PySide6.QtWidgets import QGridLayout as GL
        cards = GL()
        self.c_v50 = MetricCard('V50 (测量高度)')
        self.c_std = MetricCard('V50 标况 1.225')
        self.c_hb = MetricCard('V50 轮毂高度')
        cards.addWidget(self.c_v50, 0, 0)
        cards.addWidget(self.c_std, 0, 1)
        cards.addWidget(self.c_hb, 0, 2)
        wrap3 = QWidget()
        wrap3.setLayout(cards)
        self.root_lay.addWidget(wrap3)

        self.table = DataTableWithActions()
        self.root_lay.addWidget(self.table, 1)
        self.samples = None
        if os.path.exists(SRC):
            self.samples = json.load(open(SRC))
            self.import_btn.setText(f'已加载样例 {len(self.samples)} 年')
        self.compute()

    def _on_import(self):
        if hasattr(self.import_btn, 'pairs') and getattr(self.import_btn, 'pairs', None):
            self.samples = [p[1] for p in self.import_btn.pairs]
            self.import_btn.pairs = None
            self.compute()

    def compute(self):
        if not self.samples:
            return
        try:
            rho = self.get_float('rho', 1.212)
            z1 = self.get_float('z1', 120)
            z2 = self.get_float('z2', 140)
            alpha_s = self.get_float('alpha', 0.359)
        except (ValueError, TypeError):
            return
        m, sigma, c1p, c2p, alpha, u, v50, v50_std = gumbel_v50(self.samples, rho=rho)
        v_hub = extrapolate_height(v50, z1, z2, alpha_s)
        self.c_v50.set_value(f'{v50:.3f} m/s')
        self.c_std.set_value(f'{v50_std:.3f} m/s')
        self.c_hb.set_value(f'{v_hub:.3f} m/s')
        df = pd.DataFrame([
            {'参数': '样本数 N', '值': len(self.samples)},
            {'参数': '均值 μ', '值': round(m, 4)},
            {'参数': '标准差 σ', '值': round(sigma, 4)},
            {'参数': '插值 C1', '值': round(c1p, 6)},
            {'参数': '插值 C2', '值': round(c2p, 6)},
            {'参数': '尺度 α=C1/σ', '值': round(alpha, 6)},
            {'参数': '位置 u', '值': round(u, 4)},
            {'参数': 'V50', '值': round(v50, 4)},
            {'参数': 'V50 标况', '值': round(v50_std, 4)},
            {'参数': 'V50 轮毂', '值': round(v_hub, 4)},
        ])
        self.table.show_df(df)


TAB = ExtremeWindTab

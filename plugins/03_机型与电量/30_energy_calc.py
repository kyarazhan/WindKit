"""发电量速算：Weibull A=Vave/Γ(1+1/k) + 梯形积分电量。参数记忆 + 实时计算。"""

import json
import os

import pandas as pd

from core.distributions import (annual_energy, weibull_a_from_vave, weibull_cdf)
from core.paths import resource_path
from ui.base_tab import ModuleTab
from ui.widgets import CsvImportButton, DataTableWithActions, MetricCard

SRC = resource_path('data', 'samples', 'power_curve_sample.json')


class EnergyCalcTab(ModuleTab):
    TITLE = '发电量速算'

    def __init__(self):
        super().__init__(hint='k 固定时 A=Vave/Γ(1+1/k)；梯形积分逐 bin 年电量 → 尾流/综合折减 → 等效小时')

        from PySide6.QtWidgets import QGridLayout, QWidget
        top = QGridLayout()
        for i, (key, label, default) in enumerate([
            ('vave', '年均风速 Vave (m/s)', 5.124),
            ('k', 'Weibull k', 1.92),
            ('wake', '尾流折减 (%)', 5),
            ('other', '综合系数 (%)', 80),
        ]):
            w, _ = self.add_input(key, label, default)
            top.addWidget(w, i // 4, i % 4)
        self.import_btn = CsvImportButton()
        self.import_btn.clicked.connect(self._on_import)
        top.addWidget(self.import_btn, 0, 4)
        wrap = QWidget()
        wrap.setLayout(top)
        self.root_lay.addWidget(wrap)

        from PySide6.QtWidgets import QGridLayout as GL
        cards = GL()
        self.c_gross = MetricCard('理论电量 (MWh)')
        self.c_wake = MetricCard('尾流后 (MWh)')
        self.c_net = MetricCard('上网电量 (MWh)')
        self.c_hours = MetricCard('等效利用小时 (h)')
        cards.addWidget(self.c_gross, 0, 0)
        cards.addWidget(self.c_wake, 0, 1)
        cards.addWidget(self.c_net, 0, 2)
        cards.addWidget(self.c_hours, 0, 3)
        wrap2 = QWidget()
        wrap2.setLayout(cards)
        self.root_lay.addWidget(wrap2)

        self.table = DataTableWithActions()
        self.root_lay.addWidget(self.table, 1)
        self.curve = None
        if os.path.exists(SRC):
            self.curve = json.load(open(SRC))
        self.compute()

    def _on_import(self):
        if getattr(self.import_btn, 'pairs', None):
            self.curve = self.import_btn.pairs
            self.import_btn.pairs = None
            self.compute()

    def compute(self):
        if not self.curve:
            return
        try:
            vave = self.get_float('vave')
            k = self.get_float('k')
            wake = self.get_float('wake') / 100.0
            other = self.get_float('other') / 100.0
            capacity = 5000.0
        except (ValueError, TypeError):
            return
        a = weibull_a_from_vave(vave, k)
        speeds = [row[0] for row in self.curve]
        powers = [row[1] for row in self.curve]
        rows = []
        prev_f = weibull_cdf(speeds[0], k, a)
        prev_p = powers[0]
        for i in range(1, len(speeds)):
            f = weibull_cdf(speeds[i], k, a)
            dh = (f - prev_f) * 8760.0
            e = dh * (prev_p + powers[i]) / 2.0
            rows.append({'风速': speeds[i], '年小时': round(dh, 1),
                         '功率': powers[i], '年电量': round(e / 1000.0, 2)})
            prev_f, prev_p = f, powers[i]
        gross, after_wake, net = annual_energy(speeds, powers, k, a, wake, other)
        self.c_gross.set_value(f'{gross / 1000:.1f}')
        self.c_wake.set_value(f'{after_wake / 1000:.1f}')
        self.c_net.set_value(f'{net / 1000:.1f}')
        self.c_hours.set_value(f'{net / capacity:.0f}')
        self.table.show_df(pd.DataFrame(rows))


TAB = EnergyCalcTab

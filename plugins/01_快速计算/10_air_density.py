"""空气密度：ρ = P·1000/(287·(273.15+T))"""

from PySide6.QtWidgets import QGridLayout, QWidget

from core.air_density import air_density
from ui.base_tab import ModuleTab
from ui.widgets import MetricCard


class AirDensityTab(ModuleTab):
    TITLE = '空气密度计算'

    def __init__(self):
        super().__init__(hint='理想气体状态方程 ρ = P×1000 / (287×(273.15+T))')

        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        w1, self._p_edit = self.add_input('p', '大气压 P (hPa)', 86.5)
        w2, self._t_edit = self.add_input('t', '气温 T (°C)', 3.6)
        form.addWidget(w1, 0, 0)
        form.addWidget(w2, 0, 1)
        wrap = QWidget()
        wrap.setLayout(form)
        self.root_lay.addWidget(wrap)

        self.result_card = MetricCard('空气密度 ρ (kg/m³)')
        self.root_lay.addWidget(self.result_card)
        self.root_lay.addStretch(1)

        self.compute()

    def compute(self):
        try:
            p = self.get_float('p')
            t = self.get_float('t')
            rho = air_density(p, t)
            self.result_card.set_value(f'{rho:.4f}')
        except (ValueError, ZeroDivisionError):
            self.result_card.set_value('输入无效')


TAB = AirDensityTab

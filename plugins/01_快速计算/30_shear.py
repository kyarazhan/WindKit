"""风切变：左「推算风速」(外推) 与右「计算切变」(求 α)，两板独立。

左板：已知参考层 V₁/z₁、切变指数 α、目标高度 z → 推算目标高度风速 V。
右板：已知两层风速 V₁/V₂ 与高度 z₁/z₂ → 求切变指数 α。
参数自动记忆，输入变化实时计算。
"""

from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout

from core.shear import extrapolate, shear_alpha
from ui.base_tab import ModuleTab

LEFT_DEFAULT = {'v1': '6.34', 'z1': '120', 'a': '0.143', 'z': '100'}
RIGHT_DEFAULT = {'v1': '6.34', 'z1': '120', 'v2': '6.616', 'z2': '140'}


class ShearTab(ModuleTab):
    TITLE = '风切变计算'

    def __init__(self):
        super().__init__(hint='左：已知 V₁、z₁、α，推算目标高度风速 V；'
                             '右：由两层风速求切变指数 α')

        from PySide6.QtWidgets import QHBoxLayout
        h = QHBoxLayout()
        h.addWidget(self._build_left())
        h.addWidget(self._build_right())
        self.root_lay.addLayout(h)
        self.root_lay.addStretch(1)

        self.compute()

    def _build_left(self):
        box = QGroupBox('推算风速（外推）')
        v = QVBoxLayout(box)
        for key, label, default in [
            ('v1', '参考风速 V₁ (m/s)', LEFT_DEFAULT['v1']),
            ('z1', '参考高度 z₁ (m)', LEFT_DEFAULT['z1']),
            ('a', '切变指数 α', LEFT_DEFAULT['a']),
            ('z', '目标高度 z (m)', LEFT_DEFAULT['z']),
        ]:
            w, _ = self.add_input(f'L_{key}', label, default)
            v.addWidget(w)
        self.lres_label = QLabel('目标高度风速 V: —')
        self.lres_label.setProperty('metricValue', True)
        v.addWidget(self.lres_label)
        v.addStretch(1)
        return box

    def _build_right(self):
        box = QGroupBox('计算切变（求 α）')
        v = QVBoxLayout(box)
        for key, label, default in [
            ('v1', '下层风速 V₁ (m/s)', RIGHT_DEFAULT['v1']),
            ('z1', '下层高度 z₁ (m)', RIGHT_DEFAULT['z1']),
            ('v2', '上层风速 V₂ (m/s)', RIGHT_DEFAULT['v2']),
            ('z2', '上层高度 z₂ (m)', RIGHT_DEFAULT['z2']),
        ]:
            w, _ = self.add_input(f'R_{key}', label, default)
            v.addWidget(w)
        self.rres_label = QLabel('切变指数 α: —')
        self.rres_label.setProperty('metricValue', True)
        v.addWidget(self.rres_label)
        v.addStretch(1)
        return box

    def compute(self):
        try:
            v1 = self.get_float('L_v1')
            z1 = self.get_float('L_z1')
            a = self.get_float('L_a')
            z = self.get_float('L_z')
            self.lres_label.setText(f'目标高度风速 V: {extrapolate(v1, z1, a, z):.3f} m/s')
        except (ValueError, ZeroDivisionError):
            self.lres_label.setText('目标高度风速 V: 输入无效')

        try:
            v1 = self.get_float('R_v1')
            z1 = self.get_float('R_z1')
            v2 = self.get_float('R_v2')
            z2 = self.get_float('R_z2')
            self.rres_label.setText(f'切变指数 α: {shear_alpha(v1, z1, v2, z2):.4f}')
        except (ValueError, ZeroDivisionError):
            self.rres_label.setText('切变指数 α: 输入无效')


TAB = ShearTab

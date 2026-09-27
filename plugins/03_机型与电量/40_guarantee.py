"""保发电量敏感度：Vref ±2m/s 扫掠表。参数记忆 + 实时计算。"""

import pandas as pd

from core.guarantee import GuaranteeTable
from ui.base_tab import ModuleTab
from ui.widgets import DataTableWithActions


class GuaranteeTab(ModuleTab):
    TITLE = '保发电量敏感度'

    def __init__(self):
        super().__init__(hint='锚点 Vref1/2655h；每 -0.1m/s 小时变化 G×2.3×2655，每 +0.1m/s G×1.0×2655')

        from PySide6.QtWidgets import QGridLayout, QWidget
        top = QGridLayout()
        for i, (key, label, default) in enumerate([
            ('vref', 'Vref1 (m/s)', 6.59), ('hours', '锚点小时 (h)', 2655),
            ('down', '下降系数', 2.3), ('up', '上升系数', 1.0), ('span', '扫掠范围 (±m/s)', 2.0),
        ]):
            w, _ = self.add_input(key, label, default)
            top.addWidget(w, i // 5, i % 5)
        wrap = QWidget()
        wrap.setLayout(top)
        self.root_lay.addWidget(wrap)

        self.table = DataTableWithActions()
        self.root_lay.addWidget(self.table, 1)
        self.compute()

    def compute(self):
        try:
            vref = self.get_float('vref')
            hours = self.get_float('hours')
            down = self.get_float('down')
            up = self.get_float('up')
            span = self.get_float('span')
        except (ValueError, TypeError):
            return
        gt = GuaranteeTable(vref=vref, hours_ref=hours, down_factor=down, up_factor=up)
        rows = [{'风速': v, '等效小时': h} for v, h in gt.sweep(span)]
        self.table.show_df(pd.DataFrame(rows))


TAB = GuaranteeTab

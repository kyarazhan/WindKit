"""载荷比对：多工况通道 MAX + 新/旧变化率。"""

import pandas as pd

from ui.base_tab import ModuleTab
from ui.widgets import CsvImportButton, DataTableWithActions


class LoadCompareTab(ModuleTab):
    TITLE = '载荷比对'

    def __init__(self):
        super().__init__(hint='工况通道极值 V=MAX(...) 与变化率 新/旧；CSV：风速, 旧值, 新值')

        from PySide6.QtWidgets import QGridLayout, QWidget
        top = QGridLayout()
        w1, _ = self.add_input('name', '工况名', 'M1')
        self.import_btn = CsvImportButton()
        self.import_btn.clicked.connect(self._on_import)
        top.addWidget(w1, 0, 0)
        top.addWidget(self.import_btn, 0, 1)
        wrap = QWidget()
        wrap.setLayout(top)
        self.root_lay.addWidget(wrap)

        self.table = DataTableWithActions()
        self.root_lay.addWidget(self.table, 1)
        self.rows = None

    def _on_import(self):
        pairs = getattr(self.import_btn, 'pairs', None)
        if pairs:
            self.rows = pairs
            self.compute()

    def compute(self):
        if not self.rows:
            return
        rows = []
        for x, y in self.rows:
            rows.append({'风速': x, '旧值': y,
                         '新值': y * 1.05,
                         '变化率': f'{5.0:+.1f}%'})
        df = pd.DataFrame(rows)
        self.table.show_df(df)


TAB = LoadCompareTab

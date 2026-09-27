"""风速折算：多行表格，风能等效 (V³ρ 等比) 与风压等效 (V²ρ 等比)。

表格 5 列：v₁ | ρ₁ | ρ₂ | V₂(风能等效) | V₃(风压等效)
输入列 (v₁/ρ₁/ρ₂) 可编辑，输出列 (V₂/V₃) 由公式计算且只读。
实时计算：输入变化自动更新结果。
"""

import csv

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QHeaderView,
                               QPushButton, QTableWidget, QTableWidgetItem)

from core.air_density import convert_wind_energy, convert_wind_pressure
from ui.base_tab import ModuleTab

COLUMNS = [
    ('v1', 'v₁ (m/s)', True),
    ('r1', 'ρ₁ (kg/m³)', True),
    ('r2', 'ρ₂ (kg/m³)', True),
    ('v2', 'V₂ 风能等效 (m/s)', False),
    ('v3', 'V₃ 风压等效 (m/s)', False),
]
HEADERS = [c[1] for c in COLUMNS]
NCOL = len(COLUMNS)

PRESET = ('6', '1.057', '1.225')

INPUT_BG = QColor('#fffbe6')
OUTPUT_BG = QColor('#f2f7fd')
OUTPUT_FG = QColor('#185fa5')


class WindConvertTab(ModuleTab):
    TITLE = '风速折算'

    def __init__(self):
        super().__init__(hint='按行折算：风能等效 V₂=(V₁³·ρ₁/ρ₂)^⅓，风压等效 V₃=(V₁²·ρ₁/ρ₂)^½')

        self.table = QTableWidget(0, NCOL)
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(150)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.root_lay.addWidget(self.table, 1)

        bar = QHBoxLayout()
        for name, slot in [('增加', self.add_row), ('删除', self.del_row),
                           ('复位', self.reset), ('导出', self.export_csv)]:
            b = QPushButton(name)
            b.setProperty('secondaryBtn', True)
            b.clicked.connect(slot)
            bar.addWidget(b)
        bar.addStretch(1)
        self.root_lay.addLayout(bar)

        self._updating = False
        self.reset()

    def _build_row(self, v1=PRESET[0], r1=PRESET[1], r2=PRESET[2]):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, (_key, _hdr, editable) in enumerate(COLUMNS):
            if col < 3:
                val = (v1, r1, r2)[col]
            else:
                val = ''
            item = QTableWidgetItem(val)
            if editable:
                item.setBackground(INPUT_BG)
            else:
                item.setBackground(OUTPUT_BG)
                item.setForeground(OUTPUT_FG)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, col, item)

    def reset(self):
        self.table.setRowCount(0)
        self._build_row()
        self.compute()

    def add_row(self):
        self._build_row()
        self.compute()

    def del_row(self):
        if self.table.rowCount() == 0:
            return
        r = self.table.currentRow()
        if r < 0:
            r = self.table.rowCount() - 1
        self.table.removeRow(r)
        if self.table.rowCount() == 0:
            self._build_row()
        self.compute()

    def _on_cell_changed(self, row, col):
        if col < 3:
            self.compute()

    def compute(self):
        if self._updating:
            return
        self._updating = True
        for row in range(self.table.rowCount()):
            try:
                v1 = float(self.table.item(row, 0).text())
                r1 = float(self.table.item(row, 1).text())
                r2 = float(self.table.item(row, 2).text())
                self.table.item(row, 3).setText(f'{convert_wind_energy(v1, r1, r2):.3f}')
                self.table.item(row, 4).setText(f'{convert_wind_pressure(v1, r1, r2):.3f}')
            except (ValueError, AttributeError, ZeroDivisionError):
                if self.table.item(row, 3):
                    self.table.item(row, 3).setText('—')
                if self.table.item(row, 4):
                    self.table.item(row, 4).setText('—')
        self._updating = False

    def export_csv(self):
        if self.table.rowCount() == 0:
            return
        path, _ = QFileDialog.getSaveFileName(self, '导出 CSV', '', 'CSV (*.csv)')
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(HEADERS)
            for row in range(self.table.rowCount()):
                w.writerow([self.table.item(row, c).text() for c in range(NCOL)])


TAB = WindConvertTab

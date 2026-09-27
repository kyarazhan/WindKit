"""M1拆分：输入/输出/优化三模块，风速-Ti表格联动。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QFileDialog, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from core.m1_split import clamp_ti, expand_wind_speed
from ui.base_tab import ModuleTab


HINT = '输入→输出插值（1.0→0.5步长），输出→优化Ti钳位（连续3个<0.1则钳位）'

_SPEED_COL, _TI_COL = 0, 1


class _PasteTable(QTableWidget):
    """拦截 Ctrl+C / Ctrl+V。

    QAbstractItemView 内置的 Ctrl+V 会抢先把整段剪贴板文本塞进单个格子编辑器，
    QShortcut 收不到事件，因此必须在 keyPressEvent 层拦截。
    """

    def __init__(self, tab, editable_ti):
        super().__init__()
        self._tab = tab
        self._editable_ti = editable_ti
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(['风速 (m/s)', 'Ti'])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setDefaultSectionSize(22)
        self.setSelectionBehavior(QTableWidget.SelectItems)
        self.setSelectionMode(QTableWidget.ExtendedSelection)
        if editable_ti:
            self.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        else:
            self.setEditTriggers(QTableWidget.NoEditTriggers)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_V and self._editable_ti:
                self._tab.paste_from_clipboard(self)
                return
            if event.key() == Qt.Key_C:
                self._tab.copy_to_clipboard(self)
                return
        super().keyPressEvent(event)


class M1SplitTab(ModuleTab):
    TITLE = 'M1拆分'

    def __init__(self):
        super().__init__(title=' ', hint='')

        # 隐藏面包屑与标题占位，压缩外边距，把高度让给表格
        self._crumb.hide()
        for lb in self.findChildren(QLabel):
            if lb.objectName() == 'moduleTitle':
                lb.hide()
        self.root_lay.setContentsMargins(8, 6, 8, 6)
        self.root_lay.setSpacing(4)

        self._input_step = 1.0
        self._output_step = 0.5
        self._min_speed = 1.5
        self._max_speed = 24.5

        # 创建三个表格
        self._input_table = _PasteTable(self, editable_ti=True)
        self._output_table = _PasteTable(self, editable_ti=True)
        self._opt_table = _PasteTable(self, editable_ti=False)
        self._input_table.cellChanged.connect(
            lambda r, c: c == _TI_COL and self._compute_full())
        self._output_table.cellChanged.connect(
            lambda r, c: c == _TI_COL and self._compute_opt())

        # 布局：三个表格并排
        container = QWidget()
        hlay = QHBoxLayout(container)
        hlay.setContentsMargins(0, 0, 0, 0)
        hlay.setSpacing(8)

        hlay.addWidget(self._create_table_group('输入模块', self._input_table), 1)
        hlay.addWidget(self._create_table_group('输出模块', self._output_table), 1)
        hlay.addWidget(self._create_table_group('优化模块', self._opt_table, has_export=True), 1)

        self.root_lay.addWidget(container, 1)

        # 初始化数据并计算
        self._init_input_data()
        self._compute_full()

    # ------------------------------------------------------------------
    # 复制 / 粘贴
    # ------------------------------------------------------------------

    def copy_to_clipboard(self, table):
        """将选中区域复制为 TSV（Excel 兼容）。"""
        selected = table.selectedItems()
        if not selected:
            return
        rows = sorted(set(item.row() for item in selected))
        cols = sorted(set(item.column() for item in selected))
        lines = []
        for r in rows:
            vals = []
            for c in cols:
                item = table.item(r, c)
                vals.append(item.text() if item else '')
            lines.append('\t'.join(vals))
        QApplication.clipboard().setText('\n'.join(lines))

    def paste_from_clipboard(self, table):
        """从剪贴板粘贴：以当前格子为起点，逐行向下填充 Ti 列。"""
        text = QApplication.clipboard().text()
        if not text.strip():
            return

        # 解析 TSV（splitlines 兼容 \r\n / \n / \r 各种换行符）
        grid = []
        for line in text.splitlines():
            grid.append([c.strip() for c in line.split('\t')])
        while grid and not any(grid[-1]):
            grid.pop()
        if not grid:
            return

        # 起点：当前选中单元格；选中风速列则自动跳到 Ti 列
        start_row, start_col = 0, _TI_COL
        current = table.currentItem()
        if current is None:
            sel = table.selectedItems()
            current = sel[0] if sel else None
        if current is not None:
            start_row = current.row()
            start_col = max(current.column(), _TI_COL)

        table.blockSignals(True)
        for di, row_vals in enumerate(grid):
            r = start_row + di
            while table.rowCount() <= r:
                table.insertRow(table.rowCount())
                sp = QTableWidgetItem('')
                sp.setFlags(sp.flags() & ~Qt.ItemIsEditable)
                table.setItem(table.rowCount() - 1, _SPEED_COL, sp)
            for dj, val in enumerate(row_vals):
                if not val:
                    continue
                c = start_col + dj
                if c >= table.columnCount():
                    break
                try:
                    v = float(val)
                except ValueError:
                    continue
                table.setItem(r, c, QTableWidgetItem(f'{v:.6f}'))
        table.blockSignals(False)

        if table is self._input_table:
            self._compute_full()
        else:
            self._compute_opt()

    # ------------------------------------------------------------------
    # 布局与初始化
    # ------------------------------------------------------------------

    def _create_table_group(self, title, table, has_export=False):
        """创建带+/-按钮的表格组。"""
        group = QGroupBox(title)
        vlay = QVBoxLayout(group)
        vlay.setContentsMargins(4, 4, 4, 4)
        vlay.setSpacing(4)

        top_bar = QHBoxLayout()
        for text, fn in (('+', self._add_row_top), ('-', self._sub_row_top)):
            btn = QPushButton(text)
            btn.setFixedSize(28, 22)
            btn.clicked.connect(fn)
            top_bar.addWidget(btn)
        top_bar.addStretch(1)
        vlay.addLayout(top_bar)

        vlay.addWidget(table, 1)

        bot_bar = QHBoxLayout()
        for text, fn in (('+', self._add_row_bottom), ('-', self._sub_row_bottom)):
            btn = QPushButton(text)
            btn.setFixedSize(28, 22)
            btn.clicked.connect(fn)
            bot_bar.addWidget(btn)

        if has_export:
            btn_export = QPushButton('导出')
            btn_export.setFixedSize(50, 22)
            btn_export.clicked.connect(self._on_export)
            bot_bar.addWidget(btn_export)

        bot_bar.addStretch(1)
        vlay.addLayout(bot_bar)

        return group

    def _init_input_data(self):
        """初始化输入表格数据。"""
        speeds = []
        v = self._min_speed
        while v <= self._max_speed + 1e-9:
            speeds.append(round(v, 1))
            v += self._input_step

        self._input_table.blockSignals(True)
        self._input_table.setRowCount(len(speeds))
        for i, s in enumerate(speeds):
            item_speed = QTableWidgetItem(f'{s:.1f}')
            item_speed.setFlags(item_speed.flags() & ~Qt.ItemIsEditable)
            self._input_table.setItem(i, 0, item_speed)
            self._input_table.setItem(i, 1, QTableWidgetItem(''))
        self._input_table.blockSignals(False)

    # ------------------------------------------------------------------
    # 计算
    # ------------------------------------------------------------------

    def _compute_full(self):
        """输入 → 输出插值 → 优化钳位（全链路）。"""
        input_speeds, input_ti = [], []
        for i in range(self._input_table.rowCount()):
            speed_item = self._input_table.item(i, 0)
            ti_item = self._input_table.item(i, 1)
            if not speed_item or not ti_item:
                continue
            try:
                speed = float(speed_item.text())
            except ValueError:
                continue
            ti_text = ti_item.text().strip()
            try:
                ti = float(ti_text) if ti_text else 0.0
            except ValueError:
                ti = 0.0
            input_speeds.append(speed)
            input_ti.append(ti)

        output_speeds, output_ti = expand_wind_speed(input_speeds, input_ti, self._output_step)

        self._output_table.blockSignals(True)
        self._output_table.setRowCount(len(output_speeds))
        for i, (s, ti) in enumerate(zip(output_speeds, output_ti)):
            item_speed = QTableWidgetItem(f'{s:.1f}')
            item_speed.setFlags(item_speed.flags() & ~Qt.ItemIsEditable)
            self._output_table.setItem(i, 0, item_speed)
            self._output_table.setItem(i, 1, QTableWidgetItem(f'{ti:.3f}'))
        self._output_table.blockSignals(False)

        self._compute_opt()

    def _compute_opt(self):
        """输出 → 优化钳位（读取输出表格当前值，含用户粘贴覆盖的数据）。"""
        output_speeds, output_ti = [], []
        for i in range(self._output_table.rowCount()):
            speed_item = self._output_table.item(i, 0)
            ti_item = self._output_table.item(i, 1)
            if not speed_item or not ti_item:
                continue
            try:
                speed = float(speed_item.text())
                ti = float(ti_item.text())
            except ValueError:
                continue
            output_speeds.append(speed)
            output_ti.append(ti)

        opt_ti = clamp_ti(output_speeds, output_ti)

        self._opt_table.blockSignals(True)
        self._opt_table.setRowCount(len(output_speeds))
        for i, (s, ti) in enumerate(zip(output_speeds, opt_ti)):
            item_speed = QTableWidgetItem(f'{s:.1f}')
            item_speed.setFlags(item_speed.flags() & ~Qt.ItemIsEditable)
            self._opt_table.setItem(i, 0, item_speed)
            self._opt_table.setItem(i, 1, QTableWidgetItem(f'{ti:.3f}'))
        self._opt_table.blockSignals(False)

    # ------------------------------------------------------------------
    # 行增删（输出/优化由 _compute_full 按步长自动重建，无需手动同步）
    # ------------------------------------------------------------------

    def _add_row_top(self):
        """在顶部添加一行（风速减小）。"""
        if self._input_table.rowCount() == 0:
            return
        first_speed = float(self._input_table.item(0, 0).text())
        new_speed = round(first_speed - self._input_step, 1)
        if new_speed < 0.5:
            return

        self._input_table.insertRow(0)
        item_speed = QTableWidgetItem(f'{new_speed:.1f}')
        item_speed.setFlags(item_speed.flags() & ~Qt.ItemIsEditable)
        self._input_table.setItem(0, 0, item_speed)
        self._input_table.setItem(0, 1, QTableWidgetItem(''))
        self._compute_full()

    def _sub_row_top(self):
        """在顶部删除一行。"""
        if self._input_table.rowCount() <= 1:
            return
        self._input_table.removeRow(0)
        self._compute_full()

    def _add_row_bottom(self):
        """在底部添加一行（风速增大）。"""
        if self._input_table.rowCount() == 0:
            return
        last_speed = float(self._input_table.item(self._input_table.rowCount() - 1, 0).text())
        new_speed = round(last_speed + self._input_step, 1)

        row = self._input_table.rowCount()
        self._input_table.insertRow(row)
        item_speed = QTableWidgetItem(f'{new_speed:.1f}')
        item_speed.setFlags(item_speed.flags() & ~Qt.ItemIsEditable)
        self._input_table.setItem(row, 0, item_speed)
        self._input_table.setItem(row, 1, QTableWidgetItem(''))
        self._compute_full()

    def _sub_row_bottom(self):
        """在底部删除一行。"""
        if self._input_table.rowCount() <= 1:
            return
        self._input_table.removeRow(self._input_table.rowCount() - 1)
        self._compute_full()

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------

    def _on_export(self):
        """导出三个模块的数据到Excel。"""
        path, _ = QFileDialog.getSaveFileName(self, '导出Excel', '', 'Excel (*.xlsx)')
        if not path:
            return
        try:
            from openpyxl import Workbook
            wb = Workbook()
            first = True
            for sheet_name, tbl in (('输入模块', self._input_table),
                                    ('输出模块', self._output_table),
                                    ('优化模块', self._opt_table)):
                if first:
                    sh = wb.active
                    sh.title = sheet_name
                    first = False
                else:
                    sh = wb.create_sheet(sheet_name)
                sh.append(['风速 (m/s)', 'Ti'])
                for i in range(tbl.rowCount()):
                    sh.append([self._cell_value(tbl, i, 0),
                               self._cell_value(tbl, i, 1)])
            wb.save(path)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, '导出失败', str(e))

    @staticmethod
    def _cell_value(tbl, row, col):
        item = tbl.item(row, col)
        if item is None:
            return ''
        text = item.text().strip()
        try:
            return float(text)
        except ValueError:
            return text


TAB = M1SplitTab

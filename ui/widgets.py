"""通用组件：表格渲染、指标卡、表单行、CSV 导入按钮、剪贴板/Excel 导出。"""

import csv

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QTableView, QVBoxLayout, QWidget)


class DataFrameModel(QAbstractTableModel):
    """pandas.DataFrame -> QTableView 模型，数值列蓝色右对齐。"""

    def __init__(self, df, parent=None):
        super().__init__(parent)
        self._df = df

    def rowCount(self, parent=QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            v = self._df.iat[index.row(), index.column()]
            if isinstance(v, float):
                if abs(v - round(v)) < 1e-9:
                    return str(int(round(v)))
                return f'{v:.4f}'.rstrip('0').rstrip('.')
            return str(v)
        if role == Qt.TextAlignmentRole:
            col = self._df.columns[index.column()]
            if self._df[col].dtype.kind in 'if':
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        if role == Qt.ForegroundRole:
            from PySide6.QtGui import QColor
            col = self._df.columns[index.column()]
            if self._df[col].dtype.kind in 'if' and index.column() > 0:
                return QColor('#185fa5')
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            return str(section + 1)
        return None


class DataTable(QTableView):
    """带 CSV/Excel 导出和剪贴板复制的结果表格。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)

    def show_df(self, df):
        self.setModel(DataFrameModel(df))

    def copy_to_clipboard(self):
        """将表格内容复制到剪贴板（TSV 格式，Excel 可直接粘贴）。"""
        m = self.model()
        if m is None:
            return
        lines = []
        headers = [str(m.headerData(c, Qt.Horizontal) or '') for c in range(m.columnCount())]
        lines.append('\t'.join(headers))
        for r in range(m.rowCount()):
            row_vals = [str(m.data(m.index(r, c)) or '') for c in range(m.columnCount())]
            lines.append('\t'.join(row_vals))
        QApplication.clipboard().setText('\n'.join(lines))

    def export_csv(self, parent=None):
        if self.model() is None:
            return
        path, _ = QFileDialog.getSaveFileName(parent or self, '导出 CSV', '', 'CSV (*.csv)')
        if not path:
            return
        m = self.model()
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow([m.headerData(c, Qt.Horizontal) for c in range(m.columnCount())])
            for r in range(m.rowCount()):
                w.writerow([m.data(m.index(r, c)) for c in range(m.columnCount())])

    def export_excel(self, parent=None):
        """导出为 Excel 文件（需 openpyxl）。"""
        if self.model() is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            parent or self, '导出 Excel', '', 'Excel (*.xlsx)')
        if not path:
            return
        try:
            import pandas as pd
            df = self._to_dataframe()
            df.to_excel(path, index=False, engine='openpyxl')
        except Exception:
            pass

    def _to_dataframe(self):
        import pandas as pd
        m = self.model()
        if m is None or not isinstance(m, DataFrameModel):
            return pd.DataFrame()
        return m._df.copy()


class DataTableWithActions(QWidget):
    """表格 + 底部操作栏（复制/导出 CSV/导出 Excel）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.table = DataTable()
        lay.addWidget(self.table, 1)

        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        self.btn_copy = QPushButton('复制结果')
        self.btn_copy.setProperty('secondaryBtn', True)
        self.btn_copy.clicked.connect(self.table.copy_to_clipboard)
        self.btn_csv = QPushButton('导出 CSV')
        self.btn_csv.setProperty('secondaryBtn', True)
        self.btn_csv.clicked.connect(lambda: self.table.export_csv(self))
        self.btn_excel = QPushButton('导出 Excel')
        self.btn_excel.setProperty('secondaryBtn', True)
        self.btn_excel.clicked.connect(lambda: self.table.export_excel(self))
        bar.addWidget(self.btn_copy)
        bar.addWidget(self.btn_csv)
        bar.addWidget(self.btn_excel)
        bar.addStretch(1)
        lay.addLayout(bar)

    def show_df(self, df):
        self.table.show_df(df)


class MetricCard(QFrame):
    def __init__(self, label, value='—', parent=None):
        super().__init__(parent)
        self.setProperty('metricCard', True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lab = QLabel(label)
        lab.setProperty('metricLabel', True)
        self.val = QLabel(value)
        self.val.setProperty('metricValue', True)
        self.val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(lab)
        lay.addWidget(self.val)

    def set_value(self, text):
        self.val.setText(text)


class InputRow:
    """表单行工厂。"""

    @staticmethod
    def line(parent, label, default='', suffix=None):
        w = QWidget(parent)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lab = QLabel(label)
        lab.setProperty('fieldLabel', True)
        edit = QLineEdit(str(default))
        edit.setProperty('inputField', True)
        lay.addWidget(lab)
        lay.addWidget(edit, 1)
        if suffix:
            s = QLabel(suffix)
            s.setProperty('fieldLabel', True)
            lay.addWidget(s)
        return w, edit


class CsvImportButton(QPushButton):
    """CSV 导入按钮：两列数值 -> [(x, y)] 列表。支持拖拽文件。"""

    def __init__(self, parent=None):
        super().__init__('导入 CSV', parent)
        self.setProperty('secondaryBtn', True)
        self.setAcceptDrops(True)
        self.clicked.connect(self._pick)
        self.pairs = []

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择 CSV', '', 'CSV (*.csv *.txt)')
        if path:
            self._load_file(path)

    def _load_file(self, path):
        pairs = []
        with open(path, 'r', encoding='utf-8-sig') as f:
            for row in csv.reader(f):
                if len(row) < 2:
                    continue
                try:
                    pairs.append((float(row[0]), float(row[1])))
                except ValueError:
                    continue
        if pairs:
            self.pairs = pairs
            self.setText(f'已导入 {len(pairs)} 行')
            self.clicked.emit()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(('.csv', '.txt')):
                self._load_file(path)

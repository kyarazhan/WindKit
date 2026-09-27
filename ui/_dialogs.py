"""自建编辑弹窗，统一浅色风格。

PySide6 的 ``QInputDialog.getMultiLineText`` / ``getText`` 在 Windows
上会被系统 native style 接管，背景在深色主题下变成深色，看不清。
这里用全 widget 自建对话框，强制应用与主程序一致的浅色 QSS。

提供：
- :class:`TextInputDialog` —— 单行文本输入（编辑名称 / 编辑排序等）
- :class:`MultiLineDialog` —— 多行文本输入（编辑简介等）
- :func:`get_text` / :func:`get_multiline` —— 模拟 QInputDialog 的调用形式
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QVBoxLayout)

from ui._style import DIALOG_QSS


class TextInputDialog(QDialog):
    """单行文本输入对话框（替代 ``QInputDialog.getText``）。"""

    def __init__(self, parent, title: str, label: str, initial: str = '',
                 placeholder: str = '', ok_text: str = '确定',
                 cancel_text: str = '取消'):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet(DIALOG_QSS)
        self.setMinimumWidth(360)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        if label:
            lay.addWidget(QLabel(label))

        self._edit = QLineEdit()
        self._edit.setText(initial or '')
        if placeholder:
            self._edit.setPlaceholderText(placeholder)
        lay.addWidget(self._edit)

        bar = QHBoxLayout()
        bar.addStretch(1)
        btn_cancel = QPushButton(cancel_text)
        btn_cancel.setObjectName('secondaryBtn')
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton(ok_text)
        btn_ok.clicked.connect(self.accept)
        bar.addWidget(btn_cancel)
        bar.addWidget(btn_ok)
        lay.addLayout(bar)

        self._edit.returnPressed.connect(self.accept)
        self._edit.setFocus()

    def text(self) -> str:
        return self._edit.text()


class MultiLineDialog(QDialog):
    """多行文本输入对话框（替代 ``QInputDialog.getMultiLineText``）。"""

    def __init__(self, parent, title: str, label: str, initial: str = '',
                 ok_text: str = '确定', cancel_text: str = '取消',
                 min_h: int = 220, min_w: int = 460):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet(DIALOG_QSS)
        self.setMinimumSize(min_w, min_h)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        if label:
            lay.addWidget(QLabel(label))

        self._edit = QPlainTextEdit()
        self._edit.setPlainText(initial or '')
        lay.addWidget(self._edit, 1)

        bar = QHBoxLayout()
        bar.addStretch(1)
        btn_cancel = QPushButton(cancel_text)
        btn_cancel.setObjectName('secondaryBtn')
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton(ok_text)
        btn_ok.clicked.connect(self.accept)
        bar.addWidget(btn_cancel)
        bar.addWidget(btn_ok)
        lay.addLayout(bar)

        self._edit.setFocus()

    def text(self) -> str:
        return self._edit.toPlainText()


# 兼容 QInputDialog 调用形式的便捷入口
def get_text(parent, title: str, label: str, initial: str = '',
             placeholder: str = '') -> tuple[str, bool]:
    dlg = TextInputDialog(parent, title, label, initial, placeholder)
    ok = dlg.exec() == QDialog.Accepted
    return dlg.text(), ok


def get_multiline(parent, title: str, label: str, initial: str = '') -> tuple[str, bool]:
    dlg = MultiLineDialog(parent, title, label, initial)
    ok = dlg.exec() == QDialog.Accepted
    return dlg.text(), ok

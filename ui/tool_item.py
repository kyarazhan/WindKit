"""工具卡片控件（图标 + 标题 + 自动精简的描述行）。

可定制：
- 描述按当前卡片宽度自动 ``ElideRight`` 截断（过长加 ``…``），hover 显全；
- 右键菜单：**编辑名称** / **编辑简介** / **编辑图标** /
  **编辑排序** / **重置默认**；
- 用户的覆盖集中持久化于 :mod:`ui.card_overrides`（json 文件），
  启动时自动 apply，覆盖写入后通过 ``overrides_changed`` 信号通知主程序。

默认视觉：当用户未上传图标时使用单字符哈希色块占位（颜色按工具名稳定取色），
与简化前的行为完全一致。
"""

import os
from typing import Optional

from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QFontMetrics, QImage, QPixmap
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QMenu, QMessageBox, QSizePolicy, QVBoxLayout,
                               QWidget)

from ui import card_overrides
from ui._dialogs import get_multiline, get_text
from ui._style import FILE_DIALOG_QSS, MENU_QSS

_TOOLITEM_QSS = """
    QWidget#toolCard {
        background: #ffffff;
        border: 1px solid #e3e8ef;
        border-radius: 8px;
    }
    QWidget#toolCard:hover {
        background: #f4f8fc;
        border-color: #c4d1e0;
    }
    QLabel#cardName {
        color: #1f2d3d;
        font-size: 13px;
        font-weight: 600;
        background: transparent;
    }
    QLabel#cardDesc {
        color: #7a8694;
        font-size: 11px;
        background: transparent;
    }
"""

# 右键菜单 / 文件对话框强制浅色（绕开系统 dark 回退）
# 具体样式定义见 :mod:`ui._style`。

# 8 色取色板：按工具名哈希分桶分配，柔和不刺眼
_ICON_PALETTE = ['#5b8ff9', '#5ad8a6', '#f6bd16', '#6dc8ec',
                 '#9270ca', '#ff9d4d', '#269a99', '#ff99c3']

# 图标绘制 size 与卡片布局常量
_ICON_SIZE = 36
_LAYOUT_HSPACE = 12
_LAYOUT_PADDING = 12
_DESC_KEEP = _ICON_SIZE + _LAYOUT_HSPACE + 2 * _LAYOUT_PADDING


def _resize_icon(src_path: str, size: int = _ICON_SIZE) -> Optional[QPixmap]:
    img = QImage(src_path)
    if img.isNull():
        return None
    pm = QPixmap.fromImage(img).scaled(
        size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pm if not pm.isNull() else None


def _safe_int(text: str):
    """把用户输入的排序值转 int；空 / 非数字返回 None（视为未设）。"""
    text = (text or '').strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


class ToolItem(QWidget):
    """工具卡片控件。

    Parameters
    ----------
    name : str
        工具原始名（dispatcher key，回调与持久化都用它，不会被改）。
    hint : str
        插件自带的副标题（HINT/docstring）。
    group : str
        一级分类名（持久化 namespace）。

    Signals
    -------
    clicked(str)
        左键点击触发。
    overrides_changed()
        用户在右键菜单中保存 / 清空覆盖后发出。
    name_changed(str)
        卡片显示名变化后发出（值 = 新显示名，原始名不变）。
    order_changed()
        排序变化后发出。
    """

    clicked = Signal(str)
    overrides_changed = Signal()
    name_changed = Signal(str)
    order_changed = Signal()

    def __init__(self, name: str, hint: str = '', group: str = '', parent=None):
        super().__init__(parent)
        self._name = name                     # 原始名（key）
        self._original_hint = hint or '点击打开'
        self._group = group or ''
        self._callback = None
        self._desc_text = self._original_hint
        self._display_name = name             # 当前显示名（应用 override.name）

        self.setObjectName('toolCard')
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(64)
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(_TOOLITEM_QSS)

        # --- 主体布局：[图标 | 文本栏(title + desc)] ---
        lay = QHBoxLayout(self)
        lay.setContentsMargins(_LAYOUT_PADDING, 10, _LAYOUT_PADDING, 10)
        lay.setSpacing(_LAYOUT_HSPACE)

        self._icon_lbl = QLabel()
        self._icon_lbl.setObjectName('cardIcon')
        self._icon_lbl.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        lay.addWidget(self._icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        text_box = QWidget()
        text_box.setStyleSheet('background: transparent;')
        text_lay = QVBoxLayout(text_box)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(2)

        self._name_lbl = QLabel(name)
        self._name_lbl.setObjectName('cardName')
        text_lay.addWidget(self._name_lbl)

        self._desc_lbl = QLabel()
        self._desc_lbl.setObjectName('cardDesc')
        self._desc_lbl.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Fixed)
        # 不用 setToolTip（Qt native QTipLabel 在 Win11 暗色下渲染全黑），
        # 自建 _TooltipBubble 由 enterEvent/leaveEvent 控制显示。
        text_lay.addWidget(self._desc_lbl)

        lay.addWidget(text_box, 1, Qt.AlignmentFlag.AlignVCenter)

        self._apply_overrides()

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    def set_callback(self, callback):
        if callback is None:
            if self._callback is not None:
                try:
                    self.clicked.disconnect(self._callback)
                except (TypeError, RuntimeError):
                    pass
                self._callback = None
            return
        if self._callback is not None:
            try:
                self.clicked.disconnect(self._callback)
            except (TypeError, RuntimeError):
                pass
        self.clicked.connect(callback)
        self._callback = callback

    @property
    def name(self) -> str:
        """原始名（dispatch key），不会变。"""
        return self._name

    @property
    def display_name(self) -> str:
        """当前显示名（应用 override.name）。"""
        return self._display_name

    @property
    def group(self) -> str:
        return self._group

    @property
    def current_desc(self) -> str:
        return self._desc_text

    @property
    def current_order(self):
        """当前 override.order；未设返回 None。"""
        return self._current_order

    @current_order.setter
    def current_order(self, v):
        self._current_order = v

    @property
    def original_order(self) -> int:
        """discover 阶段按文件前缀定的默认顺序（主程序注入）。"""
        return self._original_order

    @original_order.setter
    def original_order(self, v: int):
        self._original_order = v

    @property
    def effective_order(self) -> int:
        """最终排序权重：override.order 优先；未设回退 original_order。"""
        return self._current_order if self._current_order is not None else self._original_order

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._callback is not None:
                self._callback(self._name)
            else:
                self.clicked.emit(self._name)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_QSS)
        a_name = QAction('编辑名称', self)
        a_desc = QAction('编辑简介', self)
        a_icon = QAction('编辑图标', self)
        a_order = QAction('编辑排序', self)
        a_reset = QAction('重置默认', self)
        a_name.triggered.connect(self._edit_name)
        a_desc.triggered.connect(self._edit_desc)
        a_icon.triggered.connect(self._edit_icon)
        a_order.triggered.connect(self._edit_order)
        a_reset.triggered.connect(self._reset_overrides)
        for a in (a_name, a_desc, a_icon, a_order):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(a_reset)
        menu.exec(event.globalPos())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_desc()

    def enterEvent(self, event):
        """鼠标进入卡片 → 弹自建浅色 tooltip（绕开 Qt native QTipLabel 在
        Windows 11 暗色主题下的黑色背景）。

        不论描述是否被精简，**所有卡片**都弹完整文案（用户 hover 是想看全量）。
        """
        if not hasattr(self, '_desc_lbl'):
            super().enterEvent(event)
            return
        if self._desc_text:
            _TooltipBubble.show_bubble(self._desc_text, anchor=self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        _TooltipBubble.hide_bubble()
        super().leaveEvent(event)

    # ------------------------------------------------------------------
    # 覆盖层 apply + 编辑动作
    # ------------------------------------------------------------------
    def _apply_overrides(self):
        ov = card_overrides.get_tool_overrides(self._group, self._name)

        # 名称
        self._display_name = ov['name'] or self._name
        if self._name_lbl.text() != self._display_name:
            self._name_lbl.setText(self._display_name)

        # 描述
        self._desc_text = ov['desc'] or self._original_hint
        self._refresh_desc()

        # 排序
        self._current_order = ov['order']

        # 图标
        if ov['icon']:
            pm = _resize_icon(ov['icon'], _ICON_SIZE)
            if pm is not None:
                self._icon_lbl.setPixmap(pm)
                self._icon_lbl.setText('')
                self._icon_lbl.setStyleSheet(
                    'QLabel{background:transparent;border:none;}')
            else:
                self._render_default_icon()
        else:
            self._render_default_icon()

    def _render_default_icon(self):
        """单字符 + 哈希分色色块（用户未上传图标时的占位）。"""
        # 用「显示名」首字，保证用户改名称后图标跟着变
        seed = self._display_name or self._name
        initial = (seed[:1] if seed else '·')
        color = _ICON_PALETTE[hash(seed) % len(_ICON_PALETTE)]
        self._icon_lbl.setPixmap(QPixmap())
        self._icon_lbl.setText(initial)
        self._icon_lbl.setStyleSheet(
            'QLabel{background:%s;color:#fff;font-size:14px;font-weight:700;'
            'border-radius:6px;qproperty-alignment:AlignCenter;}' % color)

    def _refresh_desc(self):
        if not hasattr(self, '_desc_lbl'):
            return
        fm = QFontMetrics(self._desc_lbl.font())
        max_w = max(60, self.width() - _DESC_KEEP)
        elided = fm.elidedText(self._desc_text, Qt.ElideRight, max_w)
        self._desc_lbl.setText(elided)
        # 不再用 setToolTip（避免 Qt native QTipLabel 在暗色主题下变黑）；
        # 自建 _TooltipBubble 由 enterEvent/leaveEvent 控制显示。

    # ---- 编辑动作 ----
    def _edit_name(self):
        text, ok = get_text(
            self, f'编辑「{self._name}」的名称', '名称（留空恢复默认）',
            self._display_name, placeholder='输入新名称')
        if not ok:
            return
        text = (text or '').strip()
        card_overrides.set_tool_name(self._group, self._name, text)
        self._apply_overrides()
        self.name_changed.emit(self._display_name)
        self.overrides_changed.emit()

    def _edit_desc(self):
        text, ok = get_multiline(
            self, f'编辑「{self._name}」的简介', '简介（多行；留空恢复默认）',
            self._desc_text)
        if not ok:
            return
        card_overrides.set_tool_desc(self._group, self._name, text)
        self._apply_overrides()
        self.overrides_changed.emit()

    def _edit_icon(self):
        dlg = QFileDialog(self, f'选择「{self._name}」的图标（png / jpg / jpeg）',
                          os.getcwd(), '图片 (*.png *.jpg *.jpeg)')
        dlg.setStyleSheet(FILE_DIALOG_QSS)
        if dlg.exec() != QFileDialog.Accepted or not dlg.selectedFiles():
            return
        path = dlg.selectedFiles()[0]
        pm = _resize_icon(path, 128)
        if pm is None or pm.isNull():
            QMessageBox.warning(self, '图标错误', f'无法读取图片：{path}')
            return
        os.makedirs(card_overrides.ICON_CACHE_DIR, exist_ok=True)
        ext = os.path.splitext(path)[1].lower() or '.png'
        safe = f'{self._group}_{self._name}'.replace('/', '_').replace('\\', '_')
        cache_path = os.path.join(card_overrides.ICON_CACHE_DIR, safe + ext)
        if not pm.save(cache_path, 'PNG' if ext == '.png' else None):
            QMessageBox.warning(self, '图标错误', '写入缓存目录失败，请检查权限')
            return
        card_overrides.set_tool_icon(self._group, self._name, cache_path)
        self._apply_overrides()
        self.overrides_changed.emit()

    def _edit_order(self):
        cur = '' if self._current_order is None else str(self._current_order)
        text, ok = get_text(
            self, f'编辑「{self._name}」的排序',
            '排序（数字越小越靠前；留空回退目录前缀）',
            cur, placeholder='例如 0 / 5 / 99')
        if not ok:
            return
        val = _safe_int(text)
        if val is None and (text or '').strip():
            QMessageBox.warning(self, '排序值无效', '请输入整数，或留空恢复默认')
            return
        card_overrides.set_tool_order(self._group, self._name, val)
        self._apply_overrides()
        self.order_changed.emit()
        self.overrides_changed.emit()

    def _reset_overrides(self):
        card_overrides.clear_tool(self._group, self._name)
        self._apply_overrides()
        self.overrides_changed.emit()

    # ------------------------------------------------------------------
    # 调试用
    # ------------------------------------------------------------------
    def clear_overrides_silently(self):
        card_overrides.clear_tool(self._group, self._name)
        self._apply_overrides()


# ==================================================================
# 自建 Tooltip 浮层（绕开 Qt native QTipLabel 在暗色主题下的黑色 bug）
# ==================================================================
class _TooltipBubble(QWidget):
    """单例浮层：鼠标悬停 ToolItem 时显示完整描述。

    之所以自建：PySide6 6.5+ 在 Windows 11 暗色主题下，QTipLabel 的
    调色板是 native 接管，setPalette / setStyleSheet 都没法把它变浅，
    出现"黑色长方形 + 看不到字"（实测：Window=Window=ToolTipBase=#000000）。
    自建一个无边框 QWidget + QLabel，浅色样式完全可控。
    """

    _INSTANCE: '_TooltipBubble | None' = None
    _HIDE_TIMER: 'QTimer | None' = None

    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setObjectName('windkitTooltipBubble')
        self.setStyleSheet("""
            QWidget#windkitTooltipBubble {
                background: #fffde8;
                border: 1px solid #d8dce0;
                border-radius: 4px;
            }
            QLabel {
                color: #1f3b4d;
                font-size: 12px;
                background: transparent;
                padding: 6px 10px;
            }
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._lbl = QLabel()
        self._lbl.setWordWrap(True)
        self._lbl.setMaximumWidth(360)
        lay.addWidget(self._lbl)

    def set_text(self, text: str):
        self._lbl.setText(text)
        self._lbl.adjustSize()
        self.adjustSize()

    @classmethod
    def show_bubble(cls, text: str, anchor: QWidget):
        if cls._INSTANCE is None:
            cls._INSTANCE = cls()
        bubble = cls._INSTANCE
        bubble.set_text(text)
        # 定位：anchor 底部下方 6px；超出屏幕右则左移
        global_pos = anchor.mapToGlobal(QPoint(0, anchor.height() + 6))
        bubble.move(global_pos)
        bubble.show()
        bubble.raise_()
        # 6 秒后自动消失（与 app.setToolTipDuration(8000) 对齐）
        if cls._HIDE_TIMER is None:
            cls._HIDE_TIMER = QTimer()
            cls._HIDE_TIMER.setSingleShot(True)
            cls._HIDE_TIMER.timeout.connect(cls.hide_bubble)
        cls._HIDE_TIMER.start(6000)

    @classmethod
    def hide_bubble(cls):
        if cls._HIDE_TIMER is not None:
            cls._HIDE_TIMER.stop()
        if cls._INSTANCE is not None:
            cls._INSTANCE.hide()

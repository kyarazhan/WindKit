"""WindKit 主窗口：分类导航 + 卡片网格 + 搜索 + 快捷键 + 统一调度。

布局：
- 顶部一级分类 Tab（pill 样式，可选图标；选中态实色填充）；
- 搜索框（模糊匹配工具名/描述）；
- 下方卡片网格：本分类下全部工具；
- 顶栏最右端「帮助」按钮。

快捷键：
- Ctrl+1~9：切换分类
- Ctrl+F：聚焦搜索框
"""

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QMainWindow, QMenu, QMessageBox, QPushButton,
                               QStackedWidget, QVBoxLayout, QLineEdit, QWidget)

from core.paths import resource_path, user_data_dir
from core.version import VERSION
from ui import card_overrides
from ui._dialogs import get_text
from ui._style import FILE_DIALOG_QSS, MENU_QSS
from ui.tool_dispatcher import ToolDispatcher
from ui.tool_item import ToolItem, _safe_int
from ui.update_tools import UpdateMixin

ICON = resource_path('icon.png')

_PRIMARY_TABQSS = """
    QPushButton#primaryTab {
        background: #ffffff;
        color: #475569;
        border: 1px solid #d6dde6;
        border-radius: 14px;
        padding: 4px 14px;
        font-size: 12px;
    }
    QPushButton#primaryTab:hover {
        background: #eef3f8;
        border-color: #b9c5d4;
    }
    QPushButton#primaryTab:checked {
        background: #3b82f6;
        color: #ffffff;
        border-color: #3b82f6;
    }
    QPushButton#primaryTab:checked:hover {
        background: #2563eb;
        border-color: #2563eb;
    }
"""

_HELP_BTNQSS = """
    QPushButton#helpBtn {
        background: transparent;
        color: #475569;
        border: none;
        padding: 4px 14px;
        font-size: 12px;
    }
    QPushButton#helpBtn:hover {
        color: #185fa5;
    }
"""

_SEARCH_QSS = """
    QLineEdit#searchBox {
        background: #f5f7fb;
        border: 1px solid #d6dde6;
        border-radius: 14px;
        padding: 4px 12px;
        font-size: 12px;
        color: #475569;
        min-width: 180px;
        max-width: 260px;
    }
    QLineEdit#searchBox:focus {
        border-color: #3b82f6;
        background: #ffffff;
    }
"""

CARD_COLS = 4

_DEFAULT_GROUP_DISPLAY = {
    '风资源分析': '风能分析',
    '机型与电量': '机组信息',
    '载荷与工况': '载荷工况',
}
_DEFAULT_GROUP_ORDER_HINT = {'机组信息': 999}


class ToolboxWindow(UpdateMixin, QMainWindow):
    """WindKit 主窗口：顶部分类 Tab + 搜索 + 卡片网格 + 统一调度。"""

    def __init__(self, title: str = 'WindKit · 风资源工具箱'):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(1180, 760)
        if os.path.exists(ICON):
            self.setWindowIcon(QIcon(ICON.replace('\\', '/')))

        self.dispatcher = ToolDispatcher(resource_path('plugins'))
        self.groups, self.failures = self.dispatcher.discover()

        central = QWidget()
        central.setObjectName('centralBg')
        central.setStyleSheet('QWidget#centralBg { background: #f5f7fb; }')
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._top_bar = QFrame()
        self._top_bar.setObjectName('topBar')
        self._top_bar.setStyleSheet(
            'QFrame#topBar { background: #ffffff; border-bottom: 1px solid #e3e8ef; }')
        self._top_lay = QHBoxLayout(self._top_bar)
        self._top_lay.setContentsMargins(16, 10, 16, 10)
        self._top_lay.setSpacing(8)

        self.primary_buttons = []

        self.stack = QStackedWidget()
        self.stack.setObjectName('cardStack')

        root.addWidget(self._top_bar)
        root.addWidget(self.stack, 1)

        self._refresh_layout()
        self._setup_shortcuts()
        self._setup_update()
        self._report_discover_result()

    def _report_discover_result(self):
        """装载结果：状态栏摘要 + 明细落 data/plugin_load_errors.log
        （打包模式下的装载问题只能靠这份日志定位，每次启动整写一份）。"""
        loaded = sum(len(items) for _, items in self.groups)
        if self.failures:
            status = (f'就绪（{len(self.failures)} 个插件装载失败，'
                      f'已跳过；明细见 data/plugin_load_errors.log）')
        else:
            status = f'就绪（{loaded} 个工具已装载）'
        self.statusBar().showMessage(status)
        try:
            from datetime import datetime
            log_path = os.path.join(user_data_dir(),
                                    'plugin_load_errors.log')
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(f'WindKit v{VERSION} · '
                        f'{datetime.now():%Y-%m-%d %H:%M:%S} · '
                        f'装载成功 {loaded} / 失败 {len(self.failures)}\n')
                for line in self.failures:
                    f.write('- ' + line + '\n')
        except OSError:
            pass

    def _setup_shortcuts(self):
        """注册全局快捷键。"""
        for i in range(1, 10):
            shortcut = QKeySequence(f'Ctrl+{i}')
            action = QAction(self)
            action.setShortcut(shortcut)
            action.triggered.connect(lambda _checked, idx=i-1: self._show_category(idx))
            self.addAction(action)

        search_action = QAction(self)
        search_action.setShortcut(QKeySequence('Ctrl+F'))
        search_action.triggered.connect(self._focus_search)
        self.addAction(search_action)

    def _focus_search(self):
        if hasattr(self, '_search_edit') and self._search_edit:
            self._search_edit.setFocus()
            self._search_edit.selectAll()

    def _compute_displayed_groups(self):
        out = []
        for gidx, (gkey, items) in enumerate(self.groups):
            ov = card_overrides.get_group_overrides(gkey)
            display = ov['name'] or _DEFAULT_GROUP_DISPLAY.get(gkey, gkey)
            if ov['order'] is not None:
                eff = ov['order']
            elif display in _DEFAULT_GROUP_ORDER_HINT and ov['name'] == '':
                eff = _DEFAULT_GROUP_ORDER_HINT[display]
            else:
                eff = gidx

            item_list = []
            for iidx, info in enumerate(items):
                tov = card_overrides.get_tool_overrides(gkey, info.name)
                eff_item = tov['order'] if tov['order'] is not None else iidx
                item_list.append((eff_item, info, tov))
            item_list.sort(key=lambda x: (x[0], x[1].name))

            out.append({
                'key': gkey, 'display': display, 'eff_order': eff,
                'icon': ov['icon'], 'items': item_list,
            })
        out.sort(key=lambda x: (x['eff_order'], x['key']))
        return out

    def _refresh_layout(self):
        while self.stack.count() > 0:
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.setParent(None)
            w.deleteLater()

        while self._top_lay.count() > 0:
            item = self._top_lay.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.primary_buttons.clear()
        self.help_btn = None
        self._search_edit = None

        groups = self._compute_displayed_groups()
        for gi, g in enumerate(groups):
            btn = QPushButton(g['display'])
            btn.setObjectName('primaryTab')
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(_PRIMARY_TABQSS)
            if g['icon'] and os.path.exists(g['icon']):
                btn.setIcon(QIcon(g['icon']))
                btn.setIconSize(QSize(14, 14))
            btn.clicked.connect(lambda _checked, idx=gi: self._show_category(idx))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, idx=gi: self._on_tab_context_menu(idx, pos))
            self._top_lay.addWidget(btn)
            self.primary_buttons.append(btn)

            page = self._make_category_widget(g['key'], g['items'])
            self.stack.addWidget(page)

        self._top_lay.addStretch(1)

        self._search_edit = QLineEdit()
        self._search_edit.setObjectName('searchBox')
        self._search_edit.setPlaceholderText('搜索工具... (Ctrl+F)')
        self._search_edit.setStyleSheet(_SEARCH_QSS)
        self._search_edit.textChanged.connect(self._on_search)
        self._top_lay.addWidget(self._search_edit)

        self.help_btn = QPushButton('帮助')
        self.help_btn.setObjectName('helpBtn')
        self.help_btn.setCursor(Qt.PointingHandCursor)
        self.help_btn.setStyleSheet(_HELP_BTNQSS)
        help_menu = QMenu(self)
        help_menu.setStyleSheet(MENU_QSS)
        a_update = QAction('检查更新', self)
        a_update.triggered.connect(self._open_update)
        a_about = QAction('关于 WindKit', self)
        a_about.triggered.connect(self._about)
        help_menu.addAction(a_update)
        help_menu.addAction(a_about)
        self.help_btn.setMenu(help_menu)
        self._top_lay.addWidget(self.help_btn)

        if self.primary_buttons:
            self._show_category(0)

    def _on_search(self, text: str):
        """搜索框文本变化时过滤卡片显示。"""
        query = text.strip().lower()
        if not query:
            for i in range(self.stack.count()):
                page = self.stack.widget(i)
                page.setVisible(True)
            return

        matched_groups = set()
        for gi, g in enumerate(self._compute_displayed_groups()):
            page = self.stack.widget(gi)
            if page is None:
                continue
            has_match = False
            for _eff, info, _tov in g['items']:
                if query in info.name.lower() or query in info.hint.lower():
                    has_match = True
                    break
            page.setVisible(has_match)
            if has_match:
                matched_groups.add(gi)

        if matched_groups:
            first = min(matched_groups)
            self._show_category(first)

    def _make_category_widget(self, gkey: str, sorted_items):
        widget = QWidget()
        widget.setStyleSheet('background: transparent;')
        wrap = QVBoxLayout(widget)
        wrap.setContentsMargins(20, 18, 20, 18)
        wrap.setSpacing(12)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        for c in range(CARD_COLS):
            grid.setColumnStretch(c, 1)

        for idx, (_eff, info, _tov) in enumerate(sorted_items):
            card = ToolItem(name=info.name, hint=info.hint, group=gkey)
            card.original_order = idx
            card.set_callback(self._on_tool_click)
            card.overrides_changed.connect(self._on_card_overrides_changed)
            r, c = divmod(idx, CARD_COLS)
            grid.addWidget(card, r, c)

        wrap.addLayout(grid)
        wrap.addStretch(1)
        return widget

    def _on_tool_click(self, name: str):
        self.dispatcher.open_tool(name)

    def _show_category(self, idx: int):
        if idx < 0 or idx >= len(self.primary_buttons):
            return
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.primary_buttons):
            btn.setChecked(i == idx)

    def _on_card_overrides_changed(self):
        self._refresh_layout()

    def _on_tab_context_menu(self, gi: int, pos):
        groups = self._compute_displayed_groups()
        if gi < 0 or gi >= len(groups):
            return
        g = groups[gi]
        btn = self.primary_buttons[gi]

        menu = QMenu(self)
        menu.setStyleSheet(MENU_QSS)
        a_name = QAction('编辑名称', self)
        a_icon = QAction('编辑图标', self)
        a_order = QAction('编辑排序', self)
        a_reset = QAction('重置默认', self)
        a_name.triggered.connect(lambda: self._edit_group_name(g['key'], g['display']))
        a_icon.triggered.connect(lambda: self._edit_group_icon(g['key']))
        a_order.triggered.connect(lambda: self._edit_group_order(g['key']))
        a_reset.triggered.connect(lambda: self._reset_group(g['key']))
        menu.addAction(a_name)
        menu.addAction(a_icon)
        menu.addAction(a_order)
        menu.addSeparator()
        menu.addAction(a_reset)
        menu.exec(btn.mapToGlobal(pos))

    def closeEvent(self, event):
        self._stop_update()
        self.dispatcher.close_all()
        super().closeEvent(event)

    def _about(self):
        QMessageBox.about(
            self, '关于 WindKit',
            f'WindKit · 风资源工程小工具箱 v{VERSION}\n\n'
            '插件式架构：功能页置于 plugins/ 目录，启动时自动发现装载。\n'
            '主程序仅负责分类入口与统一调度，工具窗口由调度器统一构造。\n'
            '点击卡片弹出独立工具窗口，关闭即可回到主界面。\n'
            '右键点击分类 Tab 或卡片可编辑名称/图标/简介/排序，所有改动可持久化。\n\n'
            '快捷键：Ctrl+1~9 切换分类 | Ctrl+F 搜索')

    def _edit_group_name(self, gkey: str, current_display: str):
        text, ok = get_text(
            self, f'编辑「{gkey}」的显示名',
            '显示名（留空恢复默认；不影响 dispatch key）',
            current_display, placeholder='输入新名称')
        if not ok:
            return
        card_overrides.set_group_name(gkey, (text or '').strip())
        self._refresh_layout()

    def _edit_group_icon(self, gkey: str):
        dlg = QFileDialog(self, f'选择「{gkey}」的图标（png / jpg / jpeg）',
                          os.getcwd(), '图片 (*.png *.jpg *.jpeg)')
        dlg.setStyleSheet(FILE_DIALOG_QSS)
        if dlg.exec() != QFileDialog.Accepted or not dlg.selectedFiles():
            return
        path = dlg.selectedFiles()[0]
        from ui.tool_item import _resize_icon
        pm = _resize_icon(path, 128)
        if pm is None or pm.isNull():
            QMessageBox.warning(self, '图标错误', f'无法读取图片：{path}')
            return
        os.makedirs(card_overrides.ICON_CACHE_DIR, exist_ok=True)
        ext = os.path.splitext(path)[1].lower() or '.png'
        cache_path = os.path.join(card_overrides.ICON_CACHE_DIR, f'group_{gkey}' + ext)
        if not pm.save(cache_path, 'PNG' if ext == '.png' else None):
            QMessageBox.warning(self, '图标错误', '写入缓存目录失败，请检查权限')
            return
        card_overrides.set_group_icon(gkey, cache_path)
        self._refresh_layout()

    def _edit_group_order(self, gkey: str):
        ov = card_overrides.get_group_overrides(gkey)
        cur = '' if ov['order'] is None else str(ov['order'])
        text, ok = get_text(
            self, f'编辑「{gkey}」的排序',
            '排序（数字越小越靠前；留空回退目录前缀）',
            cur, placeholder='例如 0 / 5 / 99')
        if not ok:
            return
        val = _safe_int(text)
        if val is None and (text or '').strip():
            QMessageBox.warning(self, '排序值无效', '请输入整数，或留空恢复默认')
            return
        card_overrides.set_group_order(gkey, val)
        self._refresh_layout()

    def _reset_group(self, gkey: str):
        card_overrides.clear_group(gkey)
        self._refresh_layout()

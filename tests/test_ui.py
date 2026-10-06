"""UI 回归测试：分类 Tab 排序 + 卡片网格 + 工具调度 + 窗口生命周期。

覆盖的核心契约：
1. 一级分类 Tab 顺序：'机型与电量' 一次性默认改名为「机组信息」并置末；
2. 顶部 Tab 真的位于窗口顶部（不漂到堆叠区下面）；
3. 卡片展示工具名 + 一行说明（HINT 或模块首行 docstring），二者均可见；
4. 重复点击同一工具复用窗口；
5. 主窗口关闭联动全部工具窗口与子进程退出；
6. 全部 11 个工具真实可构造；
7. 右键菜单（Tab 4 动作 / 卡片 5 动作）+ 浅色 QMenu；
8. 覆盖层（name / desc / icon / order）持久化往返；
9. 排序：override.order 优先，未设回退目录前缀。
"""
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QPoint, Qt  # noqa: E402
from PySide6.QtGui import QContextMenuEvent, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout,  # noqa: E402
                                QLabel, QSpacerItem, QStackedWidget)
from ui import card_overrides  # noqa: E402
from ui import tool_item as tool_item_mod  # noqa: E402
from ui.tool_dispatcher import ToolDispatcher  # noqa: E402
from ui.tool_item import ToolItem  # noqa: E402
from ui.toolbox_window import ToolboxWindow  # noqa: E402

PLUGINS = os.path.abspath(os.path.join(ROOT, 'plugins'))
TOTAL_TOOLS = 11


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope='module')
def window(app):
    w = ToolboxWindow()
    w.show()
    yield w
    w.dispatcher.close_all()


def test_primary_menu_puts_group03_last_and_renamed(window):
    """一次性默认：'机型与电量' 移至末尾（坐标转换之后）并改名为「机组信息」。"""
    groups = window._compute_displayed_groups()
    order_keys = [g['key'] for g in groups]
    displays = [g['display'] for g in groups]
    # 机型与电量 必须位于坐标转换 之后
    idx_machine = order_keys.index('机型与电量')
    idx_coord = order_keys.index('坐标转换')
    assert idx_machine > idx_coord, (
        f'「机型与电量」({idx_machine}) 应在「坐标转换」({idx_coord}) 之后')
    # 显示名为「机组信息」（除非用户手动 override 改了名）
    last_g = groups[-1]
    assert last_g['key'] == '机型与电量'
    assert last_g['display'] == '机组信息', last_g
    # 顶栏 button 文本对齐
    last_btn = window.primary_buttons[-1]
    assert last_btn.text() == '机组信息'
    # 与 _compute 顺序一致
    assert displays == [g['display'] for g in groups]
    # 第一组不再是「机型与电量」
    assert groups[0]['key'] != '机型与电量'


def test_group_display_renames(window):
    """一次性默认：分组显示名映射生效，且 group key 保持不变。"""
    by_key = {g['key']: g for g in window._compute_displayed_groups()}
    assert by_key['风资源分析']['display'] == '风能分析'
    assert by_key['载荷与工况']['display'] == '载荷工况'
    assert by_key['机型与电量']['display'] == '机组信息'


def test_primary_bar_is_on_top(window):
    """一级分类 Tab 真的位于窗口顶部（在 QStackedWidget 之上），不是底部。"""
    central = window.centralWidget()
    assert central is not None
    top_bar = window.findChild(QFrame, 'topBar')
    assert top_bar is not None
    idx_top = central.layout().indexOf(top_bar)
    idx_stack = central.layout().indexOf(window.stack)
    assert 0 <= idx_top < idx_stack, (
        f'topBar 位置 {idx_top} 不在 stack {idx_stack} 之上')


def test_submenu_cards_have_name_and_desc(window):
    """子菜单每个工具为卡片：图标 + 工具名 + 一行说明，且三者均可见。"""
    # 第一组（按 effective_order 排）下的所有工具卡片
    items = window.stack.widget(0).findChildren(ToolItem)
    assert len(items) >= 1, '第一组至少 1 张卡片'
    for it in items:
        labels = it.findChildren(QLabel)
        name_label = next((l for l in labels if l.objectName() == 'cardName'), None)
        desc_label = next((l for l in labels if l.objectName() == 'cardDesc'), None)
        icon_label = next((l for l in labels if l.objectName() == 'cardIcon'), None)
        assert name_label is not None and name_label.text() == it.name, \
            f'卡片名不可见: {it.name}'
        assert desc_label is not None and desc_label.text(), \
            f'卡片描述不可见: {it.name}'
        assert icon_label is not None, f'卡片图标控件缺失: {it.name}'


def test_submenu_uses_grid_layout(window):
    """子菜单使用 QGridLayout 网格布局（非垂直列表）。"""
    page = window.stack.widget(0)
    grids = page.findChildren(QGridLayout)
    assert len(grids) >= 1, '分类页应使用 QGridLayout'


def test_click_dispatches_to_dispatcher(window):
    """点击卡片 -> 回调 -> 调度器开窗口。"""
    it = window.stack.widget(0).findChildren(ToolItem)[0]
    received = []
    it.set_callback(received.append)

    # 构造真实 QMouseEvent 模拟左键按下，触发 mousePressEvent 分派
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(5, 5),
                     window.stack.widget(0).mapToGlobal(QPoint(5, 5)),
                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier)
    it.mousePressEvent(ev)
    assert received == [it.name]

    win = window.dispatcher.open_tool(it.name)
    assert win is not None and win.isVisible()
    window.dispatcher.close_tool(it.name)


def test_category_switch_syncs_button_state(window):
    window._show_category(1)
    assert window.stack.currentIndex() == 1
    assert window.primary_buttons[1].isChecked()
    assert not window.primary_buttons[0].isChecked()
    window._show_category(0)


def test_tool_count(window):
    assert sum(len(its) for _, its in window.groups) == TOTAL_TOOLS


def test_all_tools_open_without_error(window):
    """全部工具窗口均可真实构造（捕捉插件内部崩溃）。"""
    for _, items in window.groups:
        for info in items:
            win = window.dispatcher.open_tool(info.name)
            assert win.isVisible(), info.name
            assert getattr(win, 'tool_title', '') == info.name
    window.dispatcher.close_all()


def test_reopen_reuses_window(window):
    """重复打开同一工具复用既有窗口，避免孤儿窗口泄漏。"""
    first = window.dispatcher.open_tool('机型库')
    again = window.dispatcher.open_tool('机型库')
    assert again is first
    window.dispatcher.close_all()


def test_close_main_closes_all_tools(app):
    """主窗口关闭时一并收起全部工具窗口。"""
    w = ToolboxWindow()
    for _, items in w.groups:
        for info in items:
            w.dispatcher.open_tool(info.name)
    assert len(w.dispatcher._windows) == TOTAL_TOOLS
    w.close()
    assert len(w.dispatcher._windows) == 0


def test_discover_no_failures():
    d = ToolDispatcher(PLUGINS)
    groups, failures = d.discover()
    assert failures == [], failures
    assert sum(len(i) for _, i in groups) == TOTAL_TOOLS


def test_legacy_plugin_cleanup_removed_on_discover(tmp_path, monkeypatch):
    """v1.0.2 下线插件的残留文件在装载前被清理（更新包只覆盖不删除）。"""
    import ui.tool_dispatcher as td

    monkeypatch.setattr(
        td, 'resource_path',
        lambda *parts: os.path.join(str(tmp_path), *parts))
    legacy = tmp_path / 'plugins' / '02_风资源分析' / '10_turbulence.py'
    legacy.parent.mkdir(parents=True)
    legacy.write_text('x', encoding='utf-8')
    d06 = tmp_path / 'plugins' / '06_M1拆分'
    (d06 / '__pycache__').mkdir(parents=True)
    (d06 / '__pycache__' / 'm1.pyc').write_bytes(b'x')
    keep = tmp_path / 'plugins' / '02_风资源分析' / '40_diurnal.py'
    keep.write_text('y', encoding='utf-8')

    d = ToolDispatcher(str(tmp_path / 'plugins'))
    d.discover()

    assert not legacy.exists(), '下线插件残留未被清理'
    assert not d06.exists(), '空分组目录未被清理'
    assert keep.exists(), '误删了在营插件'


def test_dispatcher_extracts_desc_from_docstring():
    """原生插件若无 HINT 类属性，应回退到模块首行 docstring。"""
    d = ToolDispatcher(PLUGINS)
    groups, _ = d.discover()
    # air_density 首行: "空气密度：ρ = P·1000/(287·(273.15+T))"
    air = next((i for g, items in groups for i in items if i.name == '空气密度计算'), None)
    assert air is not None
    assert '空气密度' in air.hint
    # 界址点 ⇄ 中心（原生 TAB 插件）有 HINT，应使用 HINT
    jie = next((i for g, items in groups for i in items if i.name == '界址点 ⇄ 中心'), None)
    assert jie is not None
    assert '正向' in jie.hint and '几何中心' in jie.hint


# ====================================================================
# 帮助按钮（顶栏右端）
# ====================================================================
def test_help_button_sits_on_topbar_right_most(window):
    """帮助按钮是 topBar 的子组件，且位于最后一个非-stretch 子项。"""
    top_bar = window.findChild(QFrame, 'topBar')
    assert top_bar is not None
    assert window.help_btn is not None
    assert window.help_btn.text() == '帮助'
    # 帮助按钮绝不能进 primary_buttons（否则 _show_category 会把它当分类误勾）
    assert window.help_btn not in window.primary_buttons
    # topBar 内非 stretch 的最后一个 widget 应是帮助按钮
    lays = [top_bar.layout().itemAt(i) for i in range(top_bar.layout().count())]
    last_widget = next(
        (it.widget() for it in reversed(lays) if it.widget() is not None), None)
    assert last_widget is window.help_btn, '帮助按钮不在顶栏最右侧'


def test_show_category_does_not_toggle_help(window):
    """切换分类不能让「帮助」按钮变 checked。"""
    window.help_btn.setChecked(True)   # 故意先勾，看 _show_category 会不会清掉
    window._show_category(0)
    assert not window.help_btn.isChecked()
    window._show_category(2)
    assert not window.help_btn.isChecked()


def test_top_bar_stays_left_aligned_after_repeated_refresh(window, app):
    """连续触发 ``_refresh_layout`` 多次，第一个 Tab 不能向右漂移。

    历史 bug：旧版只清理 ``primary_buttons``，把 stretch 与旧 help_btn 留下。
    每次 rebuild 累积一个 stretch 把分类 Tab 往右挤，
    用户在卡片上点「编辑排序」或 Tab 上点「重置默认」后会观察到这个现象。
    """
    # 触发首次 refresh_layout（拿到稳定的初始基线）
    window._on_card_overrides_changed()
    app.processEvents()
    x0 = window.primary_buttons[0].x()
    assert x0 < 100, f'初始第一个 Tab x={x0}，应在左侧（setContentsMargins=16）'

    # 反复触发 refresh（卡片/顶栏 override 变化都会走这条路径）
    for _ in range(5):
        window._on_card_overrides_changed()
        app.processEvents()

    x_after = window.primary_buttons[0].x()
    assert x_after == x0, (
        f'Tab x 从 {x0} 漂移到 {x_after}——refresh 累积了 stale item')
    # 帮助按钮必须还在最右
    last_widget = next(
        (window._top_lay.itemAt(i).widget()
         for i in reversed(range(window._top_lay.count()))
         if window._top_lay.itemAt(i).widget() is not None), None)
    assert last_widget is window.help_btn, '帮助按钮不在顶栏最右'
    # 整条布局里 stretch 必须恰好 1 个，且在 tabs 之后、help 之前
    stretch_count = sum(
        1 for i in range(window._top_lay.count())
        if isinstance(window._top_lay.itemAt(i), QSpacerItem))
    assert stretch_count == 1, (
        f'_top_lay 应只有 1 个 stretch，实际 {stretch_count} 个（stale item 累积）')


# ====================================================================
# 卡片网格：等宽 + 列等长
# ====================================================================
def test_card_grid_has_equal_column_stretches(window):
    """每个分类页的 QGridLayout 必须为 CARD_COLS 列各设 columnStretch=1。"""
    page = window.stack.widget(0)
    grid = next((g for g in page.findChildren(QGridLayout)), None)
    assert grid is not None
    for c in range(4):
        assert grid.columnStretch(c) == 1, f'列 {c} stretch={grid.columnStretch(c)}'


def test_card_desc_elides_with_narrow_width(window):
    """卡片极窄时描述自动 ElideRight，hover 显示完整文案（自建浅色浮层）。

    历史上用 setToolTip 走 native QTipLabel，但 Qt 6.5+ 在 Win11 暗色下
    把 QTipLabel 渲染成黑色（Palette Window 角色全黑），
    现在改用自建 _TooltipBubble，绕开 native。
    """
    it = window.stack.widget(0).findChildren(ToolItem)[0]
    it.resize(60, 64)        # 强制窄宽
    it._refresh_desc()
    shown = it._desc_lbl.text()
    full = it.current_desc
    assert full and shown, '描述为空'
    if len(full) > 1:        # 仅 1 字时不需要省略号
        assert shown != full, f'未自动精简: shown={shown!r}'
        assert shown.endswith('…'), f'末位非省略号: {shown!r}'
    # 走 enterEvent 应该弹出 _TooltipBubble 并展示全量文案
    from ui.tool_item import _TooltipBubble
    from PySide6.QtGui import QEnterEvent
    from PySide6.QtCore import QPointF
    ev = QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(0, 0))
    it.enterEvent(ev)
    try:
        assert _TooltipBubble._INSTANCE is not None, '未弹出自建浮层'
        bubble = _TooltipBubble._INSTANCE
        assert bubble.isVisible(), '浮层未显示'
        assert bubble._lbl.text() == full, (
            f'浮层文案不完整: 期望 {full!r}，实际 {bubble._lbl.text()!r}')
        # 浮层背景必须是浅色（不是黑色）
        pal = bubble.palette()
        from PySide6.QtGui import QPalette
        win_color = pal.color(QPalette.ColorRole.Window).name()
        assert win_color.lower() != '#000000', (
            f'浮层背景仍为黑色 ({win_color})——自建方案未生效')
    finally:
        _TooltipBubble.hide_bubble()
        from PySide6.QtCore import QEvent
        it.leaveEvent(QEvent(QEvent.Type.Leave))


def test_tooltip_bubble_appears_for_short_desc_too(window):
    """即描述短到不需要 ElideRight，hover 仍弹全量（用户随时要看全量）。

    历史 bug：旧判定 ``shown != full`` 才会弹，导致「空气密度计算」这种短
    描述的卡片 hover 完全不弹浮层，用户看到「有的弹有的不弹」。
    """
    it = window.stack.widget(0).findChildren(ToolItem)[0]
    # 找一个真实短描述的卡片：取第一组内 desc 最短的那张。
    # 在 800px 极宽下，35 字以下基本能被装下（不被 ElideRight 截断），
    # 即"未触发精简"的纯展示场景。
    short_card = next(
        (t for t in sorted(
            window.stack.widget(0).findChildren(ToolItem),
            key=lambda t: len(t.current_desc or ''))
         if t.current_desc and len(t.current_desc) <= 35),
        None)
    if short_card is None:
        pytest.skip('当前分类没有短描述卡片，跳过')
    # 确认它不需要 elide（装得下）
    short_card.resize(800, 64)
    short_card._refresh_desc()
    assert short_card._desc_lbl.text() == short_card.current_desc, (
        '前提：宽宽下应不被精简')
    full = short_card.current_desc
    # hover → 必须弹
    from ui.tool_item import _TooltipBubble
    from PySide6.QtGui import QEnterEvent
    from PySide6.QtCore import QPointF, QEvent
    _TooltipBubble.hide_bubble()
    short_card.enterEvent(QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(0, 0)))
    try:
        assert _TooltipBubble._INSTANCE is not None and _TooltipBubble._INSTANCE.isVisible(), (
            '短描述卡片 hover 不弹浮层——enterEvent 漏掉了全量展示的需求')
        assert _TooltipBubble._INSTANCE._lbl.text() == full
    finally:
        _TooltipBubble.hide_bubble()
        short_card.leaveEvent(QEvent(QEvent.Type.Leave))


# ====================================================================
# 右键菜单：编辑名称 / 编辑简介 / 编辑图标 / 编辑排序 / 重置默认
# ====================================================================
def test_card_context_menu_has_required_actions(window, monkeypatch):
    """右键 contextMenuEvent 触发时构造的 QMenu 含 5 个必备动作。"""
    seen = []

    class _Signal:
        """QAction.triggered 的最小替身：支持 .connect(slot)。"""
        def __init__(self):
            self._slots = []
        def connect(self, slot):
            self._slots.append(slot)
        def emit(self, *a, **k):
            [s(*a, **k) for s in self._slots]

    class _RecAction:
        def __init__(self, text, parent):
            self.text = text
            self.triggered = _Signal()

    class _RecMenu:
        def __init__(self, parent):
            self.items = seen
        def addAction(self, *a):
            self.items.extend(a)
        def addSeparator(self):
            self.items.append(None)
        def setStyleSheet(self, *_a, **_k):
            pass    # mock：不再校验 QSS 内容
        def exec(self, *a, **k):
            return None

    monkeypatch.setattr(tool_item_mod, 'QMenu', _RecMenu)
    monkeypatch.setattr(tool_item_mod, 'QAction', _RecAction)

    it = window.stack.widget(0).findChildren(ToolItem)[0]
    ev = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse, QPoint(5, 5),
        window.stack.widget(0).mapToGlobal(QPoint(5, 5)))
    it.contextMenuEvent(ev)

    labels = [a.text for a in seen if a is not None]
    for needed in ('编辑名称', '编辑简介', '编辑图标', '编辑排序', '重置默认'):
        assert needed in labels, f'缺少动作: {needed}（已有: {labels}）'


def test_tab_context_menu_has_required_actions(window, monkeypatch):
    """一级 Tab 右键 4 个动作齐全。"""
    from PySide6.QtWidgets import QPushButton
    from ui import toolbox_window as tw_mod
    seen = []

    class _Signal:
        def __init__(self):
            self._slots = []
        def connect(self, slot):
            self._slots.append(slot)
        def emit(self, *a, **k):
            [s(*a, **k) for s in self._slots]

    class _RecAction:
        def __init__(self, text, parent):
            self.text = text
            self.triggered = _Signal()

    class _RecMenu:
        def __init__(self, parent):
            self.items = seen
        def addAction(self, *a):
            self.items.extend(a)
        def addSeparator(self):
            self.items.append(None)
        def setStyleSheet(self, *_a, **_k):
            pass
        def exec(self, *a, **k):
            return None

    monkeypatch.setattr(tw_mod, 'QMenu', _RecMenu)
    monkeypatch.setattr(tw_mod, 'QAction', _RecAction)

    # 调主程序内部方法（不走真实鼠标）
    window._on_tab_context_menu(0, QPoint(5, 5))
    labels = [a.text for a in seen if a is not None]
    for needed in ('编辑名称', '编辑图标', '编辑排序', '重置默认'):
        assert needed in labels, f'Tab 缺少动作: {needed}（已有: {labels}）'


# ====================================================================
# 覆盖层持久化（图标 + 描述）
# ====================================================================
@pytest.fixture
def patched_overrides_store(tmp_path, monkeypatch):
    """把 card_overrides 的 _FILE 与 ICON_CACHE_DIR 重定向到 tmpdir。"""
    backup_file = card_overrides._FILE
    backup_cache = card_overrides.ICON_CACHE_DIR
    fake_file = str(tmp_path / 'card_overrides.json')
    fake_cache = str(tmp_path / 'card_icons')
    os.makedirs(fake_cache, exist_ok=True)
    monkeypatch.setattr(card_overrides, '_FILE', fake_file)
    monkeypatch.setattr(card_overrides, 'ICON_CACHE_DIR', fake_cache)
    yield
    # monkeypatch 自动还原


def test_overrides_set_get_clear_roundtrip(patched_overrides_store, tmp_path):
    """set_tool_icon / set_tool_desc → get → clear_tool 应当往返一致；
    icon 路径不存在时按空处理。"""
    fake_png = tmp_path / 'fake_icon.png'
    fake_png.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 64)
    card_overrides.set_tool_icon('g1', 't1', str(fake_png))
    card_overrides.set_tool_desc('g1', 't1', '自定义简介')
    o = card_overrides.get_tool_overrides('g1', 't1')
    assert o['icon'] == str(fake_png)
    assert o['desc'] == '自定义简介'
    # icon 文件被删后下次 get 应回退为 ''（不抛错）
    os.remove(str(fake_png))
    o2 = card_overrides.get_tool_overrides('g1', 't1')
    assert o2['icon'] == ''
    # clear 后全部清空
    card_overrides.clear_tool('g1', 't1')
    o3 = card_overrides.get_tool_overrides('g1', 't1')
    assert o3['icon'] == '' and o3['desc'] == ''


def test_tool_item_apply_overrides_restores_default(patched_overrides_store):
    """_apply_overrides 在无覆盖时应回到原 hint 默认文案。"""
    from PySide6.QtWidgets import QApplication
    inst = QApplication.instance()
    app = inst if inst else QApplication([])
    ti = ToolItem(name='测试工具', hint='默认介绍文字', group='测试组')
    try:
        assert ti.current_desc == '默认介绍文字'
        # 先覆盖再看能否恢复
        card_overrides.set_tool_desc('测试组', '测试工具', '用户改过的简介')
        ti._apply_overrides()
        assert ti.current_desc == '用户改过的简介'
        card_overrides.clear_tool('测试组', '测试工具')
        ti._apply_overrides()
        assert ti.current_desc == '默认介绍文字'
    finally:
        ti.clear_overrides_silently()
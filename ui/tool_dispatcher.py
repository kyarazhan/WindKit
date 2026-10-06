"""统一工具窗口调度器。

职责：
- 扫描 plugins/ 目录，按分组注册全部工具（新工具零适配接入）；
- 统一构造原生工具弹窗（动态加载插件 TAB 类），主程序不接触窗口细节；
- 提供 open_tool / close_tool / close_all 统一调度接口。

插件协议：
- 每个插件声明 ModuleTab 子类，文件尾部 ``TAB = XxxTab`` 显式暴露入口；
- 工具名取 TAB 类的 ``TITLE`` 类属性；文件名数字前缀（如 ``20_``）仅用于排序。

discover() 返回 (分组列表, 装载失败列表)：
- 分组列表: [(group_name, [ToolInfo, ...]), ...]
- 主程序仅持有分组与 ToolInfo，窗口构造统一走 open_tool(name)。
"""

import hashlib
import os
import re
import shutil
import traceback
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QVBoxLayout

from core.paths import resource_path
from ui.base_tab import ModuleTab

ICON = resource_path('icon.png')

_PREFIX = re.compile(r'^(\d+)_')

# v1.0.2 下线的插件。更新包（全量/增量）只会覆盖、不会删除文件，老安装里
# 的残留必须在此显式清理（每次装载前执行，幂等）；保留数个版本后可随
# 清理批次移除本段。
_LEGACY_PLUGIN_FILES = (
    ('plugins', '02_风资源分析', '10_turbulence.py'),
    ('plugins', '02_风资源分析', '20_long_term.py'),
    ('plugins', '02_风资源分析', '30_extreme_wind.py'),
    ('plugins', '06_M1拆分', '10_m1_split.py'),
)
_LEGACY_PLUGIN_DIRS = (
    ('plugins', '06_M1拆分'),
)


def cleanup_legacy_plugins() -> None:
    """删除已下线插件的残留文件与空分组目录（见 _LEGACY_PLUGIN_FILES）。"""
    for rel in _LEGACY_PLUGIN_FILES:
        try:
            p = resource_path(*rel)
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass
    for rel in _LEGACY_PLUGIN_DIRS:
        try:
            d = resource_path(*rel)
            # 目录里只剩 __pycache__ 时整目录删除
            if os.path.isdir(d) and not [f for f in os.listdir(d)
                                         if f != '__pycache__']:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


def _strip_prefix(name: str) -> str:
    """剥离插件文件名前的数字序号前缀（如 20_）。"""
    return _PREFIX.sub('', name)


def _extract_desc(mod) -> str:
    """提取插件的卡片副标题：HINT 类属性优先，其次模块首行 docstring，否则 '点击打开'。"""
    hint = getattr(mod, 'HINT', None)
    if isinstance(hint, str) and hint.strip():
        return hint.strip()
    doc = (getattr(mod, '__doc__', '') or '').strip()
    if doc:
        for line in doc.splitlines():
            line = line.strip()
            if not line or 'launcher' in line.lower():
                continue
            return line
    return '点击打开'


@dataclass
class ToolInfo:
    """单个工具的调度信息（调度器内部维护，主程序不接触）。"""
    name: str                # 工具名（TAB 类 TITLE）
    title: str               # 工具标题（TITLE 值）
    tab_cls: type            # 原生工具 TAB 类
    fpath: str = ''          # 插件文件绝对路径
    hint: str = ''


class ToolDispatcher:
    """统一工具窗口调度器。"""

    def __init__(self, plugins_root):
        self.plugins_root = plugins_root
        self._tools = {}       # name -> ToolInfo
        self._windows = {}     # name -> QDialog
        self._failures = []

    # ------------------------------------------------------------------
    # 发现与注册
    # ------------------------------------------------------------------
    def get_tool_info(self, name: str):
        """按工具名获取调度信息，未注册返回 None。"""
        return self._tools.get(name)

    def tool_names(self):
        """返回全部已注册工具名。"""
        return list(self._tools.keys())

    def discover(self):
        """扫描插件目录，注册工具并返回供主程序使用的完整结构。

        返回：
            main_groups: [(group_name, [ToolInfo, ...]), ...]
            failures: list[str]

        ``main_groups`` 中每个分组第二个元素为完整的 :class:`ToolInfo` 列表，
        主程序既可通过索引获取 ToolInfo（含 hint 等信息），
        也可调用 :meth:`get_tool_info` 按名查询。
        """
        cleanup_legacy_plugins()
        groups, self._failures = self._discover_raw()
        self.groups = groups
        main_groups = []
        for group_name, items in groups:
            for info in items:
                self._tools[info.name] = info
            main_groups.append((group_name, items))
        return main_groups, self._failures

    def _discover_raw(self):
        """内部发现，返回 [(group_name, [ToolInfo, ...]), ...]。"""
        groups = []
        if not os.path.isdir(self.plugins_root):
            return groups, []

        def sort_key(name):
            m = _PREFIX.match(name)
            return (0, int(m.group(1)), name) if m else (1, 0, name)

        for dname in sorted(os.listdir(self.plugins_root), key=sort_key):
            dpath = os.path.join(self.plugins_root, dname)
            if not os.path.isdir(dpath) or dname.startswith(('_', '.')):
                continue
            group_items = []
            for fname in sorted(os.listdir(dpath), key=sort_key):
                if not fname.endswith('.py') or fname.startswith('_'):
                    continue
                fpath = os.path.join(dpath, fname)
                try:
                    group_items.append(self._load_tool(fpath, fname))
                except Exception:
                    self._failures.append(
                        f'{dname}/{fname}: {traceback.format_exc(limit=0).strip()}')
            if group_items:
                groups.append((_strip_prefix(dname), group_items))
        return groups, self._failures

    def _load_tool(self, fpath, fname):
        """按文件路径装载插件，返回 ToolInfo；缺入口抛异常。"""
        # 模块名用路径摘要（稳定，不受 PYTHONHASHSEED 影响）
        digest = hashlib.md5(fpath.encode('utf-8', 'replace')).hexdigest()[:10]
        modname = f'_windkit_plugin_{digest}'
        spec = spec_from_file_location(modname, fpath)
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)

        tab_cls = getattr(mod, 'TAB', None)
        if isinstance(tab_cls, type) and issubclass(tab_cls, ModuleTab):
            name = getattr(tab_cls, 'TITLE', _strip_prefix(fname[:-3]))
            return ToolInfo(name=name, title=getattr(tab_cls, 'TITLE', name),
                            tab_cls=tab_cls, fpath=fpath,
                            hint=_extract_desc(mod))

        raise RuntimeError(f'插件缺少 TAB 入口: {fname}')

    # ------------------------------------------------------------------
    # 窗口调度
    # ------------------------------------------------------------------
    def open_tool(self, name):
        """打开指定工具，返回嵌入部件。

        同一工具重复点击时复用既有部件，避免每次都新建导致
        旧句柄被覆盖成为孤儿（内存泄漏 + 重复弹窗）。
        """
        if name not in self._tools:
            raise KeyError(f'工具不存在: {name}')
        win = self._windows.get(name)
        if win is None:
            win = self._make_window(self._tools[name])
            self._windows[name] = win
        win.show()
        return win

    def close_tool(self, name):
        """关闭并清理指定工具窗口。"""
        win = self._windows.get(name)
        if win is not None:
            del self._windows[name]
            win.close()

    def close_all(self):
        """关闭全部已打开的工具窗口。"""
        for name in list(self._windows.keys()):
            self.close_tool(name)

    def _make_window(self, info):
        """构造原生工具弹窗：动态实例化 TAB，包装为 QDialog 弹出。"""
        tab_cls = info.tab_cls
        if not (isinstance(tab_cls, type) and issubclass(tab_cls, ModuleTab)):
            raise RuntimeError(f'缺少 TAB 入口，无法弹出原生工具: {info.name}')
        tab_inst = tab_cls()

        dlg = QDialog()
        dlg.setWindowTitle(info.title)
        dlg.resize(960, 680)
        if os.path.exists(ICON):
            dlg.setWindowIcon(QIcon(ICON.replace('\\', '/')))
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(tab_inst)
        dlg.tool_title = info.title
        return dlg

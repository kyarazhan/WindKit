"""卡片/分类覆盖层持久化（图标 + 名称 + 简介 + 排序）。

集中存储于 ``<AppConfigLocation>/WindKit/card_overrides.json``，图标的本地
缓存在同级 ``card_icons/`` 目录（拷贝副本防源图被删后失效）。

支持的覆盖字段：

一级分类（group）:
- name  : 自定义显示名
- icon  : 自定义图标绝对路径（默认不显示，按需求；上传后才显示）
- order : 自定义排序（数字越小越靠前）

二级工具（tool）:
- name  : 自定义显示名
- desc  : 自定义简介
- icon  : 自定义图标（默认显示单字符哈希色块）
- order : 自定义排序

未设 / 留空表示回退到 discover 默认值。

集中化覆盖层数据模型::

    {
      "group|快速计算": {"name": "快速极速", "order": 5},
      "快速计算||风速折算": {"name": "折算器", "desc": "新版", "order": 0}
    }

key 命名空间隔离：``group|<x>`` 与 ``<x>||<tool>`` 互不冲突。
"""

import json
import os
import shutil

from PySide6.QtCore import QStandardPaths

_BASE = (QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
         or os.path.expanduser('~'))
_DIR = os.path.join(_BASE, 'WindKit')
_FILE = os.path.join(_DIR, 'card_overrides.json')
ICON_CACHE_DIR = os.path.join(_DIR, 'card_icons')

_GROUP_PREFIX = 'group|'
_SEP = '||'


def _load() -> dict:
    if not os.path.exists(_FILE):
        return {}
    try:
        with open(_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(d: dict) -> None:
    os.makedirs(_DIR, exist_ok=True)
    tmp = _FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    shutil.move(tmp, _FILE)


def _entry(d: dict, key: str) -> dict:
    e = d.get(key)
    if not isinstance(e, dict):
        return {}
    return e


def _alive(path: str) -> str:
    """icon 路径存在性检查：文件被删视为空（避免运行时找不到图）。"""
    return path if (path and os.path.exists(path)) else ''


# ====================================================================
# 一级分类（group）
# ====================================================================
def get_group_overrides(group: str) -> dict:
    """返回 ``{name, icon, order}`` 三字段；未覆盖字段为空 / None。"""
    d = _load()
    e = _entry(d, _GROUP_PREFIX + group)
    return {
        'name': e.get('name') or '',
        'icon': _alive(e.get('icon') or ''),
        'order': e.get('order'),
    }


def set_group_name(group: str, name: str) -> None:
    d = _load()
    k = _GROUP_PREFIX + group
    d.setdefault(k, {})
    d[k]['name'] = name
    _save(d)


def set_group_icon(group: str, abs_path: str) -> None:
    d = _load()
    k = _GROUP_PREFIX + group
    d.setdefault(k, {})
    d[k]['icon'] = abs_path
    _save(d)


def set_group_order(group: str, order) -> None:
    d = _load()
    k = _GROUP_PREFIX + group
    d.setdefault(k, {})
    d[k]['order'] = int(order) if order is not None and str(order).strip() != '' else None
    _save(d)


def clear_group(group: str) -> None:
    d = _load()
    d.pop(_GROUP_PREFIX + group, None)
    _save(d)


# ====================================================================
# 二级工具（tool）
# ====================================================================
def get_tool_overrides(group: str, tool: str) -> dict:
    """返回 ``{name, desc, icon, order}`` 四字段。"""
    d = _load()
    e = _entry(d, group + _SEP + tool)
    return {
        'name': e.get('name') or '',
        'desc': e.get('desc') or '',
        'icon': _alive(e.get('icon') or ''),
        'order': e.get('order'),
    }


def set_tool_name(group: str, tool: str, name: str) -> None:
    d = _load()
    k = group + _SEP + tool
    d.setdefault(k, {})
    d[k]['name'] = name
    _save(d)


def set_tool_desc(group: str, tool: str, text: str) -> None:
    d = _load()
    k = group + _SEP + tool
    d.setdefault(k, {})
    d[k]['desc'] = text
    _save(d)


def set_tool_icon(group: str, tool: str, abs_path: str) -> None:
    d = _load()
    k = group + _SEP + tool
    d.setdefault(k, {})
    d[k]['icon'] = abs_path
    _save(d)


def set_tool_order(group: str, tool: str, order) -> None:
    d = _load()
    k = group + _SEP + tool
    d.setdefault(k, {})
    d[k]['order'] = int(order) if order is not None and str(order).strip() != '' else None
    _save(d)


def clear_tool(group: str, tool: str) -> None:
    d = _load()
    d.pop(group + _SEP + tool, None)
    _save(d)


# 首次 import 时确保目录存在
os.makedirs(ICON_CACHE_DIR, exist_ok=True)

"""工具参数持久化：自动保存/恢复每个工具的输入参数。

存储位置：AppConfigLocation/WindKit/tool_params.json
（与 ui.card_overrides 同一配置根，两套数据只按文件名区分）
结构：{ "工具名": { "参数key": "值", ... }, ... }
"""

import json
import os

from PySide6.QtCore import QStandardPaths

_APP_DIR = os.path.join(
    QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
    or os.path.expanduser('~'),
    'WindKit')
_PARAMS_FILE = os.path.join(_APP_DIR, 'tool_params.json')


def _ensure_dir():
    os.makedirs(_APP_DIR, exist_ok=True)


def load_params(tool_name: str) -> dict:
    """读取指定工具的已保存参数，不存在返回空字典。"""
    all_params = _load_all()
    return all_params.get(tool_name, {})


def save_params(tool_name: str, params: dict):
    """保存指定工具的参数。"""
    _ensure_dir()
    all_params = _load_all()
    all_params[tool_name] = params
    try:
        with open(_PARAMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_params, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _load_all() -> dict:
    if not os.path.exists(_PARAMS_FILE):
        return {}
    try:
        with open(_PARAMS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

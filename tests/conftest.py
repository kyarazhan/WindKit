"""pytest 全局配置。

当前职责：
- 项目根入 sys.path（拍平后 core/ui 为顶层模块，任意 cwd 可跑 pytest）；
- ``_isolated_card_overrides`` autouse fixture：每个测试用例都把
  :mod:`ui.card_overrides` 的持久化文件与图片缓存目录重定向到
  pytest 提供的 ``tmp_path``，避免测试对真实 AppConfigLocation 写入污染
  开发机的真实覆盖数据。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_card_overrides(tmp_path, monkeypatch):
    from ui import card_overrides
    fake_file = str(tmp_path / 'card_overrides.json')
    fake_cache = str(tmp_path / 'card_icons')
    os.makedirs(fake_cache, exist_ok=True)
    monkeypatch.setattr(card_overrides, '_FILE', fake_file)
    monkeypatch.setattr(card_overrides, 'ICON_CACHE_DIR', fake_cache)
    # 注意：模块 import 时已执行 os.makedirs(ICON_CACHE_DIR)。
    # 此处 monkeypatch 后 ICON_CACHE_DIR 指向 tmp，确保读写都隔离。
    yield

"""机型库：机组扫风面积/单位千瓦扫风数据的 JSON 持久化与增删改查。"""

import hashlib
import json
import os
import shutil
from typing import Dict, List

from core.paths import resource_path, user_data_dir
from core.wind_power import sweep_area, specific_sweep

# 用户机型库：可写、更新不覆盖；首次运行时用随包只读种子库初始化
DEFAULT_DB = os.path.join(user_data_dir(), 'turbines.json')
_BUNDLED_DB = resource_path('data', 'turbines.json')

# v1.0.2 机型库精简迁移：老安装的随包种子与用户副本都按旧 54 机型生成
# （旧更新器不会刷新随包种子），凡内容与旧种子完全一致——即用户从未改过
# 机型库——直接替换为下方两台金风机型；改过的库一律不动。
_OLD_SEED_SHA256 = ('9386f464ce0daa26c5f6a44ef057e5f36aa1a0189b96f039'
                    'd7b85949a17375ef')
_V102_SEED = [
    {'vendor': '金风', 'model': 'GWH221-6250', 'd': 221, 'p': 6250,
     's': 38359.63104415, 'sp': 6.137540967064001},
    {'vendor': '金风', 'model': 'GWH221-6700', 'd': 221, 'p': 6700,
     's': 38359.63104415, 'sp': 5.725318066291045},
]


def migrate_seed_if_unmodified(path: str) -> bool:
    """机型库内容与旧种子逐字节一致时替换为 v1.0.2 精简库；返回是否替换。"""
    try:
        with open(path, 'rb') as f:
            if hashlib.sha256(f.read()).hexdigest() != _OLD_SEED_SHA256:
                return False
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(_V102_SEED, f, ensure_ascii=False, indent=1)
        return True
    except OSError:
        return False


def ensure_seed_migrated() -> None:
    """启动调用：v1.0.2 机型库精简迁移（幂等）。

    - 用户库存在且与旧种子一致 → 原地替换为两机型；
    - 用户库缺失且随包种子仍是旧 54 机型（老更新器不刷新 _internal）→
      直接落两机型，避免首次打开机型库时按旧种子生成。"""
    if not os.path.exists(DEFAULT_DB):
        try:
            if os.path.exists(_BUNDLED_DB):
                with open(_BUNDLED_DB, 'rb') as f:
                    if (hashlib.sha256(f.read()).hexdigest()
                            == _OLD_SEED_SHA256):
                        os.makedirs(os.path.dirname(DEFAULT_DB),
                                    exist_ok=True)
                        with open(DEFAULT_DB, 'w', encoding='utf-8') as f:
                            json.dump(_V102_SEED, f, ensure_ascii=False,
                                      indent=1)
        except OSError:
            pass
        return
    migrate_seed_if_unmodified(DEFAULT_DB)


class TurbineDB:
    def __init__(self, path: str = None):
        self.path = path or os.path.abspath(DEFAULT_DB)
        if not os.path.exists(self.path) and os.path.exists(_BUNDLED_DB):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            shutil.copy(_BUNDLED_DB, self.path)
        if self.path == os.path.abspath(DEFAULT_DB):
            migrate_seed_if_unmodified(self.path)
        self.turbines: List[Dict] = []
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, 'r', encoding='utf-8') as f:
                self.turbines = json.load(f)
        else:
            self.turbines = []

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.turbines, f, ensure_ascii=False, indent=1)

    def add(self, vendor: str, model: str, d: float, p: float):
        s = sweep_area(d)
        self.turbines.append({'vendor': vendor, 'model': model, 'd': d, 'p': p,
                              's': round(s, 4), 'sp': round(s / p, 4)})

    def remove(self, index: int):
        del self.turbines[index]

    def update(self, index: int, vendor: str, model: str, d: float, p: float):
        s = sweep_area(d)
        self.turbines[index] = {'vendor': vendor, 'model': model, 'd': d, 'p': p,
                                's': round(s, 4), 'sp': round(s / p, 4)}

    def vendors(self) -> List[str]:
        seen = []
        for t in self.turbines:
            if t['vendor'] not in seen:
                seen.append(t['vendor'])
        return seen

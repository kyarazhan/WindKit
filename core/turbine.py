"""机型库：机组扫风面积/单位千瓦扫风数据的 JSON 持久化与增删改查。"""

import json
import os
import shutil
from typing import Dict, List

from core.paths import resource_path, user_data_dir
from core.wind_power import sweep_area, specific_sweep

# 用户机型库：可写、更新不覆盖；首次运行时用随包只读种子库初始化
DEFAULT_DB = os.path.join(user_data_dir(), 'turbines.json')
_BUNDLED_DB = resource_path('data', 'turbines.json')


class TurbineDB:
    def __init__(self, path: str = None):
        self.path = path or os.path.abspath(DEFAULT_DB)
        if not os.path.exists(self.path) and os.path.exists(_BUNDLED_DB):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            shutil.copy(_BUNDLED_DB, self.path)
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

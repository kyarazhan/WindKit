"""长期订正 - 对齐源文件「长期订正」表逻辑。

源表核心：B/C 列 30 年年风速序列；Y12=AVERAGE(C2:C31)（30 年均值）；
Y13=AVERAGE(C12:C31)（后 20 年）；Y14=AVERAGE(C17:C31)（后 15 年）；
Y15=AVERAGE(C22:C31)（后 10 年）；P6=AVERAGE(C12:C31) 等。
差异幅度 = V塔/V长期 - 1；订正后 = V前 * (1 - 差异幅度)。
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class LongTermCorrection:
    years: List[int] = field(default_factory=list)
    values: List[float] = field(default_factory=list)
    tower_wind: float = 0.0        # 测风塔测量期平均风速 V塔
    tower_period: float = 0.0      # 测风塔测量期年数（默认与序列尾部对齐）

    def window_mean(self, last_n: int) -> float:
        """最近 last_n 年均值。"""
        if last_n >= len(self.values):
            return sum(self.values) / len(self.values)
        return sum(self.values[-last_n:]) / last_n

    @property
    def mean_30y(self) -> float:
        return self.window_mean(30)

    @property
    def mean_20y(self) -> float:
        return self.window_mean(20)

    @property
    def mean_15y(self) -> float:
        return self.window_mean(15)

    @property
    def mean_10y(self) -> float:
        return self.window_mean(10)

    @property
    def mean_5y(self) -> float:
        return self.window_mean(5)

    def deviation(self, window: int) -> float:
        """差异幅度 = V塔 / V_long(window) - 1。"""
        long_mean = self.window_mean(window)
        return self.tower_wind / long_mean - 1.0 if long_mean > 0 else 0.0

    def corrected(self, window: int) -> float:
        """订正后风速 = V塔 * (1 - 差异幅度) = V塔^2/V_long... 源表：V前*(1-差异幅度)。"""
        return self.tower_wind * (1.0 - self.deviation(window))

    def summary(self) -> Dict[str, float]:
        return {
            '30年平均': self.mean_30y,
            '20年平均': self.mean_20y,
            '15年平均': self.mean_15y,
            '10年平均': self.mean_10y,
            '5年平均': self.mean_5y,
        }

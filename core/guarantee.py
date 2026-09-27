"""保发电量敏感度 - 对齐源文件「保发表格」。

源表真实逻辑（锚点行 22：Vref1=6.59，2655h）：
G2 = B21/B22-1 = 6.49/6.59-1 = -0.01517
J2 = G2*I2*C22 = -0.01517 * 2.3 * 2655 = -92.66h  （常量！I2=2.3 直接做乘数）
G3 = B23/B22-1 = 6.69/6.59-1 = +0.01517
J3 = I3*G3*C22 = 1.0 * 0.01517 * 2655 = +40.29h   （常量）
C 列链式：C21=C22+J2，C20=C21+J2 ... C23=C22+J3，C24=C23+J3 ...
即：步长只在锚点处计算一次，随后线性累加（-92.66/0.1m/s，+40.29/0.1m/s）。
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class GuaranteeTable:
    vref: float = 6.59          # 全场机位点年平均风速锚点 m/s
    hours_ref: float = 2655.0   # 等效满负荷利用小时锚点
    down_factor: float = 2.3    # I2：下降步长乘数（源表直接乘 2.3）
    up_factor: float = 1.0      # I3：上升步长乘数

    def step_down(self) -> float:
        """风速每 -0.1m/s 的小时数步减（负值，常量）。"""
        g = (self.vref - 0.1) / self.vref - 1.0
        return g * self.down_factor * self.hours_ref

    def step_up(self) -> float:
        """风速每 +0.1m/s 的小时数步增（正值，常量）。"""
        g = (self.vref + 0.1) / self.vref - 1.0
        return self.up_factor * g * self.hours_ref

    def sweep(self, span: float = 2.0, step: float = 0.1) -> List[Tuple[float, float]]:
        """扫掠 [-span, +span]，返回 [(风速, 小时数)] 按风速升序。"""
        n_steps = int(round(span / step))
        j_down = self.step_down()
        j_up = self.step_up()
        down = [(self.vref, self.hours_ref)]
        for i in range(1, n_steps + 1):
            v = round(self.vref - i * step, 4)
            down.append((v, round(down[-1][1] + j_down, 1)))
        up = [(self.vref, self.hours_ref)]
        for i in range(1, n_steps + 1):
            v = round(self.vref + i * step, 4)
            up.append((v, round(up[-1][1] + j_up, 1)))
        return list(reversed(down[:-1])) + up

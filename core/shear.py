"""风切变幂律 - 对齐源文件「常用公式」表。

L5 = LOG10(L7/L6)/LOG10(L9/L8)     alpha = ln(V2/V1)/ln(z2/z1)
K7 = K6*(K9/K8)^K5                 V2 = V1*(z2/z1)^alpha
"""

import math


def shear_alpha(v1: float, z1: float, v2: float, z2: float) -> float:
    """由两层高度风速反推幂律指数 alpha。"""
    return math.log10(v2 / v1) / math.log10(z2 / z1)


def extrapolate(v1: float, z1: float, alpha: float, z2: float) -> float:
    """由已知高度风速与 alpha 外推目标高度风速。"""
    return v1 * (z2 / z1) ** alpha

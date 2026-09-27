"""耿贝尔(Gumbel)极值分布 - 对齐源文件「50年一遇最大风速」表。

C1 = AVERAGE(A1:A73)                       均值
C2 = STDEV.P(A1:A73)                       标准差
E2/E3 = 一次插值(N=73 两侧的 C1/C2 参数)   由 I/J/K 参数表线性插值
C3 = E2/C2                                 alpha = C1_param/sigma
C4 = C1-E3/C3                              u = mean - C2_param/alpha
C5 = C4-1/C3*LN(LN(50N/(50N-1)))           V50 = u - (1/alpha)*ln(-ln(F)), F=50N/(50N-1)
C7 = (C5^3*C6/1.225)^(1/3)                 标况换算
C16 = C13*(C15/C14)^C12                    高度外推
"""

import math

# 源 Excel 耿贝尔 C1/C2 参数表（I3:K19，N -> C1, C2）
GUMBEL_TABLE = [
    (10, 0.9497, 0.4952),
    (15, 1.02057, 0.5182),
    (20, 1.06283, 0.52355),
    (25, 1.09145, 0.53086),
    (30, 1.11238, 0.53622),
    (35, 1.12847, 0.54034),
    (40, 1.14132, 0.54362),
    (45, 1.15185, 0.5463),
    (50, 1.16066, 0.54853),
    (60, 1.17465, 0.55208),
    (70, 1.18536, 0.55477),
    (80, 1.19385, 0.55688),
    (90, 1.20649, 0.5586),
    (100, 1.20649, 0.56002),
    (250, 1.24292, 0.56878),
    (500, 1.24292, 0.56878),  # 表末占位，与 250 同值（源表 I18 截断）
]

STD_RHO = 1.225


def interpolate_param(n: int):
    """一次插值法（y=k*x+b）求 C1/C2 参数，n 为样本数。"""
    if n <= GUMBEL_TABLE[0][0]:
        return GUMBEL_TABLE[0][1], GUMBEL_TABLE[0][2]
    for i in range(1, len(GUMBEL_TABLE)):
        n0, c1_0, c2_0 = GUMBEL_TABLE[i - 1]
        n1, c1_1, c2_1 = GUMBEL_TABLE[i]
        if n <= n1:
            t = (n - n0) / (n1 - n0)
            return c1_0 + t * (c1_1 - c1_0), c2_0 + t * (c2_1 - c2_0)
    return GUMBEL_TABLE[-1][1], GUMBEL_TABLE[-1][2]


def mean(xs) -> float:
    return sum(xs) / len(xs)


def stdev_p(xs) -> float:
    """总体标准差 STDEV.P。"""
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def gumbel_v50(samples, rho: float = STD_RHO):
    """耿贝尔法 50 年一遇最大风速。

    返回 (mean, sigma, c1p, c2p, alpha, u, v50, v50_std) 。
    v50_std 为标况换算 V=(V^3*rho/1.225)^(1/3)。
    """
    m = mean(samples)
    sigma = stdev_p(samples)
    n = len(samples)
    c1p, c2p = interpolate_param(n)
    alpha = c1p / sigma
    u = m - c2p / alpha
    # 源表 C5 = C4-1/C3*LN(LN(50N/(50N-1)))；F 比=1.000274，ln 后为正小数，
    # 再 ln 得负数，减去负数即加上极值距离
    ratio = 50.0 * n / (50.0 * n - 1.0)
    v50 = u - (1.0 / alpha) * math.log(math.log(ratio))
    v50_std = (v50 ** 3 * rho / STD_RHO) ** (1.0 / 3.0)
    return m, sigma, c1p, c2p, alpha, u, v50, v50_std


def extrapolate_height(v: float, z1: float, z2: float, shear: float) -> float:
    """C16 = C13*(C15/C14)^C12 高度外推。"""
    return v * (z2 / z1) ** shear

"""Weibull 分布 - 对齐源文件「发电量速算」表。

B2 = A2/(EXP(GAMMALN(1+1/C2)))                       A = Vave/Gamma(1+1/k)
B4 = WEIBULL.DIST(A4,C2,B2,TRUE)                     累积分布 F(V)
C4 = WEIBULL.DIST(A4,C2,B2,FALSE)                    概率密度 f(V)
D5 = (B5-B4)*8760                                    区间小时数 N(h)
E5 = D5*(H4+H5)/2                                    梯形积分电量（调整曲线）
"""

import math

HOURS_PER_YEAR = 8760.0


def gamma_fn(x: float) -> float:
    return math.gamma(x)


def weibull_a_from_vave(vave: float, k: float) -> float:
    """由平均风速与形状参数 k 反推尺度参数 A。"""
    return vave / math.exp(math.log(gamma_fn(1.0 + 1.0 / k)))


def weibull_cdf(v: float, k: float, a: float) -> float:
    """Weibull 累积分布 F(V) = 1-exp(-(V/A)^k)。"""
    if v <= 0:
        return 0.0
    return 1.0 - math.exp(-((v / a) ** k))


def weibull_pdf(v: float, k: float, a: float) -> float:
    """Weibull 概率密度 f(V)。"""
    if v <= 0:
        return 0.0
    return (k / a) * ((v / a) ** (k - 1.0)) * math.exp(-((v / a) ** k))


def bin_hours(v_lo: float, v_hi: float, k: float, a: float) -> float:
    """区间 [v_lo, v_hi) 年小时数 = (F(hi)-F(lo))*8760。"""
    return (weibull_cdf(v_hi, k, a) - weibull_cdf(v_lo, k, a)) * HOURS_PER_YEAR


def annual_energy(speeds, powers, k: float, a: float, wake: float = 0.0,
                  other: float = 1.0):
    """梯形积分年电量。

    speeds/powers: 风速与对应功率序列（等距 bin 中心或边界均可，逐区间梯形）。
    wake: 尾流折减比例（源表 D2=5%）；other: 综合系数（源表 G2=80% 上网电量）。
    返回 (毛电量, 尾流后电量, 上网电量) kWh。
    """
    gross = 0.0
    for i in range(1, len(speeds)):
        dh = (weibull_cdf(speeds[i], k, a) - weibull_cdf(speeds[i - 1], k, a)) * HOURS_PER_YEAR
        gross += dh * (powers[i - 1] + powers[i]) / 2.0
    after_wake = gross * (1.0 - wake)
    net = after_wake * other
    return gross, after_wake, net

"""core 公式回归测试 - 锚点全部取自源 Excel 缓存值。"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.air_density import air_density, convert_wind_energy, convert_wind_pressure
from core.shear import shear_alpha, extrapolate
from core.wind_power import sweep_area, theoretical_power, power_coefficient
from core.distributions import weibull_a_from_vave, weibull_cdf, weibull_pdf, bin_hours, annual_energy
from core.extreme_wind import gumbel_v50, interpolate_param, stdev_p
from core.long_term import LongTermCorrection
from core.guarantee import GuaranteeTable
from core.m1_split import m1_split

SRC = os.path.join(os.path.dirname(__file__), '..', 'data', 'samples')


def approx(a, b, tol=1e-6):
    assert abs(a - b) < tol, f'{a} != {b}'


def test_air_density():
    # B5=86.5 hPa? 实测源表 B5=86.5 => B7=1.0890 验证
    approx(air_density(86.5, 3.6), 1.0890468951147119, 1e-9)


def test_convert():
    # D7=6, E7=1.098, F7=1.225 => G7=5.785
    approx(convert_wind_energy(6, 1.098, 1.225), 5.785044014063174, 1e-9)
    approx(convert_wind_pressure(6, 1.098, 1.225), 5.6804713802677345, 1e-9)


def test_shear():
    # 源表: L5=LOG10(6.616/6.34)/LOG10(140/120)=0.2764
    approx(shear_alpha(6.34, 120, 6.616, 140), 0.2764320554408639, 1e-9)
    # K7=K6*(K9/K8)^K5: K5=0.276,K6=6.34,K8=120,K9=140 => 6.6156
    approx(extrapolate(6.34, 120, 0.276, 140), 6.615559378223438, 1e-6)


def test_sweep():
    # D=150 => E=17671.458
    approx(sweep_area(150), 17671.458375000002, 1e-6)


def test_power_curve():
    # rho=1.225, D=190, V=2.5 => E9=271.346 kW
    approx(theoretical_power(2.5, 1.225, 190), 271.3458569404297, 1e-6)
    # C9=35.91, E9=271.346 => Cp=0.13234
    approx(power_coefficient(35.91, 2.5, 1.225, 190), 0.13234032907266224, 1e-9)
    # H9 = C9*(G9+1) = 35.91*(0.01+1) = 36.269
    approx(35.91 * (0.01 + 1), 36.269099999999995, 1e-9)


def test_weibull():
    # Vave=5.124, k=1.92 => A=5.776256
    approx(weibull_a_from_vave(5.124, 1.92), 5.776256375238562, 1e-9)
    # F(0.5)=0.0090716, f(0.5)=0.0346765
    a = 5.776256375238562
    approx(weibull_cdf(0.5, 1.92, a), 0.009071598994711962, 1e-12)
    approx(weibull_pdf(0.5, 1.92, a), 0.034676455872823496, 1e-12)
    # D5 = (F(0.5)-F(0))*8760 = 79.467
    approx(bin_hours(0, 0.5, 1.92, a), 79.46720719367678, 1e-9)


def test_gumbel():
    amax = json.load(open(os.path.join(SRC, 'gumbel_sample.json')))
    assert len(amax) == 73
    m, sigma, c1p, c2p, alpha, u, v50, v50_std = gumbel_v50(amax, rho=1.212)
    approx(m, 11.705479452054792, 1e-9)
    approx(sigma, 2.1514499991616933, 1e-9)
    # 源表 E2=1.187907（插值 C1 参数），E3=0.555403（C2 参数）
    approx(c1p, 1.187907, 1e-5)
    approx(c2p, 0.555403, 1e-5)
    # C3=0.55214, C4=10.69957, C5=25.55506, C7=25.46434
    approx(alpha, 0.5521425087558869, 1e-6)
    approx(u, 10.699574289542564, 1e-6)
    approx(v50, 25.55506053550615, 1e-5)
    approx(v50_std, 25.464340004896613, 1e-5)


def test_gumbel_interp():
    # N=73 落在 70/80 之间
    c1, c2 = interpolate_param(73)
    assert 1.18536 < c1 < 1.19385


def test_long_term():
    series = json.load(open(os.path.join(SRC, 'ltc_series.json')))
    ltc = LongTermCorrection(years=[int(y) for y in series], values=list(series.values()),
                             tower_wind=4.747966666666667)
    approx(ltc.mean_30y, 4.747966666666667, 1e-9)
    approx(ltc.mean_20y, 4.7609, 1e-9)
    approx(ltc.mean_15y, 4.768066666666667, 1e-9)
    approx(ltc.mean_10y, 4.7802999999999995, 1e-9)
    approx(ltc.mean_5y, 4.8078, 1e-9)


def test_guarantee():
    gt = GuaranteeTable()
    rows = gt.sweep(span=2.0)
    assert len(rows) == 41
    # 锚点 6.59 在索引 19/20 重复一次（下降链尾 + 上升链头）
    assert rows[19] == (6.59, 2655.0) and rows[20] == (6.59, 2655.0)
    # +0.1 行: 2655 + 40.288 = 2695.3（源表 C23）
    v, h = rows[21]
    approx(v, 6.69, 1e-6)
    assert abs(h - 2695.288315629742) <= 0.1
    # -0.1 行: 2655 - 92.663 = 2562.3（源表 C21）
    v, h = rows[18]
    approx(v, 6.49, 1e-6)
    assert abs(h - 2562.3368740515934) <= 0.1
    # -0.2 行（源表 C20=2469.674）
    approx(rows[17][1], 2469.673748103187, 0.1)
    # +2.0 端点：2655 + 20*40.288 = 3460.77（每步 round(0.1) 累积误差 <1h）
    approx(rows[40][1], 2655 + 20 * 40.28831562974199, 1.0)


def test_m1():
    bins = [(1.5, 0.37), (2.5, 0.36989473684210533)]
    outputs, optimized, speeds = m1_split(bins)
    assert outputs[0] == 0.37
    approx(outputs[1], 0.3699473684210527, 1e-12)
    assert optimized[0] == 0.37
    # floor 测试
    _, opt2, _ = m1_split([(1.5, 0.05)])
    assert opt2[0] == 0.1

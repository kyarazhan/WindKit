"""空气密度与风速折算 - 对齐源文件「常用公式」表。

B7 = B5*1000/(287*(273.15+B6))          空气密度 kg/m3
G7 = (D7^3*E7/F7)^(1/3)                 风能(功率)等效折算: V2 = (V1^3 * rho1/rho2)^(1/3)
H7 = (D7^2*E7/F7)^(1/2)                 风压等效折算:     V2 = (V1^2 * rho1/rho2)^(1/2)
K7 = K6*(K9/K8)^K5                      风切变外推:       V2 = V1*(z2/z1)^alpha
"""

R_DRY_AIR = 287.0
KELVIN = 273.15


def air_density(pressure_hpa: float, temp_c: float) -> float:
    """理想气体状态方程，p 单位 hPa，T 单位摄氏度。"""
    return pressure_hpa * 1000.0 / (R_DRY_AIR * (KELVIN + temp_c))


def convert_wind_energy(v1: float, rho1: float, rho2: float) -> float:
    """风能等效：保持功率密度不变 V2=(V1^3*rho1/rho2)^(1/3)。"""
    return (v1 ** 3 * rho1 / rho2) ** (1.0 / 3.0)


def convert_wind_pressure(v1: float, rho1: float, rho2: float) -> float:
    """风压等效：保持动压不变 V2=(V1^2*rho1/rho2)^(1/2)。"""
    return (v1 ** 2 * rho1 / rho2) ** 0.5

"""M1拆分核心算法：输入→输出插值，输出→优化Ti钳位。"""


def m1_split(bins, floor=0.1):
    """
    1m bin → 0.5m bin 重采样（兼容旧接口）。

    Args:
        bins: [(speed, value), ...] 输入风速-值对
        floor: 优化列下限阈值

    Returns:
        (outputs, optimized, speeds) 输出值、优化值、风速列表
    """
    if not bins:
        return [], [], []

    speeds_in = [b[0] for b in bins]
    values_in = [b[1] for b in bins]

    # 插值到0.5步长
    speeds_out, values_out = expand_wind_speed(speeds_in, values_in, 0.5)

    # 优化：钳位到floor
    optimized = [max(v, floor) for v in values_out]

    return values_out, optimized, speeds_out


def expand_wind_speed(input_speeds, input_ti, step=0.5):
    """
    将输入风速-Ti序列插值到更细的步长。

    Args:
        input_speeds: 输入风速列表 (如 [1.5, 2.5, ..., 24.5])
        input_ti: 输入Ti列表
        step: 目标步长 (默认0.5)

    Returns:
        (output_speeds, output_ti) 插值后的风速和Ti列表
    """
    if not input_speeds or not input_ti:
        return [], []

    # 确保输入数据对齐
    n = min(len(input_speeds), len(input_ti))
    input_speeds = input_speeds[:n]
    input_ti = input_ti[:n]

    # 生成目标风速序列
    min_speed = min(input_speeds)
    max_speed = max(input_speeds)
    output_speeds = []
    v = min_speed
    while v <= max_speed + 1e-9:
        output_speeds.append(round(v, 1))
        v += step

    # 线性插值Ti
    output_ti = []
    for v in output_speeds:
        # 找到插值区间
        if v <= input_speeds[0]:
            output_ti.append(input_ti[0])
        elif v >= input_speeds[-1]:
            output_ti.append(input_ti[-1])
        else:
            # 二分查找区间
            for i in range(len(input_speeds) - 1):
                if input_speeds[i] <= v <= input_speeds[i + 1]:
                    # 线性插值
                    t = (v - input_speeds[i]) / (input_speeds[i + 1] - input_speeds[i])
                    ti = input_ti[i] + t * (input_ti[i + 1] - input_ti[i])
                    output_ti.append(ti)
                    break

    return output_speeds, output_ti


def clamp_ti(output_speeds, output_ti, threshold=0.1, consecutive=3):
    """
    优化模块：如果Ti出现连续consecutive个小于threshold的值，
    从第一个开始全部钳位为threshold。

    Args:
        output_speeds: 风速列表
        output_ti: Ti列表
        threshold: 阈值 (默认0.1)
        consecutive: 连续个数 (默认3)

    Returns:
        钳位后的Ti列表
    """
    if not output_ti:
        return []

    result = list(output_ti)
    n = len(result)

    # 从后往前扫描，找到第一个连续<threshold的序列起点
    i = n - 1
    while i >= 0:
        if result[i] < threshold:
            # 向前计数连续<threshold的个数
            count = 1
            j = i - 1
            while j >= 0 and result[j] < threshold:
                count += 1
                j -= 1

            # 如果连续个数>=consecutive，从j+1开始全部钳位
            if count >= consecutive:
                for k in range(j + 1, n):
                    if result[k] < threshold:
                        result[k] = threshold
                break
            else:
                i = j
        else:
            i -= 1

    return result

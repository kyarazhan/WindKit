"""界址点坐标 ⇄ 正八边形中心：核心算法（纯 Python，无 GUI 依赖）。

正向：多边形界址点 → 质心（shoelace 公式）
反向：正八边形中心 + 对边距 S → 8 个界址点

Excel I/O 使用 openpyxl。
"""

from __future__ import annotations

import math

from openpyxl import Workbook, load_workbook

SQRT2 = math.sqrt(2.0)


# ---------------------------------------------------------------------------
# 正向：多边形 → 质心
# ---------------------------------------------------------------------------

def polygon_centroid(pts):
    """多边形质心（凸/凹通用），shoelace 公式。返回 (cx, cy, area, perimeter)。"""
    n = len(pts)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0
    if n == 1:
        return pts[0][0], pts[0][1], 0.0, 0.0
    if n == 2:
        cx = (pts[0][0] + pts[1][0]) / 2
        cy = (pts[0][1] + pts[1][1]) / 2
        perim = 2.0 * math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
        return cx, cy, 0.0, perim

    a2 = cx_acc = cy_acc = 0.0
    perim = 0.0
    ref_x, ref_y = pts[0][0], pts[0][1]
    for i in range(n):
        x0, y0 = pts[i][0] - ref_x, pts[i][1] - ref_y
        x1, y1 = pts[(i + 1) % n][0] - ref_x, pts[(i + 1) % n][1] - ref_y
        cross = x0 * y1 - x1 * y0
        a2 += cross
        cx_acc += (x0 + x1) * cross
        cy_acc += (y0 + y1) * cross
        perim += math.hypot(x1 - x0, y1 - y0)

    if abs(a2) < 1e-12:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return sum(xs) / n, sum(ys) / n, 0.0, perim

    area = abs(a2) / 2.0
    cx = cx_acc / (3.0 * a2) + ref_x
    cy = cy_acc / (3.0 * a2) + ref_y
    return cx, cy, area, perim


def parse_excel(path):
    """解析正向 Excel，返回 (groups, src_ws)。

    groups = [{name, rows, points, count, is_closed, cx, cy, area, perim}, ...]
    """
    wb = load_workbook(path, data_only=True)
    ws = wb.active

    groups = []
    current = None
    header_passed = False
    header_words = ("地块名称", "地块", "界址点", "编号")

    def _coerce_num(v):
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _looks_like_header_text(v):
        if v is None:
            return False
        s = str(v).strip()
        return any(w in s for w in header_words)

    for row in ws.iter_rows(values_only=True):
        if not row:
            continue

        if not header_passed:
            if any(_looks_like_header_text(c) for c in row):
                header_passed = True
            continue

        raw_name = row[0]
        seq = row[1] if len(row) > 1 else None
        point_id = row[2] if len(row) > 2 else None
        x = _coerce_num(row[3] if len(row) > 3 else None)
        y = _coerce_num(row[4] if len(row) > 4 else None)

        if x is None or y is None:
            continue
        if _looks_like_header_text(raw_name):
            continue

        name = str(raw_name).strip() if raw_name not in (None, "") else (
            current['name'] if current else "UNKNOWN")

        if current is None or current['name'] != name:
            current = {"name": name, "rows": [], "points": []}
            groups.append(current)

        current["rows"].append({
            "name": name, "seq": seq, "point_id": point_id, "x": x, "y": y,
        })
        current["points"].append((x, y, point_id))

    for g in groups:
        pts = g["points"]
        is_closed = False
        if len(pts) > 1:
            x0, y0, _ = pts[0]
            xL, yL, _ = pts[-1]
            if abs(x0 - xL) < 1e-6 and abs(y0 - yL) < 1e-6:
                pts = pts[:-1]
                is_closed = True
        g["points"] = pts
        g["count"] = len(pts)
        g["is_closed"] = is_closed

        if len(pts) >= 3:
            cx, cy, area, perim = polygon_centroid([(p[0], p[1]) for p in pts])
            g["cx"], g["cy"], g["area"], g["perim"] = cx, cy, area, perim
        elif len(pts) == 2:
            cx = (pts[0][0] + pts[1][0]) / 2
            cy = (pts[0][1] + pts[1][1]) / 2
            g["cx"], g["cy"], g["area"], g["perim"] = cx, cy, 0.0, \
                2 * math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
        elif len(pts) == 1:
            g["cx"], g["cy"], g["area"], g["perim"] = pts[0][0], pts[0][1], 0.0, 0.0
        else:
            g["cx"], g["cy"], g["area"], g["perim"] = 0.0, 0.0, 0.0, 0.0

    return groups, ws


def export_excel(groups, src_ws, dst_path):
    """正向导出：'中心点汇总' + '原始数据' 两个 sheet。"""
    wb = Workbook()

    ws_summary = wb.active
    ws_summary.title = "中心点汇总"
    ws_summary.append(["地块名称", "是否闭环", "界址点数",
                       "中心 X (m)", "中心 Y (m)", "面积 (m²)", "周长 (m)"])
    for g in groups:
        ws_summary.append([
            g["name"], "是" if g["is_closed"] else "否", g["count"],
            round(g["cx"], 3), round(g["cy"], 3),
            round(g["area"], 2), round(g["perim"], 2),
        ])

    ws_raw = wb.create_sheet("原始数据")
    if src_ws is not None:
        for row in src_ws.iter_rows(values_only=True):
            ws_raw.append(list(row))

    wb.save(dst_path)


# ---------------------------------------------------------------------------
# 反向：中心 + 对边距 S → 正八边形界址点
# ---------------------------------------------------------------------------

def octagon_params(S):
    """对边距 S → (h, d, a, c)：h=半对边距, d=顶点距中轴, a=平边长, c=切角。"""
    h = S / 2.0
    c = S / (2.0 + SQRT2)
    d = h - c
    a = S - 2.0 * c
    return h, d, a, c


def octagon_vertices(cx, cy, S):
    """正八边形 8 顶点（平边朝上，J1=顶边右端顺时针），返回 [(x, y) × 8]。"""
    h, d, _a, _c = octagon_params(S)
    return [
        (cx + d, cy + h),   # J1 顶边右端
        (cx - d, cy + h),   # J2 顶边左端
        (cx - h, cy + d),   # J3 左上切点
        (cx - h, cy - d),   # J4 左下切点
        (cx - d, cy - h),   # J5 底边左端
        (cx + d, cy - h),   # J6 底边右端
        (cx + h, cy - d),   # J7 右下切点
        (cx + h, cy + d),   # J8 右上切点
    ]


def parse_centers_excel(path, default_S):
    """解析反向中心点 Excel，返回 centers = [{name, cx, cy, S}, ...]"""
    wb = load_workbook(path, data_only=True)
    ws = wb.active

    def _num(v):
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    centers = []
    header_passed = False
    for row in ws.iter_rows(values_only=True):
        if not row:
            continue
        cells = list(row) + [None] * 5

        if not header_passed:
            if any(c is not None and "中心" in str(c) for c in cells):
                header_passed = True
            continue

        raw_name = cells[0]
        x = _num(cells[1])
        y = _num(cells[2])
        s = _num(cells[3])

        if x is None or y is None:
            continue
        if raw_name and ("地块" in str(raw_name) or "名称" in str(raw_name)):
            continue

        name = str(raw_name).strip() if raw_name not in (None, "") else f"P{len(centers) + 1}"
        centers.append({
            "name": name, "cx": x, "cy": y,
            "S": s if (s is not None and s > 0) else default_S,
        })

    return centers


def build_boundary_rows(centers, seq_start=1):
    """centers → 界址点行列表。每组 9 行：J1..J8 + J1 闭合行。"""
    rows = []
    seq = seq_start
    for c in centers:
        pts = octagon_vertices(c["cx"], c["cy"], c["S"])
        for i, (x, y) in enumerate(pts, start=1):
            rows.append({"name": c["name"], "seq": seq, "pid": f"J{i}", "x": x, "y": y})
            seq += 1
        rows.append({"name": c["name"], "seq": seq, "pid": "J1",
                      "x": pts[0][0], "y": pts[0][1]})
        seq += 1
    return rows


def export_boundary_excel(centers, rows, dst_path,
                          title="界址点坐标表", datum="（大地2000坐标系）",
                          merge_names=False):
    """反向导出：与原表同格式。Sheet1 界址点坐标表 + Sheet2 生成参数校验。"""
    wb = Workbook()

    ws = wb.active
    ws.title = "界址点坐标表"
    ws.append([title])
    ws.append([datum])
    ws.append(["地块名称", "序号", "界址点", "x (m)", "y (m)"])
    data_start = 4

    for r in rows:
        ws.append([r["name"], r["seq"], r["pid"], round(r["x"], 3), round(r["y"], 3)])

    if merge_names:
        n = len(rows)
        i = 0
        while i < n:
            j = i
            while j + 1 < n and rows[j + 1]["name"] == rows[i]["name"]:
                j += 1
            if j > i:
                r0, r1 = data_start + i, data_start + j
                for r in range(r0, r1 + 1):
                    ws.cell(row=r, column=1).value = None
                ws.cell(row=r0, column=1).value = rows[i]["name"]
                ws.merge_cells(start_row=r0, start_column=1,
                               end_row=r1, end_column=1)
            i = j + 1

    ws2 = wb.create_sheet("生成参数")
    ws2.append(["地块名称", "中心 X (m)", "中心 Y (m)", "对边距 S (m)",
                "校验质心 X (m)", "校验质心 Y (m)", "校验结果"])
    for c in centers:
        pts = octagon_vertices(c["cx"], c["cy"], c["S"])
        vx, vy, _, _ = polygon_centroid(pts)
        ok = abs(vx - c["cx"]) < 1e-6 and abs(vy - c["cy"]) < 1e-6
        ws2.append([c["name"], c["cx"], c["cy"], c["S"],
                    round(vx, 3), round(vy, 3), "通过" if ok else "偏差"])

    wb.save(dst_path)

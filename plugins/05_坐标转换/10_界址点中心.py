"""界址点坐标 ⇄ 正八边形中心：正向（界址点→中心）与反向（中心→界址点）双向工具。"""

from pathlib import Path

import pandas as pd
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QRadioButton, QSplitter,
                               QTabWidget, QVBoxLayout, QWidget)

from core.boundary_centroid import (
    build_boundary_rows, export_boundary_excel, export_excel,
    parse_centers_excel, parse_excel,
)
from ui.base_tab import ModuleTab
from ui.widgets import DataTable

HINT = '正向：多边形界址点 → 几何中心；反向：正八边形中心 + 对边距 → 8 个界址点'


class BoundaryCentroidTab(ModuleTab):
    TITLE = '界址点 ⇄ 中心'

    def __init__(self):
        super().__init__(hint='正向：多边形界址点 → 几何中心；反向：正八边形中心 + 对边距 → 8 个界址点')

        tabs = QTabWidget()
        tabs.addTab(self._build_forward_tab(), '① 界址点 → 中心')
        tabs.addTab(self._build_reverse_tab(), '② 中心 → 界址点')
        self.root_lay.addWidget(tabs)

    # =================================================================
    # Tab ① 界址点 → 中心
    # =================================================================
    def _build_forward_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)

        bar = QHBoxLayout()
        self._fwd_btn_open = QPushButton('选择 Excel')
        self._fwd_btn_open.setProperty('primaryBtn', True)
        self._fwd_btn_open.clicked.connect(self._fwd_open)
        bar.addWidget(self._fwd_btn_open)

        self._fwd_btn_export = QPushButton('导出新 Excel')
        self._fwd_btn_export.clicked.connect(self._fwd_export)
        bar.addWidget(self._fwd_btn_export)

        self._fwd_btn_reload = QPushButton('重新解析')
        self._fwd_btn_reload.clicked.connect(self._fwd_reload)
        bar.addWidget(self._fwd_btn_reload)

        self._fwd_path_lbl = QLabel('未选择文件')
        self._fwd_path_lbl.setStyleSheet('color:#555;')
        bar.addWidget(self._fwd_path_lbl)

        self._fwd_summary = QLabel('')
        self._fwd_summary.setStyleSheet('color:#0a6; font-weight:bold;')
        bar.addStretch(1)
        bar.addWidget(self._fwd_summary)

        lay.addLayout(bar)

        splitter = QSplitter()
        self._fwd_tbl_raw = DataTable()
        self._fwd_tbl_res = DataTable()

        left = QFrame()
        left.setFrameShape(QFrame.StyledPanel)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)
        ll.addWidget(QLabel('原始数据预览'))
        ll.addWidget(self._fwd_tbl_raw)

        right = QFrame()
        right.setFrameShape(QFrame.StyledPanel)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 4, 4, 4)
        rl.addWidget(QLabel('中心点计算结果（多边形质心）'))
        rl.addWidget(self._fwd_tbl_res)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        lay.addWidget(splitter, 1)

        self._fwd_status = QLabel('就绪。请点击「选择 Excel」加载界址点坐标表。')
        self._fwd_status.setStyleSheet('color:#444;')
        lay.addWidget(self._fwd_status)

        self._fwd_groups = []
        self._fwd_src_ws = None
        self._fwd_src_path = None
        return w

    def _fwd_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '选择界址点坐标 Excel', '',
            'Excel 文件 (*.xlsx *.xlsm);;所有文件 (*.*)')
        if path:
            self._fwd_load(path)

    def _fwd_reload(self):
        if self._fwd_src_path:
            self._fwd_load(self._fwd_src_path)
        else:
            QMessageBox.information(self, '提示', '请先选择 Excel 文件。')

    def _fwd_export(self):
        if not self._fwd_groups:
            QMessageBox.warning(self, '无数据', '请先加载 Excel。')
            return
        stem = Path(self._fwd_src_path).stem
        suggested = str(Path(self._fwd_src_path).with_name(f'{stem}_中心点结果.xlsx'))
        out, _ = QFileDialog.getSaveFileName(
            self, '保存新 Excel', suggested, 'Excel 文件 (*.xlsx)')
        if not out:
            return
        try:
            export_excel(self._fwd_groups, self._fwd_src_ws, out)
        except Exception as e:
            QMessageBox.critical(self, '导出失败', str(e))
            return
        QMessageBox.information(self, '已导出', f'已保存到：\n{out}')

    def _fwd_load(self, path):
        try:
            groups, ws = parse_excel(path)
        except Exception as e:
            QMessageBox.critical(self, '读取失败', f'无法读取 Excel：\n{e}')
            return
        if not groups:
            QMessageBox.warning(self, '无有效数据',
                                'Excel 解析后没有任何地块数据，请检查表结构。')
            return

        self._fwd_groups = groups
        self._fwd_src_ws = ws
        self._fwd_src_path = path
        self._fwd_path_lbl.setText(f'{Path(path).name}')
        self._fwd_refresh()
        total = sum(g['count'] for g in groups)
        self._fwd_status.setText(
            f'已加载：{Path(path).name}  ·  共 {len(groups)} 个地块  ·  {total} 个界址点（去重后）')

    def _fwd_refresh(self):
        raw_rows = []
        for g in self._fwd_groups:
            for row in g['rows']:
                raw_rows.append({
                    '地块名称': row['name'],
                    '序号': row['seq'] if row['seq'] is not None else '',
                    '界址点': row['point_id'] or '',
                    'x (m)': f"{row['x']:.3f}",
                    'y (m)': f"{row['y']:.3f}",
                })
        self._fwd_tbl_raw.show_df(pd.DataFrame(raw_rows))

        res_rows = []
        total_pts = 0
        for g in self._fwd_groups:
            total_pts += g['count']
            res_rows.append({
                '地块名称': g['name'],
                '闭环': '是' if g['is_closed'] else '否',
                '点数': g['count'],
                '中心 X (m)': f"{g['cx']:.3f}",
                '中心 Y (m)': f"{g['cy']:.3f}",
                '面积 (m²)': f"{g['area']:.2f}",
                '周长 (m)': f"{g['perim']:.2f}",
            })
        self._fwd_tbl_res.show_df(pd.DataFrame(res_rows))
        self._fwd_summary.setText(f'{len(self._fwd_groups)} 个地块  |  {total_pts} 个界址点（去重）')

    # =================================================================
    # Tab ② 中心 → 界址点
    # =================================================================
    def _build_reverse_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)

        # --- 输入模式 ---
        input_frame = QFrame()
        input_frame.setFrameShape(QFrame.StyledPanel)
        ifl = QVBoxLayout(input_frame)
        ifl.addWidget(QLabel('输入中心点（对边距 S = 两平行边净距 = 外接方形边长）'))

        mode_bar = QHBoxLayout()
        self._rev_radio_manual = QRadioButton('手动单组')
        self._rev_radio_excel = QRadioButton('Excel 批量')
        self._rev_radio_manual.setChecked(True)
        self._rev_radio_manual.toggled.connect(self._rev_switch_mode)
        mode_bar.addWidget(self._rev_radio_manual)
        mode_bar.addWidget(self._rev_radio_excel)
        mode_bar.addStretch(1)
        ifl.addLayout(mode_bar)

        # 手动输入行
        self._rev_manual_frame = QFrame()
        mfl = QGridLayout(self._rev_manual_frame)
        mfl.setContentsMargins(0, 4, 0, 0)

        mfl.addWidget(QLabel('地块名称'), 0, 0)
        self._rev_name_edit = QLineEdit('XF6')
        self._rev_name_edit.setFixedWidth(90)
        mfl.addWidget(self._rev_name_edit, 0, 1)

        mfl.addWidget(QLabel('中心 X (m)'), 0, 2)
        self._rev_cx_edit = QLineEdit()
        self._rev_cx_edit.setFixedWidth(120)
        mfl.addWidget(self._rev_cx_edit, 0, 3)

        mfl.addWidget(QLabel('中心 Y (m)'), 0, 4)
        self._rev_cy_edit = QLineEdit()
        self._rev_cy_edit.setFixedWidth(120)
        mfl.addWidget(self._rev_cy_edit, 0, 5)

        mfl.addWidget(QLabel('对边距 S (m)'), 0, 6)
        self._rev_s_edit = QLineEdit('23.308')
        self._rev_s_edit.setFixedWidth(80)
        mfl.addWidget(self._rev_s_edit, 0, 7)

        btn_gen = QPushButton('生成预览')
        btn_gen.setProperty('primaryBtn', True)
        btn_gen.clicked.connect(self._rev_manual_generate)
        mfl.addWidget(btn_gen, 0, 8)

        btn_append = QPushButton('追加')
        btn_append.clicked.connect(self._rev_manual_append)
        mfl.addWidget(btn_append, 0, 9)

        btn_clear = QPushButton('清空')
        btn_clear.clicked.connect(self._rev_clear)
        mfl.addWidget(btn_clear, 0, 10)

        ifl.addWidget(self._rev_manual_frame)

        # Excel 批量行
        self._rev_excel_frame = QFrame()
        efl = QHBoxLayout(self._rev_excel_frame)
        efl.setContentsMargins(0, 4, 0, 0)
        efl.addWidget(QLabel('默认对边距 S (m)'))
        self._rev_s_default_edit = QLineEdit('23.308')
        self._rev_s_default_edit.setFixedWidth(80)
        efl.addWidget(self._rev_s_default_edit)

        btn_excel = QPushButton('选择中心点 Excel')
        btn_excel.setProperty('primaryBtn', True)
        btn_excel.clicked.connect(self._rev_excel_open)
        efl.addWidget(btn_excel)

        self._rev_excel_info = QLabel('列：地块名称 | 中心X | 中心Y | [对边距S]')
        self._rev_excel_info.setStyleSheet('color:#555;')
        efl.addWidget(self._rev_excel_info)
        efl.addStretch(1)

        self._rev_excel_frame.setVisible(False)
        ifl.addWidget(self._rev_excel_frame)

        lay.addWidget(input_frame)

        # --- 输出格式 ---
        fmt_bar = QHBoxLayout()
        fmt_bar.addWidget(QLabel('表标题'))
        self._rev_title_edit = QLineEdit('界址点坐标表')
        self._rev_title_edit.setFixedWidth(180)
        fmt_bar.addWidget(self._rev_title_edit)

        fmt_bar.addWidget(QLabel('坐标系说明'))
        self._rev_datum_edit = QLineEdit('（大地2000坐标系）')
        self._rev_datum_edit.setFixedWidth(140)
        fmt_bar.addWidget(self._rev_datum_edit)

        self._rev_merge_chk = QCheckBox('合并同名地块名称单元格')
        self._rev_merge_chk.setChecked(True)
        self._rev_merge_chk.toggled.connect(self._rev_refresh_preview)
        fmt_bar.addWidget(self._rev_merge_chk)

        fmt_bar.addStretch(1)
        btn_export = QPushButton('导出界址点表')
        btn_export.setProperty('primaryBtn', True)
        btn_export.clicked.connect(self._rev_export)
        fmt_bar.addWidget(btn_export)
        lay.addLayout(fmt_bar)

        # --- 双栏预览 ---
        splitter = QSplitter()

        self._rev_tbl_input = DataTable()
        left = QFrame()
        left.setFrameShape(QFrame.StyledPanel)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)
        ll.addWidget(QLabel('输入中心点预览'))
        ll.addWidget(self._rev_tbl_input)

        self._rev_tbl_result = DataTable()
        right = QFrame()
        right.setFrameShape(QFrame.StyledPanel)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 4, 4, 4)
        rl.addWidget(QLabel('生成界址点预览（每组 9 行：J1-J8 + J1 闭合）'))
        rl.addWidget(self._rev_tbl_result)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        lay.addWidget(splitter, 1)

        self._rev_status = QLabel('就绪。手动填入中心坐标后点「生成预览」，或切换 Excel 批量。')
        self._rev_status.setStyleSheet('color:#444;')
        lay.addWidget(self._rev_status)

        self._rev_centers = []
        self._rev_rows = []
        return w

    def _rev_switch_mode(self):
        is_manual = self._rev_radio_manual.isChecked()
        self._rev_manual_frame.setVisible(is_manual)
        self._rev_excel_frame.setVisible(not is_manual)

    def _rev_clear(self):
        self._rev_centers = []
        self._rev_rows = []
        self._rev_tbl_input.show_df(pd.DataFrame())
        self._rev_tbl_result.show_df(pd.DataFrame())
        self._rev_status.setText('已清空。')

    def _rev_manual_generate(self):
        self._rev_manual_core(append=False)

    def _rev_manual_append(self):
        self._rev_manual_core(append=True)

    def _rev_manual_core(self, append):
        try:
            name = self._rev_name_edit.text().strip() or 'P1'
            cx = float(self._rev_cx_edit.text())
            cy = float(self._rev_cy_edit.text())
            S = float(self._rev_s_edit.text())
        except ValueError:
            QMessageBox.warning(self, '输入有误', '中心 X / 中心 Y / 对边距 S 必须为数字。')
            return
        if S <= 0:
            QMessageBox.warning(self, '输入有误', '对边距 S 必须为正数。')
            return
        self._rev_fill([{'name': name, 'cx': cx, 'cy': cy, 'S': S}], append=append)

    def _rev_excel_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '选择中心点 Excel', '',
            'Excel 文件 (*.xlsx *.xlsm);;所有文件 (*.*)')
        if not path:
            return
        try:
            default_S = float(self._rev_s_default_edit.text())
        except ValueError:
            default_S = 23.308
        try:
            centers = parse_centers_excel(path, default_S)
        except Exception as e:
            QMessageBox.critical(self, '读取失败', f'无法读取 Excel：\n{e}')
            return
        if not centers:
            QMessageBox.warning(self, '无有效数据',
                                '未解析到中心点。列序：地块名称 | 中心X | 中心Y | [对边距S]。')
            return
        self._rev_excel_info.setText(f'{Path(path).name}  ·  {len(centers)} 组中心点')
        self._rev_fill(centers)

    def _rev_fill(self, centers, append=False):
        if append and self._rev_centers:
            merged = {c['name']: c for c in self._rev_centers}
            for c in centers:
                merged[c['name']] = c
            centers = list(merged.values())
        self._rev_centers = centers
        self._rev_rows = build_boundary_rows(centers)

        input_rows = [{'地块名称': c['name'], '中心 X (m)': f"{c['cx']:.3f}",
                       '中心 Y (m)': f"{c['cy']:.3f}", '对边距 S (m)': f"{c['S']:.3f}"}
                      for c in centers]
        self._rev_tbl_input.show_df(pd.DataFrame(input_rows))
        self._rev_refresh_preview()
        self._rev_status.setText(
            f'已输入 {len(centers)} 组中心点 → {len(self._rev_rows)} 行界址点。'
            f'确认无误后点「导出界址点表」。')

    def _rev_refresh_preview(self):
        if not self._rev_rows:
            return
        merge = self._rev_merge_chk.isChecked()
        prev_name = None
        display_rows = []
        for r in self._rev_rows:
            show_name = r['name'] if (not merge or r['name'] != prev_name) else ''
            prev_name = r['name']
            display_rows.append({
                '地块名称': show_name,
                '序号': r['seq'],
                '界址点': r['pid'],
                'x (m)': f"{r['x']:.3f}",
                'y (m)': f"{r['y']:.3f}",
            })
        self._rev_tbl_result.show_df(pd.DataFrame(display_rows))
        n_groups = len({r['name'] for r in self._rev_rows})
        mode = '合并' if merge else '逐行显示'
        self._rev_status.setText(f'{n_groups} 组地块 × 9 行 = {len(self._rev_rows)} 行  ·  名称单元格：{mode}')

    def _rev_export(self):
        if not self._rev_rows:
            QMessageBox.warning(self, '无数据', '请先生成预览。')
            return
        out, _ = QFileDialog.getSaveFileName(
            self, '保存界址点表', '界址点坐标表_生成.xlsx', 'Excel 文件 (*.xlsx)')
        if not out:
            return
        try:
            export_boundary_excel(
                self._rev_centers, self._rev_rows, out,
                title=self._rev_title_edit.text().strip() or '界址点坐标表',
                datum=self._rev_datum_edit.text().strip(),
                merge_names=self._rev_merge_chk.isChecked(),
            )
        except Exception as e:
            QMessageBox.critical(self, '导出失败', str(e))
            return
        QMessageBox.information(self, '已导出', f'已保存到：\n{out}')


TAB = BoundaryCentroidTab

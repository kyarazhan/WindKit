"""WindKit：风资源工程小工具箱。

本文件是软件唯一入口（python windkit.py）：
  python windkit.py       桌面 GUI

主窗口定义在 ui/toolbox_window.py（ToolboxWindow）；
更新由独立的 updater.exe 完成（见 updater/ 包）。
"""

import json
import os
import subprocess
import sys

from core.paths import app_dir as _app_dir
from core.paths import resource_path

APP_DIR = _app_dir()


def _handle_update_pending() -> bool:
    """发现 .update/pending.json 时交接给独立更新器（或 bat 兜底）。

    返回 True 表示本进程应退出（更新交接完成）。"""
    pending = os.path.join(APP_DIR, '.update', 'pending.json')
    if not os.path.exists(pending):
        return False
    updater_exe = os.path.join(APP_DIR, 'updater.exe')
    if os.path.exists(updater_exe):
        try:
            cfg = json.loads(open(pending, encoding='utf-8').read())
        except Exception:
            cfg = {}
        cfg['app_dir'] = APP_DIR
        cfg['pid'] = os.getpid()    # 更新器等本进程退出后再替换文件
        with open(pending, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        subprocess.Popen(
            [updater_exe, '--config', pending],
            cwd=APP_DIR,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS,
            close_fds=True)
        return True
    # 兜底：bat 脚本接管更新（cmd.exe 不加载主程序 DLL，无锁冲突）
    package_name = ''
    try:
        pdata = json.loads(open(pending, encoding='utf-8').read())
        package_name = os.path.basename(pdata.get('package', ''))
    except Exception:
        package_name = ''
    bat = os.path.join(APP_DIR, '_do_update.bat')
    with open(bat, 'w', encoding='utf-8') as f:
        f.write('@echo off\n')
        f.write('chcp 65001 >NUL\n')
        f.write('title WindKit Updater\n')
        f.write(':wait\n')
        f.write('tasklist /FI "IMAGENAME eq WindKit.exe" 2>NUL')
        f.write(' | find /I "WindKit.exe" >NUL\n')
        f.write('if not errorlevel 1 (\n')
        f.write('    timeout /t 2 /nobreak >NUL\n')
        f.write('    goto wait\n')
        f.write(')\n')
        f.write('if not exist "data\\backups" mkdir "data\\backups"\n')
        f.write('if exist "data\\turbines.json" copy /Y "data\\turbines.json" '
                '"data\\backups\\turbines_pre_update.json" >NUL\n')
        f.write(f'tar -xf ".update\\{package_name}"\n')
        f.write('start "" "WindKit.exe"\n')
        f.write('del ".update\\pending.json" 2>NUL\n')
        f.write(f'del ".update\\{package_name}" 2>NUL\n')
        f.write('del "%~f0"\n')
    subprocess.Popen(
        ['cmd', '/c', bat],
        cwd=APP_DIR,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.DETACHED_PROCESS,
        close_fds=True)
    return True


def main() -> None:
    # 更新交接：有 pending 都让位给更新器（旧版遗留的 pending.json 由
    # updater.exe --config 兼容路径应用）
    if _handle_update_pending():
        sys.exit(0)
    # v1.0.2 机型库精简迁移（幂等，见 core/turbine.ensure_seed_migrated）
    try:
        from core.turbine import ensure_seed_migrated
        ensure_seed_migrated()
    except Exception:
        pass
    _run_gui()


def _run_gui() -> None:
    """桌面 GUI：异常落日志 → QApplication → 主窗口 → 主循环。"""
    # 未捕获异常写入运行日志，便于定位「闪退」
    def _except_hook(t, v, tb):
        try:
            import traceback
            log = os.path.join(APP_DIR, 'data', 'boot_error.log')
            os.makedirs(os.path.dirname(log), exist_ok=True)
            with open(log, 'a', encoding='utf-8') as f:
                f.write('未捕获异常 '
                        + ''.join(traceback.format_exception(t, v, tb))
                        [-2000:] + '\n')
        except Exception:
            pass
        sys.__excepthook__(t, v, tb)

    sys.excepthook = _except_hook

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QIcon, QPalette
    from PySide6.QtWidgets import QApplication

    qapp = QApplication(sys.argv)
    qapp.setStyle('Fusion')
    _force_light_palette(qapp)

    icon = resource_path('icon.png')
    if os.path.exists(icon):
        qapp.setWindowIcon(QIcon(icon.replace('\\', '/')))  # 任务栏图标

    qss = resource_path('ui', 'theme.qss')
    if os.path.exists(qss):
        with open(qss, 'r', encoding='utf-8') as f:
            qapp.setStyleSheet(f.read())

    from ui.toolbox_window import ToolboxWindow
    win = ToolboxWindow()
    win.show()
    sys.exit(qapp.exec())


def _force_light_palette(app) -> None:
    """强制应用浅色调色板，避免 PySide6 在 Windows 11 暗色主题下被 native
    style 接管，导致 QMenu / QInputDialog 出现"深色背景+看不清"。

    必须在 ``app.setStyle('Fusion')`` 之后调用，因为 Fusion 才认 QPalette。
    注：tooltip 浅色不在这里做，由 ``ToolItem._TooltipBubble`` 自建浮层
    绕开 native QTipLabel（见 ui/tool_item.py）。
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPalette

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor('#eef1f5'))
    pal.setColor(QPalette.ColorRole.WindowText, QColor('#1f3b4d'))
    pal.setColor(QPalette.ColorRole.Base, QColor('#ffffff'))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor('#f4f6f9'))
    pal.setColor(QPalette.ColorRole.Text, QColor('#1f3b4d'))
    pal.setColor(QPalette.ColorRole.Button, QColor('#ffffff'))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor('#1f3b4d'))
    pal.setColor(QPalette.ColorRole.Highlight, QColor('#185fa5'))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor('#ffffff'))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor('#fffde8'))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor('#1f3b4d'))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor('#8a9199'))
    pal.setColor(QPalette.ColorRole.Link, QColor('#185fa5'))
    pal.setColor(QPalette.ColorRole.Dark, QColor('#c0c5cb'))
    pal.setColor(QPalette.ColorRole.Mid, QColor('#d8dce0'))
    pal.setColor(QPalette.ColorRole.Light, QColor('#f4f6f9'))
    app.setPalette(pal)
    if hasattr(app.styleHints(), 'setColorScheme'):
        try:
            app.styleHints().setColorScheme(Qt.ColorScheme.Light)
        except Exception:
            pass


if __name__ == '__main__':
    main()

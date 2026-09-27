"""更新器「独立运行 + 在线更新」全 GUI 流程端到端（需系统 Python 带 tkinter）。

与真实双击 updater.exe 完全同构：主线程跑 mainloop()，全部 tkinter 访问
经由 after 回调在主线程发生（工作线程只通过队列回报进度）。

  1. _e2e_gui/WindKit = 已安装的 v1.0.0（含用户改过的机型库）
  2. _e2e_gui/src/    = 更新源（versions.json + WindKit-1.0.1.zip）
  3. 无参数构造 UpdaterApp（独立运行模式）→ 在线检查 → 版本列表出现 1.0.1
     → 下载并安装 → 等待「更新完成」
  4. 断言安装结果（版本文件/exe 替换/新插件/用户数据保留/备份）
"""
import glob
import json
import os
import shutil
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(ROOT, '_e2e_gui')
INST = os.path.join(BASE, 'WindKit')
SRC = os.path.join(BASE, 'src')
sys.path.insert(0, os.path.join(ROOT, 'updater'))

shutil.rmtree(BASE, ignore_errors=True)
shutil.copytree(os.path.join(ROOT, 'dist', 'WindKit'), INST)
os.makedirs(SRC)

# 用户数据：首运行种子化 + 自定义机型
turb_path = os.path.join(INST, 'data', 'turbines.json')
shutil.copy(os.path.join(INST, '_internal', 'data', 'turbines.json'), turb_path)
turbines = json.load(open(turb_path, encoding='utf-8'))
turbines.append({'vendor': '自定义', 'model': 'MY-3000', 'd': 140, 'p': 3000,
                 's': 15393.8, 'sp': 5.1})
json.dump(turbines, open(turb_path, 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
user_count = len(turbines)

# 更新源：v1.0.1 全量包
pkg = os.path.join(SRC, 'WindKit-1.0.1.zip')
plug = os.path.join(INST, '_internal', 'plugins', '02_风资源分析',
                    '10_turbulence.py')
with zipfile.ZipFile(pkg, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('WindKit/WindKit.exe',
                open(os.path.join(INST, 'WindKit.exe'), 'rb').read() + b'\x01')
    zf.writestr('WindKit/_internal/plugins/02_风资源分析/10_turbulence.py',
                open(plug, encoding='utf-8').read() + '\n# v1.0.1 修订\n')
    zf.writestr('WindKit/data/app_version.txt', '1.0.1\n')
    zf.writestr('WindKit/_internal/plugins/07_新功能/10_示例新工具.py',
                'TITLE = "示例新工具"\n')
json.dump({'versions': [{'version': '1.0.1', 'date': '2026-09-27',
                         'changelog': '新增示例新工具',
                         'full': {'url': 'WindKit-1.0.1.zip', 'sha256': ''}}]},
          open(os.path.join(SRC, 'versions.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)

# ---- 独立运行模式（无参数 = 双击 updater.exe）构造更新器窗口 ----
import updater_main  # noqa: E402

task = updater_main.build_standalone_task()
# 用模拟安装目录与本地源替换自探测结果（双击真实场景下这就是远程源）
task.update({'app_dir': INST, 'current_version': '1.0.0',
             'sources': [{'name': 'local-src',
                          'manifest_url': os.path.join(SRC, 'manifest.json')}]})

app = updater_main.UpdaterApp(task)
app.restart_after.set(False)          # 验证中不自动重启主程序（避免弹窗）

state = {'checked': False, 'installed': False, 'fail': False}
T0 = time.time()


def watch_chooser():
    if state['fail']:
        return finish()
    lb = getattr(app, 'lb_versions', None)
    if lb is not None and lb.size() > 0:
        state['checked'] = True
        print('PASS 版本列表出现:', lb.get(0))
        app._start_install()
        app.root.after(200, watch_install)
        return
    if time.time() - T0 > 30:
        return finish()
    app.root.after(100, watch_chooser)


def watch_install():
    if not app.installing:
        phase = str(app.lb_phase.cget('text'))
        if phase.startswith('更新完成'):
            state['installed'] = True
            print('PASS 安装阶段:', phase)
            return finish()
        if phase.startswith('更新失败') or state['fail']:
            return finish()
    if time.time() - T0 > 120:
        return finish()
    phase = str(app.lb_phase.cget('text'))
    if phase.startswith('更新失败'):
        state['fail'] = True
    app.root.after(150, watch_install)


def finish():
    try:
        app.root.destroy()
    except Exception:
        pass


def step1():
    app.mode_var.set('online')
    app._start_check()
    app.root.after(150, watch_chooser)


app.root.after(300, step1)
app.root.mainloop()

# ---- 断言 ----
ok = True


def check(name, cond):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name)
    ok = ok and cond


check('在线检查 → 版本列表出现 v1.0.1', state['checked'])
check('GUI 全流程安装完成（下载→关主程序→备份→替换）', state['installed'])
new_ver = open(os.path.join(INST, 'data', 'app_version.txt'),
               encoding='utf-8').read().strip()
check('版本文件 1.0.0 → 1.0.1', new_ver == '1.0.1')
check('主程序 exe 已替换',
      open(os.path.join(INST, 'WindKit.exe'), 'rb').read().endswith(b'\x01'))
check('新插件落地', os.path.exists(os.path.join(
    INST, '_internal', 'plugins', '07_新功能', '10_示例新工具.py')))
check('既有插件修订', '# v1.0.1 修订' in open(plug, encoding='utf-8').read())
turb_after = json.load(open(turb_path, encoding='utf-8'))
check('用户机型库保留', len(turb_after) == user_count
      and turb_after[-1]['model'] == 'MY-3000')
check('更新前自动备份生成',
      bool(glob.glob(os.path.join(INST, 'data', 'backups',
                                  'pre_update_*.zip'))))

shutil.rmtree(BASE, ignore_errors=True)
print('\nGUI E2E ' + ('ALL PASS' if ok else 'HAS FAILURES'))
sys.exit(0 if ok else 1)

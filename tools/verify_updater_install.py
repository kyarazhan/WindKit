"""更新器端到端实证（用系统 Python 跑：需要 tkinter 导入 updater_main）：

1. 复制 dist/WindKit → _e2e/WindKit 当作「已安装的 v1.0.0」
2. 用户改过机型库（模拟真实使用）
3. 制作假的 v1.0.1 更新包（带顶层 WindKit/ 文件夹 + 新增一个插件分类）
4. 写 .update/pending.json，调真实 updater.exe --config 应用更新
5. 断言：版本文件更新 / 新插件落地 / 用户机型库保留 / 自动备份生成
"""
import json
import os
import glob
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
E2E = os.path.join(ROOT, '_e2e')
INST = os.path.join(E2E, 'WindKit')
sys.path.insert(0, os.path.join(ROOT, 'updater'))

shutil.rmtree(E2E, ignore_errors=True)
shutil.copytree(os.path.join(ROOT, 'dist', 'WindKit'), INST)

# ---- 1. 模拟用户已用了一段时间：首运行种子化机型库 + 加一台自定义机型 ----
turb_path = os.path.join(INST, 'data', 'turbines.json')
if not os.path.exists(turb_path):
    # 首运行：TurbineDB 从随包只读种子库初始化用户库（此处手工等价模拟）
    shutil.copy(os.path.join(INST, '_internal', 'data', 'turbines.json'),
                turb_path)
turbines = json.load(open(turb_path, encoding='utf-8'))
turbines.append({'vendor': '自定义', 'model': 'MY-2500', 'd': 130, 'p': 2500,
                 's': 13273.2, 'sp': 5.3})
json.dump(turbines, open(turb_path, 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
user_count = len(turbines)

# ---- 2. 制作 v1.0.1 更新包（顶层 WindKit/ 文件夹）----
# 业务代码编在 exe 内嵌 PYZ 中；随包分发到 _internal 的插件源码是
# 运行期动态装载的，正是「后续新增功能」随增量/全量包落地的真实载体
pkg = os.path.join(E2E, 'WindKit-1.0.1.zip')
plug = os.path.join(INST, '_internal', 'plugins', '02_风资源分析',
                    '10_turbulence.py')
with zipfile.ZipFile(pkg, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('WindKit/WindKit.exe',
                open(os.path.join(INST, 'WindKit.exe'), 'rb').read() + b'\x01')
    zf.writestr('WindKit/_internal/plugins/02_风资源分析/10_turbulence.py',
                open(plug, encoding='utf-8').read() + '\n# v1.0.1 修订\n')
    zf.writestr('WindKit/data/app_version.txt', '1.0.1\n')
    # 模拟「后续陆续添加新功能」：更新包带来一个全新的插件分类与工具
    zf.writestr('WindKit/_internal/plugins/07_新功能/10_示例新工具.py',
                'TITLE = "示例新工具"\n')

# ---- 3. pending.json + 真实 updater.exe 应用更新 ----
upd = os.path.join(INST, 'updater.exe')
pend = os.path.join(INST, '.update', 'pending.json')
os.makedirs(os.path.dirname(pend), exist_ok=True)
json.dump({'app_dir': INST, 'package': pkg, 'pid': 0, 'app_exe': 'WindKit.exe'},
          open(pend, 'w', encoding='utf-8'), ensure_ascii=False)
rc = subprocess.run([upd, '--config', pend], cwd=INST,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    timeout=120).returncode
print('updater.exe --config exit code:', rc)

# 更新器末尾会自动重启主程序 —— 验证完关掉
time.sleep(2)
subprocess.run(['taskkill', '/IM', 'WindKit.exe', '/F'], capture_output=True)

# ---- 4. 断言 ----
ok = True


def check(name, cond):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name)
    ok = ok and cond


new_ver = open(os.path.join(INST, 'data', 'app_version.txt'),
               encoding='utf-8').read().strip()
check('版本文件 1.0.0 → 1.0.1', new_ver == '1.0.1')
check('主程序 exe 已被替换（字节变化）',
      open(os.path.join(INST, 'WindKit.exe'), 'rb').read().endswith(b'\x01'))
check('新插件随更新落地（07_新功能/10_示例新工具.py）',
      os.path.exists(os.path.join(
          INST, '_internal', 'plugins', '07_新功能', '10_示例新工具.py')))
check('既有插件随更新修订（turbulence.py 带 v1.0.1 标记）',
      '# v1.0.1 修订' in open(plug, encoding='utf-8').read())
turb_after = json.load(open(turb_path, encoding='utf-8'))
check(f'用户机型库保留（{user_count} 台含自定义机型）',
      len(turb_after) == user_count and turb_after[-1]['model'] == 'MY-2500')
check('pending.json 已清理', not os.path.exists(pend))
bk = glob.glob(os.path.join(INST, 'data', 'backups', 'pre_update_*.zip'))
check('更新前自动备份已生成', bool(bk))
log = open(os.path.join(INST, 'data', 'backups', 'updater.log'),
           encoding='utf-8').read()
check('更新日志记录 legacy apply done', 'legacy apply done' in log)

print('\nE2E ' + ('ALL PASS' if ok else 'HAS FAILURES'))
shutil.rmtree(E2E, ignore_errors=True)
sys.exit(0 if ok else 1)

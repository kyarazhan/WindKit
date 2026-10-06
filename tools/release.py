"""发布自动化：一条龙出完整包 + 增量包 + 版本索引 + 源码归档（本地 release/）。

用法:
    python tools/release.py 1.0.0 --notes "首个发布版本"
    python tools/release.py 1.0.1 --notes "新增××工具" --skip-build   # dist 已是新版时复用

流程:
  1. 校验 core/version.py 与参数一致（不一致直接拒绝，防止版本漂移）
  2. PyInstaller 打包（--skip-build 跳过；需系统 Python，含 tkinter）
  3. 冻结 exe 冒烟（offscreen 启动 6s 存活）
  4. 完整包   release/<版本>/WindKit-<版本>.zip（sha256 记入索引）
  5. 基线重演：release/ 里找上一版全量包，按顺序叠加其后的增量包
  6. 文件级 diff（sha256）→ release/<版本>/<旧>-<新>-patch.zip
     （data/ 用户数据整体排除；data/app_version.txt 每个包必须携带）
  7. 版本索引 release/<版本>/versions.json（changelog 来自 --notes）
  8. 源码归档 release/<版本>/WindKit_v<版本>_source_<日期>.zip（项目无 git，
     归档在此生成；排除 .venv/dist/build/release 与一切缓存）

发版后手工步骤（见 RELEASE.md）：git tag（git 化后）→ 把 versions.json 与
增量包（或全量包）上传到 updater/sources.json 指向的更新源。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
REL = os.path.join(ROOT, 'release')
DIST = os.path.join(ROOT, 'dist', 'WindKit')
APP_NAME = 'WindKit'

# 源码归档排除（目录名或文件名）；下划线开头的顶层目录（_v100 安装备份、
# _release_base 等临时物）与任何层级的 build/dist 一律排除
_SRC_EXCLUDE = {'.venv', 'dist', 'build', 'release', '__pycache__',
                '.pytest_cache', '.update', 'node_modules'}


def sha256(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def vtuple(v: str):
    return tuple(int(x) for x in v.split('.'))


def run(cmd, **kw):
    print('>', ' '.join(cmd))
    subprocess.run(cmd, check=True, **kw)


def build(new: str) -> None:
    cur = re.search(r"VERSION = '([^']+)'",
                    open('core/version.py', encoding='utf-8').read()).group(1)
    assert cur == new, f'core/version.py 是 {cur}，先改成 {new} 再发版'
    run([sys.executable, '-X', 'utf8', 'build.py'])


def smoke_exe() -> None:
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    proc = subprocess.Popen([os.path.join(DIST, 'WindKit.exe')], cwd=DIST,
                            env=env,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    time.sleep(6)
    alive = proc.poll() is None
    if alive:
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/F'],
                       capture_output=True)
    assert alive, '冻结 exe 启动后闪退'
    # 清理冒烟运行产生的运行时残留：data/ 仅保留 app_version.txt（程序
    # 元数据，完整包必须携带——独立更新器靠它识别已装版本）；
    # .update/（后台更新器任务残留）整目录移除，不进发布包
    data = os.path.join(DIST, 'data')
    if os.path.isdir(data):
        for entry in os.listdir(data):
            if entry == 'app_version.txt':
                continue
            p = os.path.join(data, entry)
            shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) \
                else os.remove(p)
    shutil.rmtree(os.path.join(DIST, '.update'), ignore_errors=True)
    print('exe smoke: alive OK')


def find_baseline(new: str):
    """在 release/<版本>/ 各目录里找上一版全量包与其后的增量包。

    返回 (基线版本号, 全量包路径, [补丁路径...])；没有历史全量包返回 None。"""
    fulls = []
    patches = []
    for dirpath, _dirs, files in os.walk(REL):
        for f in files:
            m = re.fullmatch(rf'{APP_NAME}-(\d+(?:\.\d+)+)\.zip', f)
            if m and vtuple(m.group(1)) < vtuple(new):
                fulls.append((vtuple(m.group(1)), m.group(1),
                              os.path.join(dirpath, f)))
                continue
            m = re.fullmatch(r'(\d+(?:\.\d+)+)-(\d+(?:\.\d+)+)-patch\.zip', f)
            # 终点必须严格小于本版本：== new 的是本次正在重新生成的产物，
            # 计入基线会把「已升级到 new」的状态当成旧版（补丁退化为空）
            if m and vtuple(m.group(2)) < vtuple(new):
                patches.append((vtuple(m.group(1)), vtuple(m.group(2)),
                                os.path.join(dirpath, f)))
    if not fulls:
        return None
    fulls.sort()
    base_v, base_zip = fulls[-1][1], fulls[-1][2]
    chain = [p for p in sorted(patches) if p[0] >= vtuple(base_v)]
    return base_v, base_zip, [p[2] for p in chain]


def make_patch(new: str, vdir: str) -> str | None:
    """基线重演 + 文件级 diff → 增量包。无历史全量包时返回 None（首版）。"""
    base = find_baseline(new)
    if base is None:
        print('baseline: 无历史全量包（首版），跳过增量包')
        return None
    base_v, base_zip, patches = base
    work = os.path.join(ROOT, '_release_base')
    shutil.rmtree(work, ignore_errors=True)
    with zipfile.ZipFile(base_zip) as zf:
        zf.extractall(work)
    base_dir = os.path.join(work, APP_NAME)
    for p in patches:
        print('baseline +=', os.path.basename(p))
        with zipfile.ZipFile(p) as zf:
            zf.extractall(base_dir)
    print(f'baseline: v{base_v} + {len(patches)} patch(es)')

    def scan(root):
        out = {}
        for r, d, fs in os.walk(root):
            rel = os.path.relpath(r, root)
            if rel == '.':
                # 只排除安装根顶层的 data/（用户数据，更新永不覆盖）；
                # 嵌套的 _internal/data/ 是随包只读资源，必须进补丁
                d[:] = [x for x in d if x not in ('.update', 'data')]
            else:
                d[:] = [x for x in d if x != '.update']
            for f in fs:
                p = os.path.join(r, f)
                out[os.path.relpath(p, root).replace('\\', '/')] = sha256(p)
        return out

    old = scan(base_dir)
    changed = [rel for rel, h in scan(DIST).items() if old.get(rel) != h]
    # data/ 用户数据整体排除（更新永不覆盖），但 app_version.txt 是程序
    # 元数据，必须随每个补丁更新——独立更新器靠它识别已装版本
    changed.append('data/app_version.txt')
    changed.sort()
    patch_name = f'{base_v}-{new}-patch.zip'
    patch_path = os.path.join(vdir, patch_name)
    with zipfile.ZipFile(patch_path, 'w', zipfile.ZIP_DEFLATED,
                         compresslevel=9) as zf:
        for rel in changed:
            if rel == 'data/app_version.txt':
                zf.writestr(rel, new + '\n')
            else:
                zf.write(os.path.join(DIST, *rel.split('/')), rel)
    print(f'patch: {patch_name} {len(changed)} files, '
          f'{os.path.getsize(patch_path) / 1048576:.1f} MB')
    shutil.rmtree(work, ignore_errors=True)
    return patch_name


def make_source_archive(new: str, vdir: str) -> str:
    """项目无 git：源码归档在此生成（排除虚拟环境/产物/缓存）。"""
    stamp = time.strftime('%Y%m%d')
    name = f'{APP_NAME}_v{new}_source_{stamp}.zip'
    path = os.path.join(vdir, name)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) \
            as zf:
        for r, d, fs in os.walk(ROOT):
            d[:] = [x for x in d
                    if x not in _SRC_EXCLUDE and not x.startswith('_')]
            for f in fs:
                if f.endswith(('.pyc', '.pyo', '.log')):
                    continue
                p = os.path.join(r, f)
                zf.write(p, os.path.join(
                    APP_NAME, os.path.relpath(p, ROOT)))
    print(f'src  : {name} {os.path.getsize(path) / 1048576:.1f} MB')
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('version')
    ap.add_argument('--notes', default='', help='本版更新说明（进 versions.json）')
    ap.add_argument('--skip-build', action='store_true')
    args = ap.parse_args()
    new = args.version
    os.makedirs(REL, exist_ok=True)
    vdir = os.path.join(REL, new)          # 本版全部产物集中于此
    os.makedirs(vdir, exist_ok=True)

    if not args.skip_build:
        build(new)
    smoke_exe()

    # ---- 完整包（带顶层文件夹 WindKit/，更新器安装时自动去前缀）----
    full_name = f'{APP_NAME}-{new}.zip'
    full_path = os.path.join(vdir, full_name)
    shutil.make_archive(full_path[:-4], 'zip', root_dir=os.path.join(ROOT,
                                                                     'dist'),
                        base_dir=APP_NAME)
    print(f'full : {full_name} {os.path.getsize(full_path) / 1048576:.1f} MB')

    # ---- 增量包（有上一版全量包时）----
    patch_name = make_patch(new, vdir)

    # ---- 源码归档 ----
    make_source_archive(new, vdir)

    # ---- versions.json ----
    entry = {'version': new,
             'date': time.strftime('%Y-%m-%d'),
             'changelog': args.notes or '缺陷修复与内部优化。',
             'full': {'url': full_name, 'sha256': sha256(full_path)}}
    if patch_name:
        psha = sha256(os.path.join(vdir, patch_name))
        base_v = re.match(r'(\d+(?:\.\d+)+)-\d+(?:\.\d+)+-patch\.zip',
                          patch_name).group(1)
        entry['patch'] = {'base': base_v, 'url': patch_name, 'sha256': psha}
    idx = {'versions': [entry]}
    with open(os.path.join(vdir, 'versions.json'), 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

    print('\n===== 发布清单（release/' + new + '/）=====')
    print(f'  {full_name}')
    if patch_name:
        print(f'  {patch_name}')
        print(f'  patch sha256: {entry["patch"]["sha256"]}')
    print(f'  full  sha256: {entry["full"]["sha256"]}')
    print('  versions.json')
    print('上传更新源（GitHub Release / 内网）：versions.json 必传；'
          '老用户升级传增量包，无增量时传全量包。')


if __name__ == '__main__':
    main()

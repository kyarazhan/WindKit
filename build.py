"""PyInstaller 打包脚本：
  dist/WindKit/WindKit.exe（主程序 onedir）+ updater.exe（独立更新器）
  + data/app_version.txt（版本溯源，独立更新器据此识别已装版本）

用法（在 venv 中）：
    pip install -r requirements.txt -r requirements-build.txt
    python build.py            # 打包主程序 + 更新器
    python build.py --updater  # 只重建更新器

发布物：
    dist/WindKit/              整目录压缩为 WindKit-<版本>.zip 发布
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys

from core.version import VERSION

ROOT = os.path.dirname(os.path.abspath(__file__))

# 主程序入口与业务包（全部编译进 exe/_internal）
ENTRY = 'windkit.py'
APP_PKGS = ['core', 'ui']

# 运行时必须排除的可选依赖与开发工具
EXCLUDES = [
    'matplotlib', 'numba', 'llvmlite', 'sqlalchemy', 'lxml', 'PIL',
    'psycopg2', 'psycopg_binary', 'pytest', 'tkinter',
]
# 本地业务包（随源码/资源分发，绝不作为 hidden-import）
LOCAL_PKGS = {'windkit', 'core', 'ui', 'updater', 'tests'}

# 只读资源：随包分发到 _internal/（运行期经 core.paths.resource_path 定位）
RESOURCES = [
    ('ui/theme.qss', 'ui'),
    ('icon.png', '.'),
    ('data/turbines.json', 'data'),
    ('data/samples', os.path.join('data', 'samples')),
    ('plugins', 'plugins'),
    ('updater/sources.json', 'updater'),
]


def _data(src: str, dst: str) -> str:
    """构造 --add-data 参数：源路径;目标目录。"""
    return f"{os.path.join(ROOT, src)}{os.pathsep}{dst}"


def _local_submodules() -> list[str]:
    """core/ui 业务包的全部子模块，显式加入打包清单。

    主程序入口静态分析只能覆盖自己 import 到的模块；插件运行时才
    import 的业务模块（如 core.air_density、core.shear）若不显式收集，
    打包版会全部 ModuleNotFoundError（v1.0.0 的 13 个插件装载失败即此因）。"""
    out = []
    for pkg in APP_PKGS:
        for r, d, fs in os.walk(os.path.join(ROOT, pkg)):
            d[:] = [x for x in d if x != '__pycache__']
            for f in fs:
                if f.endswith('.py') and f != '__init__.py':
                    rel = os.path.relpath(os.path.join(r, f), ROOT)
                    out.append(rel[:-3].replace('\\', '/').replace('/', '.'))
    return sorted(out)


def _scan_hidden_imports() -> list[str]:
    """静态扫描业务源码的全部 import（含函数级），返回第三方/标准库
    顶层模块名。插件经 importlib 动态装载，运行时分析不到，必须显式声明；
    插件依赖的 core/ui 本身就在业务包里，无需列入。"""
    tops: set[str] = set()
    files = [os.path.join(ROOT, ENTRY)]
    for pkg in APP_PKGS:
        for r, d, fs in os.walk(os.path.join(ROOT, pkg)):
            d[:] = [x for x in d if x != '__pycache__']
            files += [os.path.join(r, f) for f in fs if f.endswith('.py')]
    for r, d, fs in os.walk(os.path.join(ROOT, 'plugins')):
        d[:] = [x for x in d if x != '__pycache__']
        files += [os.path.join(r, f) for f in fs if f.endswith('.py')]
    for p in files:
        tree = ast.parse(open(p, encoding='utf-8').read())
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    tops.add(a.name.split('.')[0])
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                tops.add(n.module.split('.')[0])
    # updater 包的兄弟模块（feed/version）只被独立 updater.exe 使用
    tops -= {'feed', 'version'}
    return sorted(t for t in tops
                  if t not in LOCAL_PKGS and t not in EXCLUDES)


def _clean_pycache() -> None:
    """打包前清掉随包资源目录里的 __pycache__（add-data 会原样拷贝）。"""
    for top in ('plugins', 'data'):
        for r, d, _fs in os.walk(os.path.join(ROOT, top)):
            d[:] = [x for x in d if x != '__pycache__']
            for x in list(d):
                if x == '__pycache__':
                    import shutil
                    shutil.rmtree(os.path.join(r, x), ignore_errors=True)


def build_app() -> None:
    dist_dir = os.path.join(ROOT, "dist", "WindKit")
    hidden = _scan_hidden_imports()
    _clean_pycache()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "WindKit",
        "--onedir",
        "--windowed",
        "--icon", os.path.join(ROOT, "icon.ico"),
    ]
    for src, dst in RESOURCES:
        cmd += ["--add-data", _data(src, dst)]
    cmd += [
        "--distpath", os.path.join(ROOT, "dist"),
        "--workpath", os.path.join(ROOT, "build", "WindKit"),
        "--specpath", os.path.join(ROOT, "build"),
        "--clean", "--noconfirm",
    ]
    for h in hidden + _local_submodules():
        cmd += ["--hidden-import", h]
    for e in EXCLUDES:
        cmd += ["--exclude-module", e]
    cmd.append(os.path.join(ROOT, ENTRY))
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)

    # 版本溯源文件（独立更新器据此识别已装版本）
    data_dir = os.path.join(dist_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "app_version.txt"), "w",
              encoding="utf-8") as f:
        f.write(VERSION + "\n")

    print("\n主程序打包完成 → dist/WindKit/WindKit.exe (v" + VERSION + ")")


def build_updater() -> None:
    # 更新器界面是 tkinter（纯标准库）：部分精简版 Python（如 uv/embeddable
    # 的 3.13 venv）不带 tkinter，提前给出可行动的报错而不是 PyInstaller 半途炸
    try:
        import tkinter  # noqa: F401
    except ImportError:
        sys.exit('!! 当前 Python 缺少 tkinter，无法构建 updater.exe。\n'
                 '   请改用系统 Python（含 tcl/tk，如 python.exe 3.14）运行 build.py')
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "updater.spec",
        "--clean", "--noconfirm",
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=os.path.join(ROOT, "updater"))
    # spec 产物在 updater/dist/updater.exe → 挪到主程序目录旁
    src = os.path.join(ROOT, "updater", "dist", "updater.exe")
    dst = os.path.join(ROOT, "dist", "WindKit", "updater.exe")
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(src, dst)
        print("更新器打包完成 →", dst)
    else:
        print("!! 未找到 updater/dist/updater.exe，请检查打包输出")


def main() -> None:
    if "--updater" in sys.argv:
        build_updater()
        return
    build_app()
    build_updater()
    print("\n全部完成。发布：python tools/release.py <版本> --notes \"说明\"")


if __name__ == '__main__':
    main()

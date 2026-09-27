"""build.py 打包清单回归：防止业务子模块再次漏出插件依赖（v1.0.0 的 13 插件失败）。"""
import importlib.util
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location(
    'build', os.path.join(ROOT, 'build.py'))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_local_submodules_cover_all_core_ui():
    mods = set(build._local_submodules())
    # 插件运行时才 import 的典型业务模块必须显式在打包清单里
    for required in ('core.air_density', 'core.shear', 'core.turbine',
                     'core.boundary_centroid', 'core.distributions',
                     'core.m1_split', 'ui.widgets', 'ui.base_tab'):
        assert required in mods, required
    assert not any(m.endswith('__init__') for m in mods)
    assert all('/' not in m and '\\' not in m for m in mods)


def test_local_submodules_are_deterministic():
    assert build._local_submodules() == build._local_submodules()

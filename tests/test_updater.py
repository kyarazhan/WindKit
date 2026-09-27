"""更新器回归测试：版本比较 / 版本索引解析 / 下载规划 / 安装提取与数据保护。

updater 五个模块以顶层兄弟模块互相 import（feed/version/config/updater_main），
此处用 importlib 按路径装载并在 sys.modules 注册兄弟名，不污染 sys.path。
updater_main 顶层 import tkinter：开发 venv（无 tkinter）时以 stub 顶替——
被测的安装/备份/提取全是纯逻辑，不构造 GUI。
"""
import hashlib
import importlib.util
import json
import os
import sys
import types
import zipfile

import pytest

UPDATER_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'updater'))
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# ---- tkinter stub（仅当环境没有 tkinter 时生效）----
try:
    import tkinter  # noqa: F401
except ImportError:
    _tk = types.ModuleType('tkinter')
    _tk.ttk = types.ModuleType('tkinter.ttk')
    sys.modules.setdefault('tkinter', _tk)
    sys.modules.setdefault('tkinter.ttk', _tk.ttk)


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(UPDATER_DIR, name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


upver = _load('version')
feed = _load('feed')
_load('config')
updater_main = _load('updater_main')


# ====================================================================
# 版本比较
# ====================================================================
def test_version_compare():
    assert upver.parse_version('1.2.3') == (1, 2, 3)
    assert upver.parse_version('1.2') == (1, 2, 0)
    assert upver.compare_versions('1.10.0', '1.9.9') == 1
    assert upver.compare_versions('1.0.0', '1.0.0') == 0
    assert upver.is_newer('1.0.1', '1.0.0')
    assert not upver.is_newer('1.0.0', '1.0.0')
    assert not upver.is_newer('1.0.0', '1.0.1')


# ====================================================================
# 版本索引：归一化 / 相对 URL 解析 / 本地 versions.json 源
# ====================================================================
def test_feed_normalize_resolves_relative_urls():
    entries = [{'version': 'v1.0.1', 'date': '2026-10-01', 'changelog': 'x',
                'full': {'url': 'WindKit-1.0.1.zip', 'sha256': 'abc'}}]
    out = feed._normalize(entries, 'http://host/wk/versions.json',
                          '1.0.0', True)
    assert out[0]['version'] == '1.0.1'
    assert out[0]['full']['url'] == 'http://host/wk/WindKit-1.0.1.zip'
    assert out[0]['full']['sha256'] == 'abc'


def test_feed_local_versions_json_source(tmp_path):
    """本地/UNC 源：索引与其引用的包同目录，相对名自动解析为绝对路径。"""
    pkg = tmp_path / 'WindKit-1.0.1.zip'
    pkg.write_bytes(b'placeholder')
    idx = {'versions': [{'version': '1.0.1', 'date': '2026-10-01',
                         'changelog': '说明',
                         'full': {'url': 'WindKit-1.0.1.zip',
                                  'sha256': 'x'}}]}
    (tmp_path / 'versions.json').write_text(json.dumps(idx, ensure_ascii=False),
                                            encoding='utf-8')
    task = {'sources': [{'name': 'nas',
                         'manifest_url': str(tmp_path / 'manifest.json')}],
            'current_version': '1.0.0',
            'include_prerelease': True}
    ents, notes = feed.fetch_index(task)
    assert ents and ents[0]['version'] == '1.0.1'
    assert ents[0]['full']['url'] == str(pkg)
    assert any('成功' in n for n in notes)


def test_feed_newer_versions_and_plan_full():
    entries = [
        {'version': '1.0.2', 'full': {'url': 'f2', 'sha256': ''},
         'patch': {'base': '1.0.1', 'url': 'u2', 'sha256': ''}},
        {'version': '1.0.1', 'full': {'url': 'f1', 'sha256': ''},
         'patch': {'base': '1.0.0', 'url': 'u1', 'sha256': ''}},
    ]
    assert [e['version'] for e in feed.newer_versions(entries, '1.0.0')] == \
        ['1.0.2', '1.0.1']
    pkgs, err = feed.plan_packages(entries, '1.0.0', '1.0.2', 'full')
    assert err == '' and len(pkgs) == 1
    assert pkgs[0]['label'] == '全量包 WindKit-1.0.2.zip'


def test_feed_plan_patch_chain_multi_hop():
    entries = [
        {'version': '1.0.2', 'full': {'url': 'f2', 'sha256': ''},
         'patch': {'base': '1.0.1', 'url': 'u2', 'sha256': ''}},
        {'version': '1.0.1', 'full': {'url': 'f1', 'sha256': ''},
         'patch': {'base': '1.0.0', 'url': 'u1', 'sha256': ''}},
    ]
    pkgs, err = feed.plan_packages(entries, '1.0.0', '1.0.2', 'patch')
    assert err == ''
    assert [p['label'] for p in pkgs] == \
        ['增量包 v1.0.0 → v1.0.1', '增量包 v1.0.1 → v1.0.2']
    # 断链：1.0.0 → 1.0.3 缺 1.0.2→1.0.3 的增量且 1.0.3 无全量 → 报错可读
    entries2 = [{'version': '1.0.3',
                 'patch': {'base': '1.0.2', 'url': 'u3', 'sha256': ''}}]
    _pkgs, err = feed.plan_packages(entries2, '1.0.0', '1.0.3', 'patch')
    assert '没有适用于 v1.0.0 的增量包' in err


# ====================================================================
# 安装：提取 / 用户数据保护 / 顶层目录归一化 / 无效包拒绝
# ====================================================================
def _make_pkg(path, files):
    with zipfile.ZipFile(path, 'w') as zf:
        for arc, data in files:
            zf.writestr(arc, data)


def test_extract_preserves_user_data_and_strips_top_folder(tmp_path):
    app = tmp_path / 'WindKit'
    (app / 'data').mkdir(parents=True)
    (app / 'data' / 'turbines.json').write_text('[{"user": true}]',
                                                encoding='utf-8')
    pkg = tmp_path / 'WindKit-1.0.1.zip'
    _make_pkg(pkg, [
        ('WindKit/WindKit.exe', 'NEWEXE'),
        ('WindKit/_internal/core/version.pyc', 'NEWPYC'),
        ('WindKit/data/turbines.json', '[{"bundled": true}]'),
        ('WindKit/data/app_version.txt', '1.0.1\n'),
    ])
    updater_main.extract_preserve_data(str(pkg), str(app))
    # 带顶层文件夹的完整包：自动去前缀，文件落到安装根
    assert (app / 'WindKit.exe').read_text(encoding='utf-8') == 'NEWEXE'
    assert (app / '_internal' / 'core' / 'version.pyc').read_text(
        encoding='utf-8') == 'NEWPYC'
    # data/turbines.json 属用户数据：更新绝不覆盖
    assert (app / 'data' / 'turbines.json').read_text(
        encoding='utf-8') == '[{"user": true}]'
    # app_version.txt 是程序元数据：随更新写入新版本
    assert (app / 'data' / 'app_version.txt').read_text(
        encoding='utf-8') == '1.0.1\n'


def test_extract_rejects_invalid_package(tmp_path):
    app = tmp_path / 'WindKit'
    app.mkdir()
    bad = tmp_path / 'source-archive.zip'
    _make_pkg(bad, [('readme.md', 'x'), ('core/version.py', 'v')])
    with pytest.raises(ValueError):
        updater_main.extract_preserve_data(str(bad), str(app))


# ====================================================================
# 备份 / 恢复
# ====================================================================
def test_backup_then_restore_roundtrip(tmp_path):
    app = tmp_path / 'WindKit'
    (app / 'data' / 'backups').mkdir(parents=True)
    (app / 'data' / 'turbines.json').write_text('[]', encoding='utf-8')
    (app / 'data' / 'note.txt').write_text('用户便签', encoding='utf-8')
    bdir = tmp_path / 'bk'
    dst = updater_main.backup_data(str(app), str(bdir))
    assert dst and os.path.exists(dst)
    (app / 'data' / 'turbines.json').write_text('CORRUPT', encoding='utf-8')
    n = updater_main.restore_backup(str(app), dst)
    assert n == 2
    assert (app / 'data' / 'turbines.json').read_text(
        encoding='utf-8') == '[]'
    assert (app / 'data' / 'note.txt').read_text(
        encoding='utf-8') == '用户便签'


# ====================================================================
# 下载（本地包通道）与 sha256 校验
# ====================================================================
def test_download_local_package_with_sha(tmp_path):
    src = tmp_path / 'pkg.zip'
    src.write_bytes(b'hello package')
    dest = tmp_path / 'staging' / 'pkg.zip'
    updater_main.download_package(
        str(src), str(dest), hashlib.sha256(b'hello package').hexdigest(),
        lambda d, t: None)
    assert dest.read_bytes() == b'hello package'

    dest2 = tmp_path / 'staging2' / 'pkg.zip'
    with pytest.raises(ValueError):
        updater_main.download_package(str(src), str(dest2), 'bad-sha',
                                      lambda d, t: None)
    assert not dest2.exists()      # 校验失败：半成品必须被删掉


# ====================================================================
# 独立运行（双击 updater.exe，无参数）的任务自构造
# ====================================================================
def test_standalone_task_dev_mode():
    task = updater_main.build_standalone_task()
    # 开发模式：安装根 = updater 的上一级（项目根）；更新源取 updater/sources.json
    assert os.path.normpath(task['app_dir']) == \
        os.path.normpath(os.path.join(ROOT))
    assert task['app_exe'] == 'WindKit.exe'
    assert isinstance(task['sources'], list) and task['sources']
    assert task['sources'][0]['type'] in ('github-releases',) or \
        task['sources'][0].get('manifest_url')

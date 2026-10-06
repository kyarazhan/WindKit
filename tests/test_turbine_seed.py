"""机型库种子迁移（v1.0.2）：未修改的旧种子替换为精简两机型；改过的库不动。"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core import turbine as tb  # noqa: E402


def test_unmodified_old_seed_replaced(tmp_path, monkeypatch):
    p = tmp_path / 'turbines.json'
    old = json.dumps(
        [{'vendor': '旧厂商', 'model': 'OLD-1', 'd': 100, 'p': 1000,
          's': 1.0, 'sp': 1.0}],
        ensure_ascii=False, indent=1)
    p.write_text(old, encoding='utf-8', newline='')
    monkeypatch.setattr(
        tb, '_OLD_SEED_SHA256',
        hashlib.sha256(p.read_bytes()).hexdigest())

    assert tb.migrate_seed_if_unmodified(str(p)) is True
    models = [t['model'] for t in json.load(open(p, encoding='utf-8'))]
    assert models == ['GWH221-6250', 'GWH221-6700']


def test_modified_library_untouched(tmp_path, monkeypatch):
    p = tmp_path / 'turbines.json'
    custom = json.dumps(
        [{'vendor': '自定义', 'model': 'MY-1', 'd': 100, 'p': 1000,
          's': 1.0, 'sp': 1.0}],
        ensure_ascii=False, indent=1)
    p.write_text(custom, encoding='utf-8')
    monkeypatch.setattr(tb, '_OLD_SEED_SHA256', 'deadbeef')

    assert tb.migrate_seed_if_unmodified(str(p)) is False
    assert 'MY-1' in p.read_text(encoding='utf-8')


def test_missing_file_is_noop(tmp_path):
    assert tb.migrate_seed_if_unmodified(str(tmp_path / 'nope.json')) is False

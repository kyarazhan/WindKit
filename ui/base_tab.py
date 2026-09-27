"""模块页基类：标题 + 说明 + 内容区 + 参数记忆 + 实时计算。

插件协议：
- 每个插件文件声明 ``TITLE`` 类属性（二级菜单文字）；
- 文件尾部 ``TAB = XxxTab`` 显式暴露入口类；
- 分组归属由所在目录（plugins/<nn>_<分组名>/）决定，
  框架装载后通过 :meth:`set_group` 注入面包屑，插件自身不写死分组。

Phase 1 增强：
- :meth:`add_input` 创建带参数记忆的输入行，值变化自动保存并触发计算；
- :meth:`compute` 子类覆写的计算方法，输入变化时自动调用；
- :meth:`save_state` / :meth:`restore_state` 参数持久化。
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.tool_params import load_params, save_params


class ModuleTab(QWidget):
    TITLE = ''

    def __init__(self, title: str = '', hint: str = ''):
        super().__init__()
        self._group = ''
        self._inputs = {}
        self._param_key = title or self.TITLE
        self._calc_timer = QTimer(self)
        self._calc_timer.setSingleShot(True)
        self._calc_timer.setInterval(300)
        self._calc_timer.timeout.connect(self._do_compute)

        self._crumb = QLabel('')
        self._crumb.setProperty('fieldLabel', True)
        self._crumb.setStyleSheet('color:#8a9199; font-size:11px;')
        t = QLabel(title or self.TITLE)
        t.setObjectName('moduleTitle')
        self.root_lay = QVBoxLayout(self)
        self.root_lay.setContentsMargins(24, 18, 24, 18)
        self.root_lay.setSpacing(10)
        self.root_lay.addWidget(self._crumb)
        self.root_lay.addWidget(t)
        if hint:
            h = QLabel(hint)
            h.setObjectName('moduleHint')
            self.root_lay.addWidget(h)

    def set_group(self, group: str):
        self._group = group
        self._crumb.setText(group)

    @property
    def group(self) -> str:
        return self._group

    def add_input(self, key: str, label: str, default='', suffix=None):
        """创建输入行并注册参数记忆。

        返回 (widget, QLineEdit)；输入变化时自动保存参数并触发 compute()。
        """
        from ui.widgets import InputRow
        saved = load_params(self._param_key)
        val = saved.get(key, default)
        w, edit = InputRow.line(self, label, val, suffix=suffix)
        self._inputs[key] = edit
        edit.textChanged.connect(lambda: self._on_input_changed())
        return w, edit

    def get_input(self, key: str) -> str:
        """获取指定输入框的当前文本值。"""
        edit = self._inputs.get(key)
        return edit.text() if edit else ''

    def get_float(self, key: str, default: float = 0.0) -> float:
        """获取指定输入框的浮点值，无效时返回 default。"""
        try:
            return float(self.get_input(key))
        except (ValueError, TypeError):
            return default

    def _on_input_changed(self):
        self._save_current_params()
        self._calc_timer.start()

    def _save_current_params(self):
        params = {key: edit.text() for key, edit in self._inputs.items()}
        save_params(self._param_key, params)

    def _do_compute(self):
        try:
            self.compute()
        except Exception:
            # 不能让单次计算异常打断输入交互，但必须在控制台可见，
            # 否则插件表现为「页面无响应无报错」（历史上吞掉过真实 bug）
            import traceback
            traceback.print_exc()

    def compute(self):
        """子类覆写：执行计算并更新结果展示。输入变化时自动调用。"""
        pass

    def trigger_compute(self):
        """手动触发一次计算（如导入数据后调用）。"""
        self._calc_timer.start()

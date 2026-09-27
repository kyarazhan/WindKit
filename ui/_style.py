"""集中浅色 QSS：右键菜单 / 文件对话框。

PySide6 在 Windows 11 暗色主题下，会让 ``QMenu``、``QFileDialog`` 等部分
native 控件采用系统暗色，与主程序浅色主题不协调。这里集中定义强制浅色
样式，被 :mod:`ui.tool_item`、:mod:`ui.toolbox_window`、
:mod:`ui._dialogs` 共同使用。
"""

# 右键菜单浅色（白底深字、hover 浅蓝）
MENU_QSS = """
    QMenu {
        background: #ffffff;
        color: #4a5560;
        border: 1px solid #d8dce0;
        padding: 4px 0;
    }
    QMenu::item {
        padding: 5px 26px 5px 14px;
        font-size: 12px;
        color: #4a5560;
        background: transparent;
    }
    QMenu::item:selected {
        background: #e6f1fb;
        color: #185fa5;
    }
    QMenu::item:disabled {
        color: #b0b6bf;
    }
    QMenu::separator {
        height: 1px;
        background: #e4e8ec;
        margin: 4px 8px;
    }
"""

# 文件对话框浅色（背景灰、列表白、按钮蓝）
FILE_DIALOG_QSS = """
    QFileDialog {
        background: #eef1f5;
        color: #1f3b4d;
    }
    QFileDialog QLabel, QFileDialog QLineEdit, QFileDialog QTreeView,
    QFileDialog QListView, QFileDialog QComboBox {
        background: #ffffff;
        color: #1f3b4d;
    }
    QFileDialog QPushButton {
        background: #185fa5;
        color: #ffffff;
        border: none;
        border-radius: 3px;
        padding: 5px 16px;
    }
    QFileDialog QPushButton:hover { background: #2a6fb5; }
    QFileDialog QPushButton[text="Cancel"],
    QFileDialog QPushButton[text="取消"] {
        background: transparent;
        color: #185fa5;
        border: 1px solid #185fa5;
    }
"""

# 弹窗浅色（QDialog 背景灰、QLineEdit/QPlainTextEdit 白）
DIALOG_QSS = """
    QDialog { background: #eef1f5; }
    QLabel { color: #1f3b4d; font-size: 12px; }
    QLineEdit, QPlainTextEdit {
        background: #ffffff;
        color: #1f3b4d;
        font-size: 13px;
        border: 1px solid #d8dce0;
        border-radius: 3px;
        padding: 4px 6px;
        selection-background-color: #cfe2f5;
    }
    QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid #185fa5; }
    QPushButton {
        background: #185fa5;
        color: #ffffff;
        border: none;
        border-radius: 3px;
        padding: 6px 18px;
        font-size: 13px;
        min-width: 72px;
    }
    QPushButton:hover { background: #2a6fb5; }
    QPushButton#secondaryBtn {
        background: transparent;
        color: #185fa5;
        border: 1px solid #185fa5;
    }
    QPushButton#secondaryBtn:hover { background: #e6f1fb; }
"""

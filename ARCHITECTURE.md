# WindKit 软件架构文档

> 更新：2026-09-27 · 本轮重组（目录拍平、无用清除、更新器换代）后的新基线
> 路线图见 [REFACTOR_PLAN.md](REFACTOR_PLAN.md)

## 1. 项目概览

**WindKit** 是风资源分析师的工程小工具箱（快速计算 / 风能分析 / 机组信息 /
载荷工况 / 坐标转换 / M1 拆分），PySide6 单机桌面应用，插件式架构：
功能页置于 `plugins/` 目录，启动时自动扫描装载，新工具放入对应分组目录即可，
框架零改动。

| 顶层 | 职责 |
|---|---|
| `windkit.py` | 唯一入口（更新交接 + QApplication 装配 + 强制浅色调色板 + QSS） |
| `core/` | 纯计算与数据层，**无 UI 依赖**（numpy/pandas/openpyxl/stdlib） |
| `ui/` | 主窗口 + 控件层（调度器、卡片、表格、覆盖层/参数持久化、UpdateMixin） |
| `plugins/` | 6 个分类目录、15 个原生工具页（协议见 §3） |
| `updater/` | 独立更新器 updater.exe 源码（与主程序进程解耦，与 WindAnaly 同机制） |
| `tools/` | 发布流水线（release.py）与更新器端到端验证脚本 |
| `tests/` | 44 项 pytest 回归（core 公式 Excel 锚点 + UI 布局/调度/持久化 + 更新器 10 项） |
| `data/` | 用户数据：turbines.json（更新永不覆盖）+ samples/（只读样例） |
| `release/` | 本地发布归档（每版本：完整包 / 增量包 / versions.json / 源码归档） |

## 2. 目录结构

```
WindKit/
├── windkit.py            # 入口：python windkit.py（冻结后 = WindKit.exe）
├── build.py              # PyInstaller：主程序 onedir + updater.exe
├── core/                 # 13 文件 847 行
│   ├── paths.py          #   路径解析（冻结感知）：app_dir/resource_path/user_data_dir
│   ├── version.py        #   VERSION / APP_NAME 唯一定义（发版只改这里）
│   ├── turbine.py        #   TurbineDB 机型库（data/turbines.json，首运行种子初始化）
│   ├── boundary_centroid.py    # 界址点质心 + 正八边形 + Excel 导入导出
│   └── air_density shear wind_power distributions extreme_wind
│       long_term guarantee m1_split
├── ui/                   # 11 文件 1,959 行
│   ├── toolbox_window.py #   主窗口：分类 Tab + 卡片网格 + 搜索 + 帮助菜单
│   ├── tool_dispatcher.py#   插件扫描/装载/窗口复用调度
│   ├── base_tab.py       #   ModuleTab 基类：参数记忆 + 300ms 防抖实时计算
│   ├── tool_item.py      #   卡片控件 + 自建 Tooltip 浮层（Win11 暗色绕障）
│   ├── card_overrides.py #   卡片/分类改名/图标/排序覆盖层（AppConfigLocation）
│   ├── tool_params.py    #   工具输入参数记忆（同一配置根 tool_params.json）
│   ├── update_tools.py   #   UpdateMixin：拉起 updater.exe + 状态栏提示
│   ├── widgets.py _dialogs.py _style.py theme.qss
├── plugins/              # 6 分类 15 插件（01_快速计算 … 06_M1拆分）
├── updater/              # 独立更新器（tkinter，纯标准库）
│   ├── updater_main.py   #   界面/下载/安装/备份/恢复/updater.exe 自替换
│   ├── feed.py           #   多源版本索引（versions.json / GitHub Releases / UNC）
│   ├── config.py         #   sources.json 加载 + app_dir
│   ├── version.py        #   版本比较
│   └── sources.json      #   更新源配置（发版前可改，无需动代码）
├── tools/                # release.py 发版流水线 + verify_updater_* 端到端验证
├── release/              # 本地发布归档（<版本>/ 完整包·增量包·索引·源码归档）
├── data/  tests/  icon.png  icon.ico  requirements*.txt  .gitignore
```

## 3. 插件协议与调度

- **协议**：每个插件声明 `ModuleTab` 子类（`TITLE` 类属性 + 可选 `HINT`），
  文件尾部 `TAB = XxxTab` 显式暴露入口；文件名数字前缀（`20_`）仅用于排序；
  `_` 开头文件/目录不装载。
- **发现**：`ToolDispatcher.discover(resource_path('plugins'))` 按目录分组、
  前缀排序；单插件装载失败不崩主程序，状态栏提示「N 个插件装载失败」。
- **调度**：`open_tool(name)` 按名复用窗口（防孤儿泄漏），TAB 实例包装为
  QDialog 弹出；`close_all()` 随主窗口关闭联动。
- **定制**：卡片/分类支持右键改名/图标/简介/排序，持久化于
  card_overrides.json；分组显示名映射（风资源分析→风能分析等）在
  `toolbox_window._DEFAULT_GROUP_DISPLAY`。

## 4. 核心数据流

```
python windkit.py
  ├─ .update/pending.json？→ 交接 updater.exe（或 bat 兜底）后退出
  └─ QApplication（Fusion + 浅色调色板 + theme.qss）
        └─ ToolboxWindow(UpdateMixin)
              ├─ _setup_update()：后台拉起 updater.exe 静默查询新版
              └─ ToolDispatcher.discover() → 顶栏分类 Tab + 卡片网格
插件页：输入（参数自动记忆）→ core/*.py 纯函数 → DataTable/MetricCard 展示
```

## 5. 自动更新（与 WindAnaly 同机制）

updater.exe 三种启动方式（均已端到端验证）：

| 方式 | 触发 | 行为 |
|---|---|---|
| 后台伴随 | 主程序启动自动拉起（`--task`） | 无窗查询更新源，发现新版写 `.update/available.json` → 主程序状态栏提示 |
| 前台窗口 | 「帮助 → 检查更新」 / **双击 updater.exe 独立运行** | 在线更新（检查→选版本→下载安装）或本地更新（选 zip 校验安装）；独立运行时自探测安装目录/版本/更新源，主程序损坏也可自救 |
| 兼容交接 | `--config .update/pending.json`（主程序入口交接） | 应用已下载好的更新包后重启主程序 |

- 安装流程：sha256 校验 → 关主程序（优雅→等待→强制）→ `data/` 自动备份
  （pre_update_*.zip，保留最近 N 份）→ 替换（`data/` 用户数据永不覆盖，
  updater.exe 自替换）→ 重启 → 可从备份恢复；
- 更新源 `updater/sources.json` 可配 GitHub Releases / HTTP / UNC；
- 版本号只改 `core/version.py`；`data/app_version.txt` 由发布流水线写入，
  供更新器识别已装版本。发版 SOP 见 RELEASE.md。

## 6. 开发与打包

```
.venv\Scripts\python -m pytest tests -q     # 回归（44 项，offscreen 可跑）
python windkit.py                           # 开发运行（系统 Python 或 .venv）
python tools/release.py <版本> --notes "说明"   # 发版一条龙 → release/<版本>/
python tools/release.py <版本> --skip-build     # dist 已是新版时
python -X utf8 tools/verify_updater_install.py  # 更新器本地安装端到端
python -X utf8 tools/verify_updater_gui.py      # 更新器独立运行+在线 GUI 端到端
```

环境约定：**开发/测试**用 `.venv`（Python 3.13 + requirements.txt）；
**打包/发版/更新器验证**用系统 Python 3.14（需 tkinter，另装
requirements-build.txt）。路径（安装根/用户数据/只读资源）统一走
`core/paths.py`，禁止各模块自行 `__file__` 推导。

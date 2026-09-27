# WindKit · 风资源工程小工具箱

风资源分析师的桌面工具箱（PySide6）：快速计算、风能分析、机组信息、
载荷工况、坐标转换、M1 拆分。插件式架构——新工具放进 `plugins/` 对应
分组目录即可，框架零改动。

## 功能一览（15 个工具）

| 分类 | 工具 |
|---|---|
| 快速计算 | 空气密度 · 风速折算 · 风切变 |
| 风能分析 | 湍流曲线 · 长期订正 · 50 年一遇最大风速 · 风速日·月分布 |
| 机组信息 | 机型库 · 功率曲线修正 · 发电量速算 · 保发电量敏感度 |
| 载荷工况 | 载荷比对 · M1 拆分 |
| 坐标转换 | 界址点 ⇄ 中心（含 Excel 导入导出） |
| M1拆分 | M1 拆分（三表联动版） |

卡片/分类支持右键改名、换图标、调排序（持久化）；工具输入参数自动记忆。

## 添加新工具（三步，框架零改动）

1. 在 `plugins/<分组目录>/` 下新建 `NN_工具名.py`（NN 决定同组内排序）；
2. 写一个 `ModuleTab` 子类：`TITLE` 类属性 + 界面 + `compute()` 计算；
   纯计算逻辑放 `core/`（便于测试）；
3. 文件尾部 `TAB = 你的类` 暴露入口。

启动即自动发现装载；样例数据放 `data/samples/`，用
`core.paths.resource_path` 引用（开发/打包通用）。参考
`plugins/01_快速计算/10_air_density.py`（最小范式）。

## 运行

```
python windkit.py                 # 开发运行
python -m pytest tests -q         # 回归（34 项）
```

依赖见 `requirements.txt`（Python ≥3.13，建议用 `.venv`）。

## 打包与自动更新

```
pip install -r requirements.txt -r requirements-build.txt   # 打包用系统 Python（需 tkinter）
python tools/release.py <版本> --notes "说明"               # 发版一条龙 → release/<版本>/
```

独立更新器 `updater.exe`（与 WindAnaly 同机制）三种方式均可用：
- **独立双击运行**：自探测目录/版本/更新源，「在线更新」（检查 → 选版本 →
  下载安装）与「本地更新」（选 zip 校验安装）都支持，主程序损坏也可自救；
- **主程序内**：启动后台静默查新（状态栏提示），「帮助 → 检查更新」前台安装；
- **入口交接**：主程序发现待更新包时自动移交更新器完成替换并重启。

安全机制：sha256 校验、全量包/增量链、安装前自动备份用户数据
（`data/backups/`，可从备份恢复）、`data/turbines.json` 永不覆盖。
更新源配置在 `updater/sources.json`（GitHub Releases / HTTP / UNC 均可）。

## 文档

- [ARCHITECTURE.md](ARCHITECTURE.md) —— 架构与目录说明
- [REFACTOR_PLAN.md](REFACTOR_PLAN.md) —— 重构/优化/迭代规划书（滚动更新）
- [RELEASE.md](RELEASE.md) —— 发版 SOP 与历史发布记录

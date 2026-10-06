# WindKit 重构、优化与迭代规划书

> 版本：v1.0 · 2026-09-27（本轮重组完成后建立的新基线）
> 基于对全量代码的审计（41 个 .py / 约 7,300 行）与本轮「目录拍平 + 无用清除 +
> 更新器换代 + 打包落地」后的现状
> 配套文档：[ARCHITECTURE.md](ARCHITECTURE.md)（新架构说明）
> 体例与机制对齐姊妹项目 **WindAnaly**（同作者、同更新器、同发版 SOP）

---

## 0. 本轮已完成的重组（2026-09-27）

经过多轮迭代，代码与架构已支离破碎（嵌套包布局、中英文混杂、死代码堆积、
有 QSS 残留而无更新器、requirements 声称有 build.py 而实际不存在）。本轮按
WindAnaly 的成熟范式完成重组，作为后续迭代的新基线：

| 事项 | 结果 |
|---|---|
| 目录拍平 | `windkit/` 包提升到根目录：`core/`（纯计算层）、`ui/`（控件层）、`windkit.py`（唯一入口）；`theme.qss` 归位 `ui/`。布局与 WindAnaly 完全一致 |
| 入口统一 | `main.py` + `windkit/app.py`（QApplication 组装）合并为唯一入口 `windkit.py`（更新交接 + 浅色调色板 + QSS + 主窗口） |
| 无用清除 | 删除：`plugins/05_坐标转换/_boundary_centroid.py`（840 行 tkinter 遗产，算法早已移植进 core）、`ui/external_tab.py`（约 120 行外部工具机制，EXTERmal_CMD 全项目零使用，调度器内 ExternalToolWindow 一并移除）、`widgets.DropArea`、`base_tab.add_input` 死分支、`tool_params.clear_params`、`card_overrides` 旧 API wrapper、`_style.TOOLTIP_QSS`（无效样式）、theme.qss 死选择器（updateBtn/primaryItem/subBar/QMenuBar 等 4 组，约 90 行）、`docs/`（无引用截图）、`.workbuddy/`（过时 AI 记忆）、全部 `__pycache__` |
| 样例数据归位 | `_src/` → `data/samples/`；5 个插件 + 测试的引用改走 `core.paths.resource_path`（开发/冻结双模式可用） |
| 更新器换代 | 移植 WindAnaly 的**独立 updater.exe 机制**（此前 WindKit 只有 theme.qss 里一个 updateBtn 样式残留，无任何更新代码），详见 §4 |
| 打包落地 | 新增 `build.py`（主程序 onedir + updater.exe + data/app_version.txt）；资源（plugins/、data/samples、turbines.json、theme.qss、icon）统一随包分发到 `_internal/`，运行期经 `core/paths.py` 定位；pyinstaller 从 requirements.txt 拆到 requirements-build.txt |
| 路径统一 | 新增 `core/paths.py`（app_dir / resource_base / resource_path / user_data_dir），调度器插件根、图标、样例数据、机型库全部接入——各处自行 `__file__` 推导的写法清零 |
| 机型库可更新安全 | `TurbineDB` 落点改为 `data/turbines.json`（用户数据，更新永不覆盖），首运行从随包种子库复制 |
| 小修 | 调度器插件模块名改用 md5 摘要（原 `abs(hash())` 受 PYTHONHASHSEED 影响）；`_do_compute` 异常改为 traceback 打印（原静默吞掉，插件坏掉表现为「无响应无报错」）；`_safe_int` 去重；tool_params 与 card_overrides 统一用 QStandardPaths 配置根 |
| 验证 | pytest 34 项全绿；离屏 GUI 冒烟通过；`python build.py` 全流程通过；发布物冒烟：WindKit.exe 存活、UpdateMixin 成功拉起 updater.exe（task.json 正确）、updater.exe 后台模式对坏源优雅退出并落日志 |
| 回滚保障 | 重构前全量备份：`Project/WindKit_pre_refactor_20260927.zip`（1.06 MB） |

### 0.1 v1.0.0 发布记录（2026-09-27，第一版交付）

| 事项 | 结果 |
|---|---|
| 发布流水线 | `tools/release.py <版本> --notes "说明"`：版本校验 → build → 冻结 exe 冒烟 → 完整包 → 基线重演 + 文件级 diff 增量包（有上一版时）→ versions.json → 源码归档，一条龙 |
| v1.0.0 产物 | `release/1.0.0/`：WindKit-1.0.0.zip（81.9 MB，sha256 `4782973c…bc18fde`）+ versions.json + 源码归档（1.1 MB）；SOP 见 [RELEASE.md](RELEASE.md) |
| 更新器回归 | 新增 `tests/test_updater.py` 10 项（版本比较/本地与在线索引解析/增量链规划/提取与用户数据保护/备份恢复/独立任务构造），34 → **44 项** |
| 更新器三模式实证 | ①独立双击（无参数）：`tools/verify_updater_gui.py` 走通「在线检查→版本列表→下载安装→完成」全 GUI 流程（mainloop + after 驱动）；②本地包安装：`tools/verify_updater_install.py` 用真实 updater.exe --config 应用 1.0.1 包，8 项断言全过；③后台伴随查询：发布物冒烟已验 |
| 更新携带新功能验证 | E2E 中更新包同时完成：既有插件修订 + 全新插件分类落地 + 版本文件更新 + 用户机型库保留 —— 证实「后续陆续加功能」可通过更新包发布 |
| 构建环境守卫 | build.py 增加 tkinter 预检（缺 tkinter 的精简 Python 给明确报错）；发版固定用系统 Python 3.14 |

### 0.2 v1.0.1 发布记录（2026-09-27，修复打包版插件装载失败）

**用户报告**：打包版状态栏「就绪（13 个插件装载失败，已跳过）」。

| 项 | 结果 |
|---|---|
| 根因 | PyInstaller 只随主入口静态分析收模块；仅插件运行时才 import 的业务子模块（core.air_density / shear / turbine / wind_power / distributions / extreme_wind / long_term / guarantee / m1_split / boundary_centroid）没进包 → 插件 `ModuleNotFoundError`。13 个失败 / 2 个成功（湍流曲线、载荷比对恰好不依赖缺失模块），与报告数字完全吻合 |
| 修复 | `build.py._local_submodules()`：core/ui 全部子模块显式列入 hidden-import；`tests/test_build.py` 2 项防回归（关键模块必须在清单、输出确定性） |
| 可观测性 | 插件装载结果每次启动整写 `data/plugin_load_errors.log`（成功数/失败数 + 失败明细），状态栏显示摘要——打包问题不再只能靠计数猜 |
| 流水线加固 | `release.py` 三处：①基线重演只收「终点 < 本版本」的补丁（重跑同版本不再退化出空补丁）；②源码归档排除一切 `_` 开头目录与任意层级 build/dist（曾把安装备份打进归档 81MB）；③exe 冒烟后清理 dist/.update 再打包 |
| 产物 | `release/1.0.1/`：WindKit-1.0.1.zip（82.0 MB）+ 1.0.0-1.0.1-patch.zip（19 文件 21.8 MB，含一次性运行时基线切换）+ versions.json + 源码归档（1.1 MB） |
| 端到端 | 备份的 1.0.0 安装 + 真实补丁 → 真实 updater.exe 应用 → v1.0.1 启动存活、**装载成功 15 / 失败 0**、备份与 pending 清理全过 |
| 教训入库 | 「开发模式全绿 ≠ 打包模式可用」：插件动态 import 的模块必须显式入包（D9 之后做构建缓存/增量瘦身时同样要守这条），新增 test_build 固化 |
| 上传 GitHub | 仓库 `kyarazhan/WindKit`（便携 git 推送，merge 掉网页生成的 README）；Release v1.0.1 资产已上传（全量 82MB + 增量 21.8MB + versions.json，`tools/publish_release.py` 凭据走 credential manager，可安全重跑）；**真实源在线验证通过**：模拟 v1.0.0 后台查询 13s 发现 v1.0.1 并写 available.json |

### 0.3 发版后遗留（下版前处理）

- v1.0.1 补丁 21.8MB 中运行时占绝对大头——D9 构建缓存落地后回落到业务真实变更；
- v1.0.0 的 GitHub Release 未发布（其全量包含插件 bug，已被 1.0.1 取代，无需补发）。

### 0.4 v1.0.2 发布记录（2026-10-06，功能调整）

| 项 | 结果 |
|---|---|
| 工具下线 | 移除风能分析下的湍流曲线 / 长期订正 / 50 年一遇最大风速（D1 湍流插值 bug 随下线关闭）；风能分析仅存风速日·月分布 |
| M1 合并 | 06 组三表联动版并入载荷工况（04/20_m1_split.py 覆盖旧简版），06 组删除（D4 决策落地：保留三表联动版；钳位双语义仍在 core 待 S2 统一为 UI 选项） |
| 机型库精简 | 随包种子裁为金风 GWH221-6250 / GWH221-6700；新增 `ensure_seed_migrated()` 启动迁移（sha256 守卫：内容与旧 54 机型种子逐字节一致——即用户从未改过库——才替换为两机型，改过的库一律不动） |
| 机制修复 ① | 更新器 `_PRESERVE` 原按「路径中含 data 目录」匹配，把 `_internal/data/`（随包只读资源）也挡在更新外，种子永远发不出去；改为仅保护安装根顶层 `data/`。⚠️ WindAnaly 同源同病，待同步修复 |
| 机制修复 ② | release.py 补丁 diff 同样只排除顶层 `data/`（此前嵌套 `_internal/data/` 不进补丁，与 ① 叠加导致种子更新完全失效，本次 E2E 抓出） |
| 下线清理 | 调度器新增 `cleanup_legacy_plugins()`：每次装载前删除下线插件残留文件与空分组（更新包只覆盖不删除，删除类变更必须显式清理；幂等，含回归测试） |
| 测试 | 46 → **50**（种子迁移 3 + 下线清理 1） |
| 端到端 | 真实 1.0.1 发布包为基座 + 真实补丁，双路径 8 项全过：旧更新器路径（残留清理 / 启动迁移 / 11/11 装载 / 备份）、新更新器路径（随包种子正确刷新） |
| 发布物 | full 82.0 MB / patch 21.7 MB（9 文件）/ versions.json / 源码归档 2.3 MB；GitHub Release v1.0.2 已上线 |
| 教训入库 | 「删除类变更」在覆盖式更新体系里必须三件套：应用侧清理（cleanup_legacy_plugins）+ 精确到顶层目录的资源保护 + 升级迁移（数据文件用 sha 守卫区分「没动过」与「用户改过」） |

---

## 1. 现状架构

### 1.1 分层与规模（本轮重组后）

```
windkit.py            唯一入口（更新交接 + QApplication 装配，约 180 行）
├── core/             13 文件 847 行 —— 纯计算与数据层，无 UI 依赖（仅 openpyxl）
│   ├── paths.py      #   路径解析（冻结感知）★新增
│   ├── version.py    #   VERSION / APP_NAME 唯一定义 ★新增
│   ├── turbine.py    #   TurbineDB：机型库 JSON 持久化（落用户数据目录）
│   ├── boundary_centroid.py  # 界址点质心 + 正八边形 + Excel 导入导出（299 行）
│   └── air_density · shear · wind_power · distributions · extreme_wind
│       long_term · guarantee · m1_split（两套语义并存，见 P4）
├── ui/               11 文件 1,959 行 —— 控件层
│   ├── toolbox_window.py     # 主窗口：分类 Tab + 卡片网格 + 搜索（含 UpdateMixin）
│   ├── tool_dispatcher.py    # 插件扫描/装载/窗口调度（纯原生 TAB 协议）
│   ├── base_tab.py           # ModuleTab 基类：参数记忆 + 防抖实时计算
│   ├── tool_item.py          # 卡片控件 + 自建 Tooltip 浮层（Win11 暗色绕障）
│   ├── card_overrides.py · tool_params.py    # 覆盖层/参数持久化（同一配置根）
│   ├── update_tools.py       # ★新增 UpdateMixin：拉起 updater.exe + 状态栏提示
│   ├── widgets.py · _dialogs.py · _style.py · theme.qss
├── plugins/          6 分类 15 插件 1,836 行（协议：ModuleTab 子类 + TAB= 入口）
├── updater/          5 文件 1,674 行 —— 独立更新器源码（与 WindAnaly 同源同机制）
├── build.py          PyInstaller：主程序 onedir + updater.exe + 版本溯源
├── data/             turbines.json（用户数据）· samples/（样例，只读资源）
└── tests/            34 项 pytest（core 11 + UI 23）
```

### 1.2 核心数据流

```
启动 windkit.py
  ├─ .update/pending.json 存在？→ 交接 updater.exe（或 bat 兜底）后退出
  └─ QApplication（Fusion + 强制浅色调色板 + ui/theme.qss）
        └─ ToolboxWindow(UpdateMixin)
              ├─ _setup_update()：后台拉起 updater.exe 静默查询
              └─ ToolDispatcher.discover(resource_path('plugins'))
                    每个插件：TAB 类 → ToolInfo → 卡片 → open_tool 复用弹窗
插件内部：core/*.py 纯函数 → widgets.DataTable/MetricCard 展示
```

### 1.3 与 WindAnaly 的关系

同一作者的两个独立软件，现已统一：目录布局、入口模式、更新器（updater/ 五
文件同源）、发版 SOP、文档体例（ARCHITECTURE/REFACTOR_PLAN/README）。
WindKit 保持「工具箱」定位（轻量插件页），WindAnaly 保持「测风塔数据分析」
定位（数据集/项目/报告），不合并运行时。

---

## 2. 主要问题诊断（按影响排序）

**P1 湍流曲线 15 m/s 插值崩溃。**
`plugins/02_风资源分析/10_turbulence.py`（原 60-69 行）：输入 bin 不覆盖
15 m/s 时 `max()`/`min()` 抛 ValueError；叠加 `_do_compute` 此前的静默吞错，
用户看到的是「页面无响应无报错」。本轮已让异常在控制台可见，插值本身待修
（需边界保护：低于/高于 15 时取最近 bin 或外推提示）。

**P2 机型库除零崩溃。**
`plugins/03_机型与电量/10_turbine_db.py` + `core/turbine.py add()/update()`：
容量输入非数字时 `get_float` 返回 0.0 → `s / p` ZeroDivisionError 未捕获。
需在 core 层加 `p > 0` 保护（或 UI 层输入校验）。

**P3 载荷比对是假工具。**
`plugins/04_载荷与工况/10_load_compare.py` 硬编码「新值 = 旧值 × 1.05」。
对用户有误导性：要么实现真比对（两组载荷表逐工况差异率），要么先下架。

**P4 双 M1 拆分工具并存且算法语义不一致。**
`04_载荷与工况/20_m1_split.py`（「M1 拆分」，CSV 简版）与
`06_M1拆分/10_m1_split.py`（「M1拆分」，三表联动版）名字仅差一个空格；
`core/m1_split.py` 里对应的 `m1_split()`（全量钳位）与 `clamp_ti()`
（连续 3 点 <0.1 才钳位）是两套「优化」语义。需合并为一个工具（保留三表
联动版），并在 UI 上明确钳位策略选项。

**P5 打包产物不可复现 → 增量补丁必然巨大。**
`build.py` 标准 onedir：每次构建 WindKit.exe / base_library.zip 字节全变，
未来做文件级 diff 增量包时，真实变更会被运行时噪声淹没。WindAnaly 已用
「模块化分发（boot 桩 + app/*.pyc + _internal 运行时）+ 输入指纹构建缓存」
解决（其补丁从 21.7MB 降到 11.7KB），方案可直接移植。

**P6 样式三处割裂。**
theme.qss（已清死选择器）、toolbox_window.py 内联 3 个 QSS 常量、
_style.py 常量 + 控件 setStyleSheet 内联并存。改主题要动 3+ 处。
建议收敛为「theme.qss 全局 + _style.py 强制浅色专用」两层。

**P7 中英文混杂与命名不一致。**
UI 文案中英混排（'Mean TI'、'σ1[B]/Vhub' 与 'σ1/Vhub [A]' 同义异形、
'V50 标况 1.225'）；目录名「06_M1拆分」中英混合；`tests/test_ui.py` 的
`jie` 拼音变量名。工具定位是国内风资源工程师，中文为主是对的，但要一致：
术语表（TI/V50/Cp/A/k 等约定俗成的英文缩写保留，其余中文）+ 列名格式统一。

**P8 测试与文档漂移。**
测试注释曾写「14 个工具」（实际 15，本轮已修）；.workbuddy 记忆与代码脱节
（已随本轮删除，以本规划书 + ARCHITECTURE.md 为准）；core docstring 提到的
外部项目名（WindVault/WindRefine/WindMatrix）已清理。测试共 34 项，覆盖
core 公式锚点（对齐源 Excel，价值极高）+ UI 布局/调度/持久化回归，但
插件内部计算无直接断言（bug P1/P2 正是从这里漏掉的）。

**P9 无版本管理、无 CI。**
项目不在 git 中（本轮已补 .gitignore，可直接 `git init`）；回归靠本地手工
pytest。WindAnaly 已有 GitHub Actions CI（windows-latest + offscreen pytest）
可照搬。

---

## 3. 技术债清单

| 编号 | 债务 | 位置 | 建议批次 |
|---|---|---|---|
| D1 | ~~湍流 15 m/s 插值无边界保护~~（工具已随 1.0.2 下线，关闭） | — | 已关闭 |
| D2 | 机型库 p=0 除零（P2） | core/turbine.py、plugins/03/10_turbine_db.py | S1 |
| D3 | 载荷比对假工具（P3） | plugins/04/10_load_compare.py | S1（实现或下架） |
| D4 | ~~双 M1 工具 + 双钳位语义~~（1.0.2 已合并为三表联动版；core 双钳位函数保留，待 S2 做 UI 选项或删函数） | core/m1_split.py | S2 |
| D5 | ~~06_M1拆分 参数记忆键 hack~~（06 组已删除，随 1.0.2 关闭；04/20_m1_split.py 内同款 `title=' '` hack 仍在） | plugins/04/20_m1_split.py | S2（顺手改） |
| D6 | 「打开机型库页面即写盘」（refresh 里顺带 save） | plugins/03/10_turbine_db.py | S2 |
| D7 | 样式三处割裂（P6） | ui/theme.qss、toolbox_window.py、各控件 | S3 |
| D8 | 界址点插件 HINT 文案写两遍；`json.load(open(...))` 文件句柄未关闭等卫生项 | plugins/05、多处 | S3 随手清 |
| D9 | 增量补丁噪声（P5） | build.py | S4 |
| D10 | UI 文案术语不统一（P7） | plugins/ 各列名/MetricCard | S3 |
| D11 | 插件计算无直接测试（P8） | tests/ | S1 起（修 D1-D3 时同步补） |
| D12 | `10_turbulence` 等 5 处样例 JSON 依赖：离线首次打开会 traceback（已可见不静默），可给「加载示例」按钮反馈 | plugins/ | S3 |

---

## 4. 自动更新机制（本轮移植，发版 SOP）

与 WindAnaly 完全同机制：**独立更新器进程 + 多源版本索引 + 全量/增量包 +
更新前自动备份**。

### 4.1 组成

| 组件 | 位置 | 职责 |
|---|---|---|
| updater.exe | `updater/updater_main.py` → PyInstaller onefile | 独立进程完成查源/选版本/下载(sha256 校验)/关主程序/备份/替换/自替换/重启；tkinter UI，纯标准库，可脱离主程序双击自救 |
| 版本索引 | `updater/feed.py` | 按源拉取 versions.json（多版本+全量/增量+changelog）；支持 GitHub Releases 网页解析、HTTP、UNC/本地三种源 |
| 更新源配置 | `updater/sources.json` | 当前指向 `kyarazhan/WindKit`；发版前确认仓库真实存在，或改为内网源（改文件即可，无需动代码） |
| 主程序侧 | `ui/update_tools.py`（UpdateMixin） | 启动后台拉起 updater.exe 静默查询（开发模式无 updater.exe 时静默跳过）；发现新版仅状态栏提示；「帮助 → 检查更新」前台拉起 |
| 入口交接 | `windkit.py` | 启动发现 `.update/pending.json` → 交给 updater.exe（无更新器时 bat 兜底，备份 turbines.json） |

### 4.2 用户数据保护

- `data/turbines.json`（机型库）更新时**永不覆盖**；`data/app_version.txt`
  随更新写入新版本号（更新器识别已装版本的依据）；
- 每次安装前自动备份 `data/` → `data/backups/pre_update_<时间戳>.zip`
  （保留最近 N 份，缺省 10）；更新器内可「从备份恢复」。

### 4.3 发版 SOP

一句话：改 `core/version.py` → 回归全绿 → `python tools/release.py <版本>
--notes "说明"` → 上传 `release/<版本>/` 产物到更新源（versions.json 必传）。
逐步操作、产物清单与发版后验证清单见 **[RELEASE.md](RELEASE.md)**。

更新包内容约定：

   ```json
   {"versions": [{
     "version": "1.0.1", "date": "2026-10-15",
     "changelog": "……",
     "full":  {"url": "WindKit-1.0.1.zip", "sha256": "..."},
     "patch": {"base": "1.0.0", "url": "1.0.0-1.0.1-patch.zip", "sha256": "..."}
   }]}
   ```
   （全量/增量均可缺省其一，更新器自动规划；增量包命名 `<旧>-<新>-patch.zip`
   由 release.py 自动 diff 产出）
5. ~~⚠️ 首次发版前必须确认 `updater/sources.json` 指向真实存在且有
   Release 的仓库~~（✅ 已解决：`kyarazhan/WindKit` Release v1.0.1 已上线，
   真实源在线查询验证通过）。

---

## 5. 迭代路线图

原则：**每批结束都有可发布版本**；core 层改动必带测试；UI 改动以
「行为不变 + 34 项回归全绿」为准绳；修 bug 与重构不混批。

### S1 · 止血：功能性 bug 清零（0.5~1 周，高风险优先）

1. **D1** 湍流 15 m/s 插值边界保护（低于取最近 bin、高于外推并提示）；
   **D11** 为湍流/机型库/发电量补插件级计算测试（构造 Tab 后 set 输入断言结果卡）；
2. **D2** 机型库 `p>0` 保护 + 非法输入 UI 提示；
3. **D3** 载荷比对：实现真比对（两组 (工况, 数值) 表的逐行差异率），或先下架；
4. `git init` + 提交新基线（.gitignore 已就位）；
5. 照搬 WindAnaly 的 `run_checks.bat`（compileall + pytest + 离屏冒烟）。

### S2 · 收敛：功能与命名统一（1 周，行为微调）

1. **D4/D5** 合并双 M1 工具：保留 06 三表联动版迁入 04（或目录改名合并），
   钳位策略做成 UI 选项（全量钳位 / 连续 3 点）；修参数记忆键 hack；
2. **D6** 机型库「查看即写盘」改为仅增删改时保存；
3. 插件文案第一轮统一（P7）：列名格式（σ1/Vhub [A] 风格）、单位括号全半角；
4. 删除 `clear_overrides_silently` 等仅测试使用的调试 API（改用正式 API）。

### S3 · 内功：样式统一 + 卫生（1 周，可与 S2 穿插）

1. **D7** 样式两层化：theme.qss 收敛全局、toolbox_window 内联 QSS 迁入
   theme.qss（objectName 选择器），_style.py 只留强制浅色专用；
2. **D10** UI 术语表 + 列名终审；
3. **D8/D12** 卫生批：文件句柄 with 化、HINT 去重、样例加载失败给行内提示；
4. GitHub Actions CI（照搬 WindAnaly：windows-latest + offscreen pytest）。

### S4 · 交付：增量发布自动化（0.5~1 周）

1. **D9** 移植 WindAnaly 的模块化分发 + 构建缓存（boot 桩 + app/*.pyc +
   `_runtime_fingerprint()`），日常补丁降到 KB~MB 级；
2. ~~`tools/release.py`~~（✅ 1.0.0 已交付：build→冒烟→完整包→基线重演→
   增量 diff→versions.json→源码归档一条龙，本次发布即由其产出）；
3. ~~发版验证脚本~~（✅ 1.0.0 已交付：`tools/verify_updater_install.py` /
   `verify_updater_gui.py` 两个端到端，随 RELEASE.md §1 常态执行）；
4. 建立本地 `release/<版本>/` 三件套归档（✅ 首版已建立）。

### S5 · 远期方向（评估后立项）

- **插件协议升级**：插件元数据（TITLE/HINT/分组）注册表化，支持
  每插件独立版本与依赖声明；
- **计算引擎向量化**：distribution/energy 大 bin 量场景 numpy 化
  （当前规模无压力，仅在出现性能反馈时启动）；
- **与 WindAnaly 联动**：工具箱内深链打开 WindAnaly 工程文件的入口；
- **多语言**：若出海需求出现，参照 WindAnaly i18n 方案。

---

## 6. 风险与对策

| 风险 | 对策 |
|---|---|
| 拍平后遗留 `windkit.` 引用未被发现的角落 | 已 compileall + 34 项测试 + 冻结版冒烟三重验证；后续 CI 兜底 |
| 更新源仓库不存在导致首版更新失败 | §4.3 第 5 步：发版前确认/改源；更新器已验证优雅降级 |
| 用户数据迁移（本次 data/ 结构不变，无迁移） | turbines.json 落点开发/冻结两模式均已验证 |
| 修 P1~P3 引入计算回归 | 先补插件级测试（锚点沿用源 Excel），再动算法 |
| M1 合并丢失任一老入口的使用习惯 | 合并后保留原两种钳位语义为选项，README 说明 |
| Python 3.14 (构建) / 3.13 (开发 venv) 双环境混淆 | 发版 SOP 固定「构建用系统 3.14」；build.py 已加 tkinter 预检，缺依赖直接给明确报错 |

---

## 7. 度量看板（每批发布后更新）

| 指标 | 重组前 | 现状（v1.0.0 已发布） | 目标 |
|---|---|---|---|
| 顶层布局 | main.py + windkit/ 嵌套包 | 根级 core/ ui/ plugins/ updater/ ✅ | 维持 |
| 死代码 | ≥1,100 行（_boundary_centroid 840 + external_tab 120 + 零散） | **0 ✅** | 维持 |
| 自动更新 | 无（仅 QSS 残留） | updater.exe 全链路打通，三模式端到端验证 ✅；**真实 GitHub 源已上线** ✅ | 持续滚动发版 |
| 打包 | 不存在（requirements 引用幻影 build.py） | release.py + publish_release.py 全自动 ✅ | 增量补丁 KB 级（D9） |
| 测试 | 33 项 | **46 项**（更新器 10 + 打包清单 2） | 50+（S1/S2 插件级） |
| 已知功能 bug | 4（P1~P4） | 3（P1~P3 已登记待修）+ 打包装载 bug 已修 ✅ | 0 |
| git/CI | 无 | **已 git 化并推送 GitHub** ✅（便携 git，远程 kyarazhan/WindKit） | GitHub Actions CI（S3） |
| 已发布版本 | 0 | 1.0.0（本地）/ **1.0.1（GitHub Releases 在线）** | 持续滚动 |

---

*本规划书随迭代滚动更新；每完成一批在 §0 追加记录。*

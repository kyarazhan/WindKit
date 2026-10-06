# WindKit 发版 SOP

> 配套：[REFACTOR_PLAN.md](REFACTOR_PLAN.md) §4（更新器机制）·
> 同机制姊妹项目 WindAnaly 的 RELEASE.md

## 0. 一句话流程

```
改 core/version.py → run_checks 全绿 → python tools/release.py <版本> --notes "说明"
→ git push origin main v<版本> → python tools/publish_release.py <版本>
```

## 1. 发版前

1. `core/version.py` 版本号改为本次版本（唯一改动点）；
2. 本地回归全绿：
   ```
   .venv\Scripts\python -m pytest tests -q          # 46 项（含更新器 10 + 打包清单 2）
   python -X utf8 tools\verify_updater_install.py   # 真实 updater.exe 本地安装端到端
   python -X utf8 tools\verify_updater_gui.py       # 独立运行+在线更新 GUI 端到端
   ```
3. 确认 `updater/sources.json` 指向真实更新源（当前 `kyarazhan/WindKit`
   GitHub Releases，已上线可用；改内网源只需改此文件，无需动代码）。

## 2. 发版（用系统 Python，含 tkinter；.venv 3.13 无 tkinter）

```
python tools/release.py <版本> --notes "本版更新说明"
python tools/release.py <版本> --notes "说明" --skip-build   # dist 已是新版时
```

脚本自动完成：版本校验 → `build.py`（主程序 onedir + updater.exe）→
冻结 exe 冒烟 → 完整包 zip → 基线重演 + 文件级 diff 增量包（有上一版时）→
`versions.json` → 源码归档。

产物约定（release/<版本>/）：

| 文件 | 用途 |
|---|---|
| `versions.json` | 更新源版本索引（上传 Release 时必传） |
| `WindKit-<版本>.zip` | 完整包，带顶层 `WindKit/` 文件夹（更新器安装时自动去前缀） |
| `<旧>-<新>-patch.zip` | 增量包（文件级 diff；`data/app_version.txt` 每包强制携带） |
| `WindKit_v<版本>_source_<日期>.zip` | 源码归档（本地/Release 留存） |

- `data/app_version.txt` 随每个包写入新版本号（更新器识别已装版本的依据）；
  `data/` 其余用户数据永不进包、安装时永不覆盖；
- 每次安装前更新器自动备份 `data/` → `data/backups/pre_update_<时间戳>.zip`。

## 3. 上传 GitHub（仓库 + Release）

```
git push origin main v<版本>                    # 代码 + 标签（便携 git：
                                                # Project\.tools\PortableGit）
python tools/publish_release.py <版本>          # 创建 Release 并上传
                                                # versions.json / 全量包 / 增量包
```

凭据走 git credential manager（与 push 同源）；脚本对同名资产先删后传，可安全重跑。
上传完成后真实源即生效——可用「模拟旧版本后台查询」验证（见 §4）。

## 4. 发版后验证

1. 装上一版 → 主程序「帮助 → 检查更新」→ 应列出最新版并可完成升级；
2. 老版本 + 增量链逐级补齐（多跳）与全量包一步到位各验一次；
3. 双击 updater.exe（无参数）独立运行：在线检查 + 本地包安装各验一次；
4. 升级后确认 `data/turbines.json` 用户改动仍在、`data/backups/` 出现备份；
5. GitHub 源在线验证：后台查询应发现新版并写 `.update/available.json`
   （v1.0.1 上线时已验证 ✅）。

## 5. 历史发布记录

| 版本 | 日期 | 说明 |
|---|---|---|
| 1.0.0 | 2026-09-27 | 首个公开发布版本（本地归档；未上 GitHub——含插件装载 bug，被 1.0.1 取代） |
| 1.0.1 | 2026-09-27 | 修复打包版 13 个插件装载失败（core/ui 子模块显式入包）；插件装载结果落日志。**已发布 GitHub Releases**：代码+tag 已推、Release 资产（全量/增量/versions.json）已上传，真实源在线查询验证通过 |
| 1.0.2 | 2026-10-06 | 功能调整：移除湍流曲线/长期订正/50年一遇最大风速；M1拆分并入载荷工况；机型库精简为金风 GWH221-6.25/6.7（未修改的旧库自动迁移）。更新器随包种子保护修复（仅顶层 data/） |

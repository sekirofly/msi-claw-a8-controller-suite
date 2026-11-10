# MSI Claw A8 Controller Suite

Alpha.26 让快速面板恢复自然的层级：先状态信息，后编辑动作。动作是唯一的焦点停靠点，Steam 只需让这一行露出来，上方的状态就在旁边。

> 首次安装默认启用；主动停用后跨重启保持停用，直到再次启用。恢复目标是系统默认，不是旧插件或用户此前的自定义配置。

[English](README.md) | 简体中文

面向 **MSI Claw A8（AMD Ryzen Z2 Extreme / BZ2EM）** 的综合 Decky 手柄管理插件项目。计划继承现有[背键与震动插件](https://github.com/sekirofly/msi-claw-a8-back-buttons-rumble)的硬件控制功能，结合 [DeckyPlumber](https://github.com/aarron-lee/DeckyPlumber) 的部分 InputPlumber 管理思路。

**v0.1.0-alpha.29 为可安装预览版，供 A8 实机测试；不是稳定版，新增功能尚未经真机验证。** 现有小插件继续独立维护。第一阶段只针对 A8，不把 Claw 8 AI+ 等其他型号当作已兼容设备。本项目非 MSI 官方产品。

## 安装与更新

1. 先停用或卸载原 DeckyPlumber 和背键/震动小插件，避免两个后台同时改配置。安装器不会自动删除它们。
2. 在 SteamOS 桌面模式的 Konsole，以普通用户运行：

```sh
curl -fsSL https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.0-alpha.29/install.sh | bash
```

3. **安装后保存工作并重启，再回游戏模式。** 若重启后仍有震动消失，可按 [MSI 官方 EC 重置说明](https://www.msi.com/support/technical_details/HH_EC_Reset)恢复；不需要每次都做，插件不会自动重置。
4. 先检查识别状态，以较低强度点击“测试震动”。按键管理默认启用，确认内置 A8 后自动应用。测试一个简单的右 M1 映射，再测试“恢复系统默认并停用”；停用选择跨重启保留，点击“启用管理”后重新自动接管。

同一安装命令可覆盖更新，保留按键配置，不会再装一份 Suite。更新不触碰当前接管状态，完成后按已保存的启用/停用选择运行。首次替换原插件是不同项目，不会自动合并原插件文件或配置。

安装器验证固定版本 ZIP 和 SHA-256 后短暂重启 Decky，不重启 InputPlumber。包内包含纯 Python YAML 库，不修改系统 Python。识别或接口不满足条件时会禁用相关操作；如果看到未识别提示，请提供诊断，不要自行放宽到任意设备。详细未完成项见[实现状态](implementation-status.zh-CN.md)。

## 重装、卸载与恢复

插件“维护与关于”内提供“修复安装（保留配置）”“干净重装当前版本”“干净卸载”。更新到未来新版本使用该版本的安装命令。终端也可执行：

```sh
# 干净重装，会清除本插件的按键配置
curl -fsSL https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.0-alpha.29/install.sh | bash -s -- reinstall
# 干净卸载
curl -fsSL https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.0-alpha.29/install.sh | bash -s -- uninstall
# 离线卸载
python3 ~/homebrew/plugins/msi-claw-a8-controller-suite/installer.py uninstall
```

更新/修复只替换插件文件并重启 Decky，保留所有配置。干净重装清除按键配置，保留启用/停用选择；二者都不先恢复设备。卸载才先恢复系统默认，失败时保留安装文件并报错；可显式 `--skip-restore` 跳过（例如 `bash -s -- uninstall --skip-restore`），此时不会恢复设备。

默认配置读取 `/usr/share/inputplumber/profiles/default.yaml` 与 `devices/50-msi_claw_a8_bz2e.yaml`；存在 `/usr/local/share/inputplumber` 时按上游优先级使用该目录。采用系统安装的配置，不读取 `/etc` 中第三方覆盖，不根据 Steam 的显示名称猜测输出类型。文件缺失、格式或 A8 身份不匹配时停止设备写入，运行 `diagnostics.sh` 查看默认文件。旧 `recovery.json` 留作备份，不再参与运行；重装/卸载前将它存入 `~/homebrew/.msi-claw-a8-controller-suite-recovery/`。新安装不创建快照。

默认 Decky 目录为 `~/homebrew`。自定义目录在末尾 `bash` 后加 `-s -- install --decky-home /绝对路径/homebrew`，按需替换动作。不要以 root 启动默认安装命令。

维护失败时查看：

```sh
journalctl -u msi-claw-a8-controller-suite-maintenance --no-pager -n 100
sudo bash ~/homebrew/plugins/msi-claw-a8-controller-suite/diagnostics.sh
```

诊断只读取本地信息，不上传或修改设备。测试期间建议保留触屏或键鼠操作入口。

## 计划功能

新增：[融合设计草案（待评审）](docs/design.zh-CN.md)，涵盖菜单结构、配置规则和代码合并方案；已获准开始实现，详见[实现状态与限制](implementation-status.zh-CN.md)。

最新 UI 建议：首页只放当前按键状态和共用震动控制，背键硬件模式收进手柄设置。游戏专用按键从默认按键复制为独立配置，明确显示编辑对象和保存范围；更换配置一律用复制，不隐式联动，模板库页面已移除。

已确认：每个游戏最多一份专用配置，可从默认或另一游戏的已保存配置复制，之后完全独立。详见[合并前审查](docs/integration-review.zh-CN.md)：列出了父项目代码冲突、建议范围及待真机验证项。

- 保留三个背键硬件模式与左右震动强度独立调节。
- 唯一识别 A8 内置手柄及 InputPlumber 能力，不管理蓝牙或 USB 外接手柄。
- 底层固定使用 Xbox Elite，界面按 A8 实体按键显示，不提供虚拟类型选择。
- 加入 左 M2 / 右 M1 及其他 A8 按键映射，恢复验证通过后加入可选的按游戏映射配置。
- 仅提供简体中文与英文，提供诊断和明确的恢复入口。

界面只呈现 A8 实际按键，包括 左 M2 / 右 M1；Steam 仍可能显示 Xbox Elite 四背键。首次启用管理时保存原配置，仅为已确认的内置手柄设置 Elite 输出；打开插件本身只读。按游戏切换只改变映射。

详见[中文调研与路线](docs/research.zh-CN.md)、[英文源码分析](docs/research.md)及[来源与许可记录](THIRD_PARTY.md)。

第一个开发阶段是移植已验证的背键/震动功能，并加入只读设备探测。当前版本启动时会按保存的管理选择自动接管内置手柄，不自动重启 InputPlumber。后续阶段需在 A8 验证输入、震动、菜单键和恢复路径。

显示名统一为 **MSI Claw A8 Controller Suite**；仓库、计划包名和安装目录标识统一为 `msi-claw-a8-controller-suite`；计划安装路径为 `~/homebrew/plugins/msi-claw-a8-controller-suite`。

## 开发与 CI

```sh
python3 scripts/check_versions.py   # 五处版本号必须一致
ruff check .                        # Python 静态检查（pyflakes 级别）
python3 -m pip install PyYAML==6.0.3
python3 -m unittest discover -s tests -v
```

后端测试在 CI 中同时跑 Python 3.11 与 3.13（掌机上的解释器比开发默认版本新）。`check_versions.py` 存在的原因是版本号出现在五个地方，其中三处一旦不一致会直接导致装不上：`installer.py` 决定下载哪个 release 资产，`install.sh` 钉死了 raw URL，面板里的那处只是显示。

本项目采用 GPL-3.0-only。当前已有开发实现；硬件控制源自原 MIT 小插件，原许可保留在 `third_party/hardware-controls-MIT.txt`。后续复用代码时保留各上游许可和署名，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。

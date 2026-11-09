# MSI Claw A8 Controller Suite

Alpha.15 补齐恢复快照、后台退出和震动测试的异常路径：恢复失败或主动跳过恢复后，重装仍保留原始快照；普通更新继续只替换插件文件。

> Alpha.3 采用两状态管理：首次安装默认启用，重启及会话恢复后自动重新应用；主动停用后一直停用，直到再次启用。首次接管前快照不覆盖。

[English](README.md) | 简体中文

面向 **MSI Claw A8（AMD Ryzen Z2 Extreme / BZ2EM）** 的综合 Decky 手柄管理插件项目。计划继承现有[背键与震动插件](https://github.com/sekirofly/msi-claw-a8-back-buttons-rumble)的硬件控制功能，结合 [DeckyPlumber](https://github.com/aarron-lee/DeckyPlumber) 的部分 InputPlumber 管理思路。

**v0.1.0-alpha.15 为可安装预览版，供 A8 实机测试；不是稳定版，新增功能尚未经真机验证。** 现有小插件继续独立维护。第一阶段只针对 A8，不把 Claw 8 AI+ 等其他型号当作已兼容设备。本项目非 MSI 官方产品。

## 安装与更新

1. 先停用或卸载原 DeckyPlumber 和背键/震动小插件，避免两个后台同时改配置。安装器不会自动删除它们。
2. 在 SteamOS 桌面模式的 Konsole，以普通用户运行：

```sh
curl -fsSL https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.0-alpha.15/install.sh | bash
```

3. **安装后保存工作并重启，再回游戏模式。** 若重启后仍有震动消失，可按 [MSI 官方 EC 重置说明](https://www.msi.com/support/technical_details/HH_EC_Reset)恢复；不需要每次都做，插件不会自动重置。
4. 先检查识别状态，以较低强度点击“测试震动”。按键管理默认启用，确认内置 A8 后自动应用。测试一个简单 M1 映射，再测试“恢复原配置并停用”；停用选择跨重启保留，点击“启用管理”后重新自动接管。

同一安装命令可覆盖更新，保留按键配置，不会再装一份 Suite。更新不触碰当前接管状态，完成后按已保存的启用/停用选择运行。首次替换原插件是不同项目，不会自动合并原插件文件或配置。

安装器验证固定版本 ZIP 和 SHA-256 后短暂重启 Decky，不重启 InputPlumber。包内包含纯 Python YAML 库，不修改系统 Python。识别或接口不满足条件时会禁用相关操作；如果看到未识别提示，请提供诊断，不要自行放宽到任意设备。详细未完成项见[实现状态](implementation-status.zh-CN.md)。

## 重装、卸载与恢复

插件“维护与关于”内提供“修复安装（保留配置）”“干净重装当前版本”“干净卸载”。更新到未来新版本使用该版本的安装命令。终端也可执行：

```sh
# 干净重装，会清除本插件的按键配置
curl -fsSL https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.0-alpha.15/install.sh | bash -s -- reinstall
# 干净卸载
curl -fsSL https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.0-alpha.15/install.sh | bash -s -- uninstall
# 离线卸载
python3 ~/homebrew/plugins/msi-claw-a8-controller-suite/installer.py uninstall
```

更新或修复只做三件事：停 Decky、替换插件文件、再启动 Decky；新版本启动后会自己重新接管，因此更新过程完全不调用 InputPlumber。干净重装与卸载才需要先归还控制器，因为记录“接管前状态”的快照即将被删除；这一步最多重试三次，干净重装若仍无法确认只告警，卸载则中止并保留文件与快照。恢复失败或主动跳过恢复时，干净重装会保留原始快照及启用选择，防止新版本把已接管状态当作原始状态。最后手段是 `--skip-restore`（例如 `bash -s -- uninstall --skip-restore`）。

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
- 加入 M1/M2 及其他 A8 按键映射，恢复验证通过后加入可选的按游戏映射配置。
- 仅提供简体中文与英文，提供诊断和明确的恢复入口。

界面只呈现 A8 实际按键，包括 M1/M2；Steam 仍可能显示 Xbox Elite 四背键。首次启用管理时保存原配置，仅为已确认的内置手柄设置 Elite 输出；打开插件本身只读。按游戏切换只改变映射。

详见[中文调研与路线](docs/research.zh-CN.md)、[英文源码分析](docs/research.md)及[来源与许可记录](THIRD_PARTY.md)。

第一个开发阶段是移植已验证的背键/震动功能，并加入只读设备探测。当前版本启动时会按保存的管理选择自动接管内置手柄，不自动重启 InputPlumber。后续阶段需在 A8 验证输入、震动、菜单键和恢复路径。

显示名统一为 **MSI Claw A8 Controller Suite**；仓库、计划包名和安装目录标识统一为 `msi-claw-a8-controller-suite`；计划安装路径为 `~/homebrew/plugins/msi-claw-a8-controller-suite`。

本项目采用 GPL-3.0-only。当前已有开发实现；硬件控制源自原 MIT 小插件，原许可保留在 `third_party/hardware-controls-MIT.txt`。后续复用代码时保留各上游许可和署名，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。

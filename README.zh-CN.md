# MSI Claw A8 Controller Suite

[English](README.md) | 简体中文

面向 **MSI Claw A8（AMD Ryzen Z2 Extreme / BZ2EM）** 的综合 Decky 手柄管理插件项目。计划继承现有[背键与震动插件](https://github.com/sekirofly/msi-claw-a8-back-buttons-rumble)的硬件控制功能，结合 [DeckyPlumber](https://github.com/aarron-lee/DeckyPlumber) 的部分 InputPlumber 管理思路。

**已开始第一轮开发（0.1.0-alpha.1），尚无正式安装版，未在 A8 验证新增功能。** 现有小插件继续独立维护。第一阶段只针对 A8，不把 Claw 8 AI+ 等其他型号当作已兼容设备。本项目非 MSI 官方产品。

## 计划功能

新增：[融合设计草案（待评审）](docs/design.zh-CN.md)，涵盖菜单结构、配置规则和代码合并方案；已获准开始实现，详见[实现状态与限制](implementation-status.zh-CN.md)。

最新 UI 建议：首页只放当前按键状态和共用震动控制，背键硬件模式收进手柄设置。游戏专用按键从默认按键复制为独立配置，明确显示编辑对象和保存范围；方案库以复制导入方式复用，不隐式联动。

已确认：每个游戏最多一份专用配置，可从默认、其他游戏的已保存配置或模板复制，之后完全独立。详见[合并前审查](docs/integration-review.zh-CN.md)：列出了父项目代码冲突、建议范围及待真机验证项。

- 保留三个背键硬件模式与左右震动强度独立调节。
- 唯一识别 A8 内置手柄及 InputPlumber 能力，不管理蓝牙或 USB 外接手柄。
- 底层固定使用 Xbox Elite，界面按 A8 实体按键显示，不提供虚拟类型选择。
- 加入 M1/M2 及其他 A8 按键映射，恢复验证通过后加入可选的按游戏映射配置。
- 仅提供简体中文与英文，提供诊断和明确的恢复入口。

界面只呈现 A8 实际按键，包括 M1/M2；Steam 仍可能显示 Xbox Elite 四背键。首次启用管理时保存原配置，仅为已确认的内置手柄设置 Elite 输出；打开插件本身只读。按游戏切换只改变映射。

详见[中文调研与路线](docs/research.zh-CN.md)、[英文源码分析](docs/research.md)及[来源与许可记录](THIRD_PARTY.md)。

第一个开发阶段是移植已验证的背键/震动功能，并加入只读设备探测。启动时不自动重启 InputPlumber 或替换手柄。后续阶段需在 A8 验证输入、震动、菜单键和恢复路径。

显示名统一为 **MSI Claw A8 Controller Suite**；仓库、计划包名和安装目录标识统一为 `msi-claw-a8-controller-suite`；计划安装路径为 `~/homebrew/plugins/msi-claw-a8-controller-suite`。

本项目采用 GPL-3.0-only。当前已有开发实现；硬件控制源自原 MIT 小插件，原许可保留在 `third_party/hardware-controls-MIT.txt`。后续复用代码时保留各上游许可和署名，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。

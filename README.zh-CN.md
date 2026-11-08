# MSI Claw A8 Controller Suite

[English](README.md) | 简体中文

面向 **MSI Claw A8（AMD Ryzen Z2 Extreme / BZ2EM）** 的综合 Decky 手柄管理插件项目。计划继承现有[背键与震动插件](https://github.com/sekirofly/msi-claw-a8-back-buttons-rumble)的硬件控制功能，结合 [DeckyPlumber](https://github.com/aarron-lee/DeckyPlumber) 的部分 InputPlumber 管理思路。

**当前仅完成调研与设计，尚无可安装插件或发行版。** 现有小插件继续独立维护。第一阶段只针对 A8，不把 Claw 8 AI+ 等其他型号当作已兼容设备。本项目非 MSI 官方产品。

## 计划功能

新增：[融合设计草案（待评审）](docs/design.zh-CN.md)，涵盖菜单结构、配置规则和代码合并方案；评审通过后再实现。

- 保留三个背键硬件模式与左右震动强度独立调节。
- 检测 A8 内置手柄、InputPlumber 能力以及支持的虚拟手柄类型。
- 加入虚拟手柄类型切换，再加入 M1/M2 和菜单键映射。
- 手动切换和恢复验证通过后，再加入可选的按游戏配置。
- 仅提供简体中文与英文，提供诊断和明确的恢复入口。

“虚拟手柄类型”“背键硬件模式”“按键映射”是三个不同设置。切换成 PlayStation 类型不会凭空增加自适应扳机等硬件能力。

详见[中文调研与路线](docs/research.zh-CN.md)、[英文源码分析](docs/research.md)及[来源与许可记录](THIRD_PARTY.md)。

第一个开发阶段是移植已验证的背键/震动功能，并加入只读设备探测。启动时不自动重启 InputPlumber 或替换手柄。后续阶段需在 A8 验证输入、震动、菜单键和恢复路径。

显示名统一为 **MSI Claw A8 Controller Suite**；仓库、计划包名和安装目录标识统一为 `msi-claw-a8-controller-suite`；计划安装路径为 `~/homebrew/plugins/msi-claw-a8-controller-suite`。

本项目采用 GPL-3.0-only。目前仅包含原创调研/设计文档及许可证文本，尚未导入其他插件实现。后续复用代码时保留各上游许可和署名，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。

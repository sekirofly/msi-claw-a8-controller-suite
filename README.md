# MSI Claw A8 Controller Suite

English | [简体中文](README.zh-CN.md)

A planned Decky controller-management plugin for **MSI Claw A8 (AMD Ryzen Z2 Extreme / BZ2EM)**, combining the hardware controls from [MSI Claw A8 Back Buttons & Rumble](https://github.com/sekirofly/msi-claw-a8-back-buttons-rumble) with selected InputPlumber integration inspired by [DeckyPlumber](https://github.com/aarron-lee/DeckyPlumber).

**Status: research and design only. No installable plugin or release yet.** The existing Back Buttons & Rumble plugin remains a separate project. Other Claw models, including Claw 8 AI+, are outside the initial scope. This is community software, not an official MSI product.

## Planned scope

- Keep the existing three hardware back-button modes and independent left/right rumble strength controls.
- Uniquely identify the embedded A8 controller and its InputPlumber capabilities; never target Bluetooth or USB external controllers.
- Use a fixed Xbox Elite output internally, with an A8-native button interface and no virtual-controller type selector.
- Add M1/M2 and other A8 button mappings, then optional per-game mapping profiles after recovery is validated.
- Provide Simplified Chinese and English interfaces, diagnostics, and explicit restore controls.

The UI represents the actual A8 buttons, including M1/M2. Steam may still identify an Xbox Elite with four paddles. First activation snapshots the original configuration and establishes Elite output only for the verified embedded controller; simply opening the plugin is read-only. Per-game changes only update mappings.

## Research and implementation plan

The proposed integration design is ready for review: [简体中文设计草案](docs/design.zh-CN.md). The quick panel shows active mappings and shared rumble controls; infrequent hardware back-button modes move into device settings. Game-specific mappings start as independent copies of default mappings, with explicit editing scope and save actions. Library presets are copied into configurations rather than silently linked. Implementation awaits user review.

See [code research and capability matrix](docs/research.md), [中文调研与路线](docs/research.zh-CN.md), and [source provenance](THIRD_PARTY.md).

First implementation milestone: port the proven hardware controls and add read-only device/capability discovery. No automatic InputPlumber restart or controller replacement on startup. Subsequent milestones require A8 testing of input, rumble, menu buttons and recovery paths.

## Identity

| Item | Value |
| --- | --- |
| Display name | MSI Claw A8 Controller Suite |
| Repository / planned package and installation directory | `msi-claw-a8-controller-suite` |
| Planned installation path | `~/homebrew/plugins/msi-claw-a8-controller-suite` |
| Languages | Simplified Chinese and English |

## License

GPL-3.0-only for this project. This repository currently contains original research/design documents and the license text, with no imported plugin implementation. Any future code reuse must preserve upstream notices and applicable source-distribution obligations; see [THIRD_PARTY.md](THIRD_PARTY.md).

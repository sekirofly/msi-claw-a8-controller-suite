# MSI Claw A8 Controller Suite

English | [简体中文](README.zh-CN.md)

A planned Decky controller-management plugin for **MSI Claw A8 (AMD Ryzen Z2 Extreme / BZ2EM)**, combining the hardware controls from [MSI Claw A8 Back Buttons & Rumble](https://github.com/sekirofly/msi-claw-a8-back-buttons-rumble) with selected InputPlumber integration inspired by [DeckyPlumber](https://github.com/aarron-lee/DeckyPlumber).

**Status: research and design only. No installable plugin or release yet.** The existing Back Buttons & Rumble plugin remains a separate project. Other Claw models, including Claw 8 AI+, are outside the initial scope. This is community software, not an official MSI product.

## Planned scope

- Keep the existing three hardware back-button modes and independent left/right rumble strength controls.
- Detect the actual A8 controller, InputPlumber capabilities and available virtual controller types.
- Add supported virtual controller modes, followed by M1/M2 and menu-button remapping.
- Add optional per-game profiles after manual switching and recovery are validated.
- Provide Simplified Chinese and English interfaces, diagnostics, and explicit restore controls.

Virtual controller identity, hardware back-button mode and button mapping are separate settings. Selecting a PlayStation-style virtual device does not add missing physical hardware features.

## Research and implementation plan

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

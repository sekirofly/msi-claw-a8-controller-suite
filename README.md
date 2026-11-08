# MSI Claw A8 Controller Suite

English | [简体中文](README.zh-CN.md)

A planned Decky controller-management plugin for **MSI Claw A8 (AMD Ryzen Z2 Extreme / BZ2EM)**, combining the hardware controls from [MSI Claw A8 Back Buttons & Rumble](https://github.com/sekirofly/msi-claw-a8-back-buttons-rumble) with selected InputPlumber integration inspired by [DeckyPlumber](https://github.com/aarron-lee/DeckyPlumber).

**Status: initial development implementation (0.1.0-alpha.1), not a released or device-validated plugin.** The existing Back Buttons & Rumble plugin remains a separate project. Other Claw models, including Claw 8 AI+, are outside the initial scope. This is community software, not an official MSI product.

## Planned scope

- Keep the existing three hardware back-button modes and independent left/right rumble strength controls.
- Uniquely identify the embedded A8 controller and its InputPlumber capabilities; never target Bluetooth or USB external controllers.
- Use a fixed Xbox Elite output internally, with an A8-native button interface and no virtual-controller type selector.
- Add M1/M2 and other A8 button mappings, then optional per-game mapping profiles after recovery is validated.
- Provide Simplified Chinese and English interfaces, diagnostics, and explicit restore controls.

The UI represents the actual A8 buttons, including M1/M2. Steam may still identify an Xbox Elite with four paddles. First activation snapshots the original configuration and establishes Elite output only for the verified embedded controller; simply opening the plugin is read-only. Per-game changes only update mappings.

## Research and implementation plan

The proposed integration design is ready for review: [简体中文设计草案](docs/design.zh-CN.md). The quick panel shows active mappings and shared rumble controls; infrequent hardware back-button modes move into device settings. Game-specific mappings start as independent copies of default mappings, with explicit editing scope and save actions. Library presets are copied into configurations rather than silently linked. Implementation has started; see [implementation status](docs/implementation-status.md).

Confirmed: each game has at most one independent configuration, copied from defaults, another game's saved configuration, or a template. No live cross-game sharing. See the [pre-implementation integration review](docs/integration-review.zh-CN.md) for source-level conflicts, proposed scope boundaries and hardware checks still required.

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

GPL-3.0-only for this project. This repository now includes a development implementation. Hardware controls derive from the existing MIT plugin, whose notice is retained in `third_party/hardware-controls-MIT.txt`. Any future code reuse must preserve upstream notices and applicable source-distribution obligations; see [THIRD_PARTY.md](THIRD_PARTY.md).

## Development

Node 22, pnpm 11.25.0 and Python 3.11+ are used in Linux CI:

```sh
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
node --test tests/frontend.cjs
python3 -m pip install PyYAML==6.0.3
python3 -m unittest discover -s tests -v
```

PyYAML is required for InputPlumber profile operations. The plugin never installs system packages. Do not run the development pip command against SteamOS system Python; use an isolated development environment. No production installer or release archive is supplied yet. CI tests simulate devices and do not validate actual A8 behavior.

Terminal recovery is implemented in `recover.py`. On a manually provisioned development device, first stop this plugin's automatic callbacks, then invoke it with `sudo python3 /absolute/plugin/path/recover.py --settings-dir /absolute/DECKY_PLUGIN_SETTINGS_DIR`. Use the exact directory reported by Decky for this plugin, not a guessed slug. Preserve `recovery.json` until restoration is confirmed. Hardware back-button mode and rumble settings are not reset. Automated uninstall/reinstall is still pending; do not delete the only recovery snapshot.

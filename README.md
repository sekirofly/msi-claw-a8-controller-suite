# MSI Claw A8 Controller Suite

Alpha.26 restores the natural order on the quick panel: the status rows come first and the edit action sits below them. The action is the only focus stop, so Steam only has to reveal one small row, and the context above it stays adjacent.

> Fresh installs default to enabled. Explicit disable persists across reboot until enabled again. Restoration means system defaults, not another plugin’s or an earlier custom configuration.

English | [简体中文](README.zh-CN.md)

A Decky controller-management plugin for **MSI Claw A8 (AMD Ryzen Z2 Extreme / BZ2EM)**, combining the hardware controls from [MSI Claw A8 Back Buttons & Rumble](https://github.com/sekirofly/msi-claw-a8-back-buttons-rumble) with selected InputPlumber integration inspired by [DeckyPlumber](https://github.com/aarron-lee/DeckyPlumber).

**Status: v0.1.0-alpha.28 preview for A8 testing, not a stable or device-validated release.** The existing Back Buttons & Rumble plugin remains a separate project. Other Claw models, including Claw 8 AI+, are outside the initial scope. This is community software, not an official MSI product.

## Install / update the preview

1. Disable or uninstall DeckyPlumber and the separate Back Buttons & Rumble plugin before enabling this suite. Removing them is not automated; two active controllers must not compete.
2. In SteamOS Desktop Mode, open Konsole and run as your normal desktop user:

```sh
curl -fsSL https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.0-alpha.28/install.sh | bash
```

3. **Save work and reboot before returning to Gaming Mode.** If vibration remains unavailable after reboot, an EC reset may help; follow [MSI's official EC reset guidance](https://www.msi.com/support/technical_details/HH_EC_Reset). EC reset is not required routinely and is never automated.
4. Open the suite, inspect device status, and first test rumble at a modest strength. Management starts enabled and applies automatically once the embedded A8 is identified. Test a simple Right M1 mapping, then test **Restore system defaults and disable**. This choice persists across reboot; **Enable management** resumes automatic management.

The installer checks the version-pinned ZIP and SHA-256 checksum, then briefly restarts Decky. It never restarts InputPlumber. A checksum detects corruption, not an independently signed release. Normal install/update retains configurations without restoring the controller first, then resumes the saved enabled/disabled choice. Keyboard and mouse are useful while testing controller configuration.

No system Python changes are needed: pure-Python PyYAML is bundled. Unknown board/USB topology or missing InputPlumber APIs disables the affected operation instead of guessing another controller. Read [preview limitations](docs/implementation-status.md).

## Repair, clean reinstall, uninstall

The Maintenance page provides repair (same version, keep configurations), clean reinstall and clean uninstall. For a newer release, run that release's install command. Terminal alternatives:

```sh
# Clean reinstall: clear mappings, retain enabled/disabled choice, install again
curl -fsSL https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.0-alpha.28/install.sh | bash -s -- reinstall
# Clean uninstall
curl -fsSL https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.0-alpha.28/install.sh | bash -s -- uninstall
# Offline clean uninstall using installed code
python3 ~/homebrew/plugins/msi-claw-a8-controller-suite/installer.py uninstall
```

Default Decky home is `~/homebrew`. For a different location append `-s -- install --decky-home /absolute/homebrew` after `bash` (use the requested action instead of `install`). Do not launch the default command as root; that would choose `/root/homebrew`.

Update/repair replaces files and restarts Decky while retaining all configuration. Clean reinstall clears mappings but retains the management choice. Neither restores the device first. Uninstall restores system defaults before removing files; failed restoration preserves the installation and reports the error. `--skip-restore` explicitly bypasses restoration.

Defaults come from the installed `/usr/share/inputplumber/profiles/default.yaml` and `devices/50-msi_claw_a8_bz2e.yaml`. An existing `/usr/local/share/inputplumber` takes precedence, as upstream does. Third-party `/etc` overrides are not factory defaults. Missing or incompatible files stop device writes rather than guessing from a Steam display name; run `diagnostics.sh` for details. Old `recovery.json` files are retained only as legacy backups, archived under `~/homebrew/.msi-claw-a8-controller-suite-recovery/` before clean reinstall/uninstall. New installs create no snapshot.

If a queued maintenance action does not complete, inspect:

```sh
journalctl -u msi-claw-a8-controller-suite-maintenance --no-pager -n 100
sudo bash ~/homebrew/plugins/msi-claw-a8-controller-suite/diagnostics.sh
```

## Planned scope

- Keep the existing three hardware back-button modes and independent left/right rumble strength controls.
- Uniquely identify the embedded A8 controller and its InputPlumber capabilities; never target Bluetooth or USB external controllers.
- Use a fixed Xbox Elite output internally, with an A8-native button interface and no virtual-controller type selector.
- Add Left M2 / Right M1 and other A8 button mappings, then optional per-game mapping profiles after recovery is validated.
- Provide Simplified Chinese and English interfaces, diagnostics, and explicit restore controls.

The UI represents the actual A8 buttons, including Left M2 / Right M1. Steam may still identify an Xbox Elite with four paddles. First automatic activation snapshots the original configuration and establishes Elite output only for the verified embedded controller. The backend applies the suite state once at startup, and again only on an explicit change: a game switch, a saved configuration, the management toggle or a retry. It does not poll the device; opening the panel adds no writes and only reports drift. Per-game changes only update mappings.

## Research and implementation plan

The proposed integration design is ready for review: [简体中文设计草案](docs/design.zh-CN.md). The quick panel shows active mappings and shared rumble controls; infrequent hardware back-button modes move into device settings. Game-specific mappings start as independent copies of default mappings, with explicit editing scope and save actions. Copies are made from the default buttons or another game's saved configuration; the separate template library page was removed because it duplicated that path. Implementation has started; see [implementation status](docs/implementation-status.md).

Confirmed: each game has at most one independent configuration, copied from the default buttons or another game's saved configuration. No live cross-game sharing and no template library. See the [pre-implementation integration review](docs/integration-review.zh-CN.md) for source-level conflicts, proposed scope boundaries and hardware checks still required.

See [code research and capability matrix](docs/research.md), [中文调研与路线](docs/research.zh-CN.md), and [source provenance](THIRD_PARTY.md).

First implementation milestone: port the proven hardware controls and add read-only device/capability discovery. Startup now reconciles the saved management choice for the embedded controller without restarting InputPlumber. Subsequent milestones require A8 testing of input, rumble, menu buttons and recovery paths.

## Identity

| Item | Value |
| --- | --- |
| Display name | MSI Claw A8 Controller Suite |
| Repository / package and installation directory | `msi-claw-a8-controller-suite` |
| Installation path | `~/homebrew/plugins/msi-claw-a8-controller-suite` |
| Languages | Simplified Chinese and English |

## License

GPL-3.0-only for this project. This repository now includes a development implementation. Hardware controls derive from the existing MIT plugin, whose notice is retained in `third_party/hardware-controls-MIT.txt`. Any future code reuse must preserve upstream notices and applicable source-distribution obligations; see [THIRD_PARTY.md](THIRD_PARTY.md).

## Development

Node 22, pnpm 11.25.0 and Python 3.11+ are used in Linux CI:

```sh
python3 scripts/check_versions.py     # every version string must agree
ruff check .                          # pyflakes-level Python checks
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
node --test tests/frontend.cjs
python3 -m pip install PyYAML==6.0.3
python3 -m unittest discover -s tests -v
```

Backend tests run on Python 3.11 and 3.13 in CI, because the handheld ships a newer interpreter than the development default. `check_versions.py` exists because the version appears in five places and three of them break installation when they drift: `installer.py` picks the release asset, `install.sh` pins the raw URL, and the panel only displays it.

Pure-Python PyYAML is bundled in the preview. The pip command above is for an isolated development environment, not SteamOS system Python. CI tests simulate controllers and do not validate actual A8 behavior.

Terminal recovery is implemented in `recover.py`. On a manually provisioned development device, first stop this plugin's automatic callbacks, then invoke it with `sudo python3 /absolute/plugin/path/recover.py --settings-dir /absolute/DECKY_PLUGIN_SETTINGS_DIR`. Use the exact directory reported by Decky for this plugin, not a guessed slug. Recovery requires the installed default files, not a saved snapshot. Hardware back-button mode and rumble settings are not reset. Prefer the installer uninstall flow, which stops Decky before recovery. Legacy snapshots are not used by this version.

# MSI Claw A8 Controller Suite

A Decky plugin for the embedded controller on **MSI Claw A8 (BZ2EM / MS-1T8K)**. **v0.1.0 is the first stable release.** Community software, not an MSI product; other Claw models are outside the supported scope.

[简体中文](README.zh-CN.md) · [Implementation status](docs/implementation-status.md)

## Install and update

Install Decky first. Disable DeckyPlumber and the separate back-button/rumble plugin to avoid competing writers. Run as your normal desktop user in SteamOS Konsole:

```sh
curl -fsSL https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.3/install.sh | bash
```

The installer verifies the release SHA-256 and restarts Decky. Updates retain mappings and management preference without resetting the controller. Save work, reboot the handheld and check plugin status. Installation completion does not confirm that mappings were applied. For a custom Decky home, use `bash -s -- install --decky-home /absolute/homebrew`.

## Use

- Management defaults to enabled on first install; explicit disable persists across reboot. Enabled management uses Xbox Elite and only the verified embedded A8 controller.
- Default mappings apply unless a game's independent custom configuration is enabled. Games are keyed by Steam ID; duplicate names display their IDs. Copying changes local edits; saving commits them.
- Hardware back-button mode and left/right rumble strengths are shared across games. Sliders save automatically; the finite rumble test targets only the embedded controller.
- Restore system defaults and disable uses the installed InputPlumber defaults, not historical custom settings from another plugin. Missing defaults produce an error.

## Maintenance and removal

| Action | Mappings | Controller |
| --- | --- | --- |
| Repair plugin and controller | Retain | Reinstall files and software-reset the internal controller |
| Clear configurations and reinstall | Delete default and all game configurations | Reinstall files and software-reset the controller |
| Clean uninstall | Delete | Restore system defaults, then remove plugin |

After confirming, wait for Decky to restart. The first two actions also require a **full handheld reboot**. Hardware mode and rumble strengths are not backed up/reapplied and may return to device defaults.

Terminal alternatives (`reinstall` clears mappings but retains the management choice):

```sh
# Clear mappings, reinstall and reset controller; reboot afterward
curl -fsSL https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.3/install.sh | bash -s -- reinstall --reset-controller
# Uninstall
curl -fsSL https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.3/install.sh | bash -s -- uninstall
# Offline uninstall using installed files
python3 ~/homebrew/plugins/msi-claw-a8-controller-suite/installer.py uninstall
```

Failed uninstall restoration preserves the installation. `--skip-restore` explicitly bypasses restoration. Legacy recovery.json files are backups only, archived under `~/homebrew/.msi-claw-a8-controller-suite-recovery/` before clearing configuration.

## Troubleshooting

Inspect diagnostics and retry messages in Maintenance. For lost rumble, repair the plugin/controller and reboot. If ineffective, follow [MSI's EC reset instructions](https://www.msi.com/support/technical_details/HH_EC_Reset). Software controller reset is not established as equivalent to a full EC reset.

```sh
sudo bash ~/homebrew/plugins/msi-claw-a8-controller-suite/diagnostics.sh
journalctl -u msi-claw-a8-controller-suite-maintenance --no-pager -n 100
```

Diagnostics are read-only and local. `game_tracking: events` means observed game changes; `compatibility-5s` checks frontend state every five seconds without backend calls/device writes when unchanged. calls.log plus one backup is bounded near 128KiB; successful state reads stay in memory. Decky/system logs follow host policies.

Installed defaults use profiles/default.yaml and devices/50-msi_claw_a8_bz2e.yaml under `/usr/local/share/inputplumber` when present, otherwise `/usr/share/inputplumber`. Third-party `/etc` overrides are not treated as defaults. Pure-Python PyYAML is bundled; system Python is not modified.

## Development and license

```sh
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
node --test tests/frontend.cjs
python3 -m unittest discover -s tests -v
python3 scripts/check_versions.py
```

Packaging requires PyYAML 6.0.3: run scripts/package.py and scripts/verify_package.py. CI also checks Python 3.11/3.13, Ruff and shell syntax.

GPL-3.0-only. Dependencies and original project attribution: [THIRD_PARTY.md](THIRD_PARTY.md). [Design](docs/design.zh-CN.md), [integration review](docs/integration-review.zh-CN.md) and [research](docs/research.md) remain historical references.

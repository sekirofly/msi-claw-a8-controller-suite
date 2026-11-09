# Initial implementation status

## Unreleased: navigation simplified

- The template library page is removed. Copy sources are the default buttons or another game's saved configuration; existing `templates` entries stay in the configuration file and are no longer shown or used.
- Device settings now holds only the back-button hardware mode and rumble. Plugin management (enable, restore original configuration and disable) moved to Maintenance and about, behind a confirmation dialog.
- Back-button modes show translated names next to the upstream identifiers. Per-mode behaviour descriptions still need device verification and were not invented.
- The localized UI test asserts three sidebar pages, that the device page no longer offers management, and polls for focus transfer instead of assuming a fixed delay, removing a pre-existing flake.

## Alpha.4: editor focus and compact mappings

Editor entry explicitly focuses the copy-source control; returning restores the originating entry. Six physical-button groups use two controls per row with horizontal gamepad navigation containers. DOM focus and paired geometry are browser-tested; Steam gamepad navigation still requires device validation.

## Alpha.3: persistent management

The UI has two management choices: enabled and disabled. Fresh installs default to enabled; the backend reconciles without requiring an open panel. Boot and recognized original-state resets reapply Elite and selected mappings. Explicit disable persists before restoration, so failed recovery never re-enables on reboot; recovery errors remain visible with retry. Re-enabling preserves the first snapshot. Updates/repair preserve the choice; clean reinstall resets settings. Legacy active/paused snapshots migrate to enabled; legacy restored snapshots migrate to disabled. Unrelated live changes still stop writes and offer retry rather than requiring restore then enable. Device identity and capability gates remain enforced. Hardware validation is still required.

2026-11-08, preview version 0.1.0-alpha.5. An installer is available for A8 testing; this is not a stable or device-validated release.

Implemented: independent versioned default/game/template storage; strict embedded A8 discovery; serialized sysfs writes; finite 500 ms physical-device rumble test; capability-gated InputPlumber discovery, fixed Elite activation, durable recovery snapshot and terminal restore; English/Chinese quick panel and settings pages; independent copying and per-game selection; explicit save-versus-apply error handling.

Installation/update, repair and clean uninstall/reinstall are now implemented with restoration before removal and snapshot retention on failure. Pure-Python PyYAML and dependency sources/licenses are packaged. Future version updates use a new pinned install command.

Still pending: multi-output and combined-template editing/conflict preview UI; built-in presets; complete outer-navigation draft protection; validated multi-game identification and sleep/restart recovery. The current editor supports one output per source; the backend validates up to four. Axes pass through and Guide/QAM remain protected.

Device discovery deliberately pins the upstream MS-1T8K internal USB topology. Unknown topologies and missing interfaces are rejected. This may need adjustment from actual A8 diagnostics; it must not be widened to arbitrary controllers. Missing profile-readback/target APIs disable mapping management. Missing physical FF_RUMBLE support disables the rumble test.

Boot and recognized original-state resets are reconciled automatically; unknown external changes report an error and offer direct retry. Hardware wake/session behavior still requires validation. Actual hardware source events, labels, rumble behavior, held-button transitions, external-controller coexistence and restoration require A8 testing.

See the [Chinese status](../implementation-status.zh-CN.md) for details and README for development tests and explicit terminal recovery. Preserve the recovery snapshot until restoration succeeds.

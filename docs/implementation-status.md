# Initial implementation status

## Alpha.11: an unconfirmed restore no longer blocks installs

- ``set_targets`` waits four seconds for the read-back and can run unconfirmed, so a slow InputPlumber transition no longer fails immediately.
- The installer retries restoration three times, and treats a restore that still cannot be confirmed as a warning for ``install`` and ``reinstall``. Refusing to update left the user unable to repair anything.
- ``uninstall`` still aborts on an unconfirmed restore: removing the plugin while the controller stays managed is not recoverable afterwards. ``--skip-restore`` remains the explicit override.
- Device validation of the actual rumble pulse is still pending.

## Alpha.10: recovery can no longer deadlock an install

- `targets()` skips a target object that vanished between listing and reading its type. InputPlumber rebuilds target devices during a restore, so one missing object used to abort the whole restore with a `CalledProcessError` traceback.
- `Bus.run` converts a failing or timed out `busctl` into `interface_unavailable`, so failures reach the UI as a retryable state instead of a raw traceback.
- The installer retries restoration once, and runs the freshly unpacked `recover.py` rather than the installed copy: an installed version with this bug could otherwise block every future reinstall.
- `--skip-restore` is documented as a last resort; the snapshot is kept and the controller stays managed.
- Device validation of the actual rumble pulse is still pending.

## Alpha.9: stale error no longer blocks the rumble test

- `flushRumble()` only reports an error for a save it actually attempted. It used to return the previous chain with a module-level `writeError` that was cleared only when a slider moved, so one failed save made every later test fail with "rumble value not saved".
- A failed slider save and a failed test call are handled in separate steps; a save failure no longer aborts the test path silently or re-labels the test error.
- Every callable records `<time> <label> start|ok|error` to `settings/calls.log` (bounded at 64 KB) and the last eight entries are returned in `call_log`, so a failure that happens above the plugin (in Decky's bridge) is distinguishable from one inside it.
- Device validation of the actual pulse is still pending.

## Alpha.8: rumble test reports its own outcome

- `test_rumble` now returns immediately and runs `rumble.pulse` on a daemon thread, so the ~0.5 s effect never holds the callable or the device queue. A slow or failing pulse can no longer surface as a failed call.
- `get_state` returns `rumble_test` (`idle`/`running`/`ok`/`error` with `code` and `detail`), and the rumble panel shows the result of the last attempt.
- The panel separates "rumble value not saved" from "test call failed", which used to share one generic message.
- Device validation of the actual pulse is still pending.

## Alpha.7: callable failures are surfaced

- The serialized guard is a `threading.Lock` held inside the worker thread instead of an `asyncio.Lock` around the await, so a callable cannot fail because of event-loop binding or a cancelled coroutine.
- An exception raised outside the worker is converted into `internal <Type>: <message>` and recorded, instead of reaching Decky as a bare "Python Exception".
- `get_state` returns `last_error` and Maintenance → Diagnostics shows it, so a failure names its cause without reading the journal.
- Rumble test behaviour is unchanged; whether the physical pulse fires is still unverified on the device.

## Alpha.6: navigation simplified

- The template library page and its storage are removed. Copy sources are the default buttons or another game's saved configuration. Loading an older file drops the legacy `templates` key, and the next save writes the file without it; clean installs never create it.
- Device settings now holds only the back-button hardware mode and rumble. Plugin management (enable, restore original configuration and disable) moved to Maintenance and about, behind a confirmation dialog.
- Back-button modes show translated names next to the upstream identifiers. Per-mode behaviour descriptions still need device verification and were not invented.
- The localized UI test asserts three sidebar pages, that the device page no longer offers management, and polls for focus transfer instead of assuming a fixed delay, removing a pre-existing flake.

## Alpha.4: editor focus and compact mappings

Editor entry explicitly focuses the copy-source control; returning restores the originating entry. Six physical-button groups use two controls per row with horizontal gamepad navigation containers. DOM focus and paired geometry are browser-tested; Steam gamepad navigation still requires device validation.

## Alpha.3: persistent management

The UI has two management choices: enabled and disabled. Fresh installs default to enabled; the backend reconciles without requiring an open panel. Boot and recognized original-state resets reapply Elite and selected mappings. Explicit disable persists before restoration, so failed recovery never re-enables on reboot; recovery errors remain visible with retry. Re-enabling preserves the first snapshot. Updates/repair preserve the choice; clean reinstall resets settings. Legacy active/paused snapshots migrate to enabled; legacy restored snapshots migrate to disabled. Unrelated live changes still stop writes and offer retry rather than requiring restore then enable. Device identity and capability gates remain enforced. Hardware validation is still required.

2026-11-08, preview version 0.1.0-alpha.11. An installer is available for A8 testing; this is not a stable or device-validated release.

Implemented: independent versioned default/game/template storage; strict embedded A8 discovery; serialized sysfs writes; finite 500 ms physical-device rumble test; capability-gated InputPlumber discovery, fixed Elite activation, durable recovery snapshot and terminal restore; English/Chinese quick panel and settings pages; independent copying and per-game selection; explicit save-versus-apply error handling.

Installation/update, repair and clean uninstall/reinstall are now implemented with restoration before removal and snapshot retention on failure. Pure-Python PyYAML and dependency sources/licenses are packaged. Future version updates use a new pinned install command.

Still pending: multi-output and combined-template editing/conflict preview UI; built-in presets; complete outer-navigation draft protection; validated multi-game identification and sleep/restart recovery. The current editor supports one output per source; the backend validates up to four. Axes pass through and Guide/QAM remain protected.

Device discovery deliberately pins the upstream MS-1T8K internal USB topology. Unknown topologies and missing interfaces are rejected. This may need adjustment from actual A8 diagnostics; it must not be widened to arbitrary controllers. Missing profile-readback/target APIs disable mapping management. Missing physical FF_RUMBLE support disables the rumble test.

Boot and recognized original-state resets are reconciled automatically; unknown external changes report an error and offer direct retry. Hardware wake/session behavior still requires validation. Actual hardware source events, labels, rumble behavior, held-button transitions, external-controller coexistence and restoration require A8 testing.

See the [Chinese status](../implementation-status.zh-CN.md) for details and README for development tests and explicit terminal recovery. Preserve the recovery snapshot until restoration succeeds.

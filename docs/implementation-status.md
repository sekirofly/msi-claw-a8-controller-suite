# Initial implementation status

## Alpha.33: reduce idle timers and disk logging

- Observe verified MobX Router dependencies plus Steam lifecycle notifications. Use a 5-second compatibility check only without an effective observer. Stabilize changes for 750ms; failed reports back off 2/5/15/30 seconds and stop after five attempts until a new event.
- Replace slider-save polling with completion notifications; one delayed rumble refresh and lifecycle cleanup.
- Coalesce concurrent state requests with mutation invalidation. Reuse a fresh identity within one status read; retain fresh identity checks for mutations. Identical game reports do not reapply mappings.
- Successful state-read traces stay in memory. Rotate calls.log and calls.log.1, each bounded near 64KiB (about 128KiB combined), deduplicate repeated errors. Host logs have their own limits.
- Fake-clock and component tests cover idle timers, transitions, backoff, cleanup and read coalescing. Actual Steam compatibility and power savings require hardware measurement; no wattage claim.

## Alpha.32: combined plugin/controller repair

Repair retains mappings; clean reinstall clears them. Both maintenance actions reset the verified internal controller after installing files and require a handheld reboot. No hardware settings backup/reapply. Ordinary updates remain file-only. Show an inline wait message and disable maintenance buttons after confirmation; submission failure allows retry. Uninstall restores system defaults. Background failure restarts Decky to release pending state, with the error retained in its journal.

## Alpha.31: settings action at the top

Remove the version anchor, styling and focus state. Move the existing Open settings action to the very top without a duplicate at the bottom. Preserve status rows and contextual editor actions.

## Alpha.30: precise editor labels and a text-like version anchor

Restore explicit default/create-game/edit-game action labels. Keep native version navigation without button background, border or block highlight; focus is indicated by text underline only. Activation remains a no-op. Native Steam styling requires hardware confirmation.

## Alpha.29: restore a fixed quick-panel layout

Use a native no-op version button at the top as a focus anchor, followed by plain status rows and one contextual Edit action. A reliable running game opens its custom configuration, otherwise defaults. Remove the extra game action and clickable scope label.

## Alpha.28: restore game-specific entry

When the current game is not the applied scope, offer creation/editing of its custom configuration. The top action still edits the displayed scope. New configurations independently copy defaults; no game entry is shown without a reliable current game.

## Alpha.27: edit the displayed configuration from the top row

Make Current buttons: configuration name the first native action, with plain status rows below and no separate Edit action. Clicking edits the displayed applied scope, including defaults during a running game. Component/type/build checks passed; Steam gamepad scrolling still needs hardware verification.

## Alpha.26: context first, action after

- Alpha.25 put the edit action above the status rows to keep the focus target near the top of the panel. That inverted the information hierarchy: what the controller is currently doing is context and must be read first.
- The rows now come first and the action sits below them. The action remains the only focus stop, so Steam reveals one small row and the context above stays adjacent; no scroll correction is involved.
- A test pins the order in both languages, and is mutation-checked by swapping the two blocks back.

## Alpha.25: no trailing control boxes, no half-width buttons

- The quick panel is one full-width action button plus plain information rows. Passing text as the ``ButtonItem`` child put it in Steam's trailing control field, which rendered as a white box next to the label; the scope now has its own information row and the button carries only the action.
- A configuration without a delete action lets Edit span the whole row. The previous markup reserved the other half for an invisible placeholder, so the button looked off-centre.
- Tests locate the summary by its chevron and assert the scope is plain information, in both languages.

## Alpha.24: every action button the same shape

- Action buttons are ``ButtonItem`` elements whose text is their only child. Without ``layout="below"`` that child lands in the trailing field, so each button drew a box sized to its own label: the three hardware modes and the maintenance actions looked ragged.
- All of them now use ``layout="below"``, matching the rumble test: full row width, centred text, identical height and padding.
- The quick-panel summary keeps the inline label/trailing form because it is a settings row, not an action button.

## Alpha.23: one component family on the quick panel

- The summary is a standard settings row (``ButtonItem`` with a label and a trailing action) instead of a ``DialogButton``, which is the dialog-button primitive and carries different height, padding and background. Mixing the two families is what made the first row look foreign next to the rumble rows.
- Open settings uses ``layout="below"`` like the rumble test, so its text is centred in a full-width row instead of sitting in the trailing control slot.
- No behaviour change: the row still opens the editor, and the information rows below remain non-interactive.

## Alpha.22: one focusable row instead of a tall card

- The quick panel makes only the action row focusable; the game, M2 and M1 lines are plain information again. A one-line focus target is always revealed completely by Steam's own focus scrolling, so no manual scroll correction is needed.
- This removes ``alignToTop``/``scrollParent`` and the two-frame wait added in alpha.21: the scroll math could not remove the clipping because the target itself was five lines tall.
- The information lines are no longer clickable; the action row carries both the current scope and the entry label.
- A test pins the structure: exactly one focusable stop in the panel and no information text inside it (mutation-checked).

## Alpha.21: focus reveals the summary, deletion asks first

- The quick panel aligns its status block with the panel's own scroll container instead of calling `scrollIntoView`. That call moves every scrollable ancestor and could stop a few pixels short, which clipped the first line under the header after scrolling down and back. The offset is computed (`scrollTop += wrapperTop - boxTop`), so the block is aligned wherever it sits and no assumption about being the first row is baked in; focus is never touched.
- Deleting a per-game configuration opens a destructive dialog whose first, focused action is Cancel. Confirming needs a deliberate move to the right; B and Escape cancel. Non-destructive confirmations keep the native dialog.
- CI now fails on a version mismatch between the five places, lints Python with pyflakes rules, runs backend tests on Python 3.11 and 3.13, cancels superseded runs on the same ref, and has job timeouts.
- Native Steam gamepad navigation and the exact scroll offset still need hardware confirmation.

## Alpha.20: native action cards, copy dialog and duplicate names

- Hardware feedback showed the plain text summary was still skipped by Steam navigation. Replace it with one native Decky DialogButton combining summary and editor entry, scrolling to the top on focus.
- Default/game configurations share title, scope/status and Edit/Delete actions; default cannot be deleted.
- Copying uses a separate dialog, changes only local mapping edits, preserves the enable toggle and returns focus on close. Cancel leaves edits unchanged.
- Disambiguate duplicate names in every game selector/title with display-only ID suffixes. Copy/save/delete retain raw IDs and names. Unknown game reports retain applied mappings without treating the previous game as current.
- Chinese/English component and Chromium DOM checks cover card activation/top scrolling, copy/cancel focus, empty sources and ID isolation. Native Steam gamepad navigation still requires hardware confirmation.

## Alpha.19: consistent game-status row

Always show Game: Not running / game name / Reading… on the second summary line. Configuration selection and the single summary focus stop are unchanged.

## Alpha.18: remove redundant headings and copy

- The outer navigation alone displays the plugin title. The quick panel starts with its current-button summary, without repeating the normal management state or device scope.
- The entire summary remains one focus stop; its text lines are not independently focusable. Top scrolling is unchanged.
- Remove repeated configuration headings and current-mode text. State shared hardware scope once per page; selected mode indicators remain.
- Management status/scope lives in Maintenance. Loading, errors and retry remain visible; disabled mapping editors explain that edits are saved for later activation.
- Chinese/English component and browser checks; native Steam navigation still needs hardware confirmation.

## Alpha.17: quick-panel clarity and focus scrolling

- Combine applied scope into “Current buttons: Default buttons / game configuration”. Show a game name only when available and distinguish initial game-state loading from no running game.
- Make the summary a focusable item that scrolls back to the panel top, without moving focus on background refresh. Remove the duplicate quick-panel title.
- Label and order back buttons Left M2 / Right M1 throughout summary/editor/output choices; preserve stored hardware identifiers. Empty rules display No output.
- Installation messages distinguish completion from applied controller state and clarify that hardware mode/rumble strengths are preserved.
- Chinese/English component and Chromium DOM focus/scroll validation; native Steam gamepad navigation requires hardware confirmation.

## Alpha.16: restore installed system defaults

- No new historical snapshots. Enabled mappings are compiled from installed defaults; disable/uninstall restores the installed default profile and A8 targets.
- Read `profiles/default.yaml` and `devices/50-msi_claw_a8_bz2e.yaml` under InputPlumber's system data directory. Missing/incompatible definitions stop writes. No guessed target name.
- Persist the management choice and one pending-restoration flag. Successful disable stops automatic writes; failed restore stays disabled and retries on restart.
- Update/reinstall does not restore first. Reinstall clears mappings but retains management preference. Uninstall preserves files on recovery failure unless explicitly skipped.
- Legacy snapshots remain backups only. Their captured profiles/targets are never used, and corrupt legacy snapshots do not block management.
- Based on InputPlumber `6aca920` config/path.rs, composite_device/mod.rs and the A8 system definition. New default-restoration behavior needs A8 hardware validation.

The following sections are historical; Alpha.16 supersedes snapshot-based restoration.

## Alpha.15: incremental review fixes

- Preserve Alpha.14 file-only updates and avoid rebuilding an already-correct target set.
- If restoration fails or is skipped, clean reinstall retains the active original snapshot and management preference while clearing mappings. Skipped uninstall also keeps an external emergency snapshot.
- Retry complete target reads during object churn; never snapshot or confirm a partial list.
- Cancelled shutdown cannot strand the backend lock; setup failure is retried during startup.
- Reject overlapping rumble pulses and avoid false running state on maintenance rejection. Testing awaits an in-flight slider save and reports its failure without permanently blocking on historic errors.
- Automated regression coverage; new failure paths still need A8 hardware validation. Existing layout and three-page navigation are unchanged.

## Alpha.14: an update no longer touches the controller

- ``transact`` only restores before ``uninstall`` and ``reinstall``. A plain ``install`` (update or repair) now stops Decky, replaces files and starts Decky: the new version re-applies on start, and the snapshot is untouched.
- That removes the slow path entirely: no ``SetTargetDevices``, no read-back window, no retry loop, nothing that can produce a false failure during an update.
- Uninstall keeps the hand-back, because the plugin and its snapshot disappear; clean reinstall keeps it because the snapshot is about to be wiped.
- Test asserts an update runs no subprocess at all.

## Alpha.13: the restore no longer restarts its own rebuild

- ``set_targets`` returns immediately when the target set already matches. Every ``SetTargetDevices`` call makes InputPlumber tear down and rebuild all target objects; writing an already-correct set started a rebuild the read-back then failed on, and the installer's retry restarted that rebuild, so the restore could never settle.
- The read-back window is 10 seconds (was 4), still exact-match.
- A mismatch logs the wanted and actual sets, so the journal names the difference instead of only ``readback_failed``.
- ``install`` and ``reinstall`` no longer print the restore warning on this path; ``uninstall`` keeps the fail-closed behaviour.

## Alpha.12: the rumble test actually runs, and the poll is gone

- ``enqueue`` forwarded the previous promise value into the callable it ran, so ``test_rumble`` was invoked as ``test_rumble(undefined)``. Python raised ``takes 1 positional argument but 2 were given`` before the method body ran; Decky surfaced it only as "Python Exception". ``enqueue`` now calls with no arguments and the call site wraps the zero-argument callable.
- The frontend test now asserts the exact argument list of the rumble call, which is what would have caught this.
- The 5 second device poll is removed. Startup applies once with bounded retries (about 40 s, for a late InputPlumber), and afterwards only explicit changes apply: game switch, saved configuration, management toggle, manual retry. The target set survives suspend on the tested device, so polling bought nothing.
- The panel reports drift (``consistent``) when the controller output no longer matches the snapshot, instead of silently disagreeing.
- Diagnostics add ``pid``, process start time and ``rumble_test``, so a restarted plugin process is distinguishable from a failed call.

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

2026-11-08, preview version 0.1.0-alpha.14. An installer is available for A8 testing; this is not a stable or device-validated release.

Implemented: independent versioned default/game/template storage; strict embedded A8 discovery; serialized sysfs writes; finite 500 ms physical-device rumble test; capability-gated InputPlumber discovery, fixed Elite activation, durable recovery snapshot and terminal restore; English/Chinese quick panel and settings pages; independent copying and per-game selection; explicit save-versus-apply error handling.

Installation/update, repair and clean uninstall/reinstall are now implemented with restoration before removal and snapshot retention on failure. Pure-Python PyYAML and dependency sources/licenses are packaged. Future version updates use a new pinned install command.

Still pending: multi-output and combined-template editing/conflict preview UI; built-in presets; complete outer-navigation draft protection; validated multi-game identification and sleep/restart recovery. The current editor supports one output per source; the backend validates up to four. Axes pass through and Guide/QAM remain protected.

Device discovery deliberately pins the upstream MS-1T8K internal USB topology. Unknown topologies and missing interfaces are rejected. This may need adjustment from actual A8 diagnostics; it must not be widened to arbitrary controllers. Missing profile-readback/target APIs disable mapping management. Missing physical FF_RUMBLE support disables the rumble test.

Boot and recognized original-state resets are reconciled automatically; unknown external changes report an error and offer direct retry. Hardware wake/session behavior still requires validation. Actual hardware source events, labels, rumble behavior, held-button transitions, external-controller coexistence and restoration require A8 testing.

See the [Chinese status](../implementation-status.zh-CN.md) for details and README for development tests and explicit terminal recovery. Preserve the recovery snapshot until restoration succeeds.

# DeckyPlumber code research

Reviewed 2026-11-07. Findings are source-code observations, not A8 hardware test results.

Pinned sources:

- [DeckyPlumber cebd2fc](https://github.com/aarron-lee/DeckyPlumber/tree/cebd2fcab2f6bc17968d1d4c4bf8cb9fa992b3a5), package version 0.1.8; fetched main matched this commit.
- [InputPlumber 6aca920](https://github.com/ShadowBlip/InputPlumber/tree/6aca9202fb8dfd6f31241c3f98b72df4a775c1a1), upstream main at review time; not necessarily the user's installed version.
- [Existing plugin v1.0.1](https://github.com/sekirofly/msi-claw-a8-back-buttons-rumble/tree/v1.0.1).

## Feature matrix

| DeckyPlumber feature | Code evidence | A8 recommendation |
| --- | --- | --- |
| Virtual controller types: Default, Xbox Series, Xbox Elite, DualSense, DualSense Edge, Hori Steam, Steam Deck, 8BitDo Ultimate 2 | `py_modules/controller_modes.py`, `controller_utils.py`: queries `SupportedTargetDeviceIds`, calls `SetTargetDevices` | High value. Show only targets reported by the installed InputPlumber; initial tests should retain native/default and add Xbox Elite, then test DualSense/Steam Deck individually. |
| Global/per-game controller settings | `plugin_settings.py`, `controllerMiddleware.ts`, `currentGameIdListener.tsx`: polls game ID each second, applies selected profile | Useful later. Mode changes can disconnect/re-enumerate a virtual controller; do not silently switch during gameplay by default. |
| Input mapping editor | `eventRegistry.ts`, `EventSelector.tsx`, `MappingEditModal.tsx`: gamepad buttons/axes/triggers/dials, keyboard keys, mouse buttons/motion, one source to multiple targets | Prioritize M1/M2 and Guide/QAM mappings. Registry entries are not proof the physical device emits those events. Multi-target mapping is not a recorded/timed macro system. |
| Preset/custom profile management | `mapping_profiles.py`, `ProfilesManagePage.tsx`: create/edit/delete/duplicate, copy presets, combine profiles, optional base-profile merge, restore base when deselected | Reuse concepts. Preserve the complete device/base configuration and define duplicate-source precedence explicitly. |
| Included presets | `py_modules/profiles`: menu-button swap; experimental volume-button swap | Menu swap is potentially useful; volume swap is low priority. A8 volume routing depends on installed device config. |
| Update/reinstall UI, version/device information, localization | `OtaUpdates.tsx`, `AboutPage.tsx`, `plugin_update.py`, `src/i18n` | Keep the existing project's verified installer design, two-language policy and diagnostics; do not copy OTA wholesale. |
| Suspend/resume listeners | `steamListeners.tsx` and `main.py:on_suspend/on_resume` | Callbacks only log. There is no implemented automatic wake recovery to inherit. |

The advanced boolean option controls whether newly created per-game profiles use Default rather than inheriting the home-screen controller mode. It is not an additional hardware feature.

## What is not implemented there

No A8 sysfs rumble-strength UI or three-way hardware M-key mode control was found. No dedicated gyro calibration/sensitivity page, stick/trigger calibration/deadzone editor, timed macro recorder, RGB, fan or power-management page was found. The event type declaration mentions `gyro`, `accelerometer` and `deadzone`, but the inspected event registry/editor does not expose complete controls for them. These would be new work, not inherited features.

## A8 evidence and limits

InputPlumber's [A8 device definition](https://github.com/ShadowBlip/InputPlumber/blob/6aca9202fb8dfd6f31241c3f98b72df4a775c1a1/rootfs/usr/share/inputplumber/devices/50-msi_claw_a8_bz2e.yaml) matches board `MS-1T8K`, defines XInput/DInput paths, hotkeys, M-key extra input and IMU sources. Default targets are Xbox Elite, mouse and keyboard. Its [claw1 capability map](https://github.com/ShadowBlip/InputPlumber/blob/6aca9202fb8dfd6f31241c3f98b72df4a775c1a1/rootfs/usr/share/inputplumber/capability_maps/msiclaw_type1.yaml) maps M1/KeyRightBrace to RightPaddle1 and M2/KeyLeftBrace to LeftPaddle1, plus Guide/QuickAccess events.

This supports investigating independent back-button mapping and gyro-capable virtual targets. It does not prove those events are available with the user's kernel, firmware, hardware M-key mode and packaged InputPlumber version. A virtual DualSense is not physical DualSense haptics or adaptive triggers. First record the installed version, DMI identity, actual composite device paths, supported targets, source capabilities and output/rumble behavior.

## Integration changes required

1. Dynamically select the A8 composite device. DeckyPlumber hardcodes `CompositeDevice0`; an external controller or re-enumeration could change the ordering.
2. Separate A8 sysfs hardware controls from optional InputPlumber D-Bus controls. Missing InputPlumber must not disable proven hardware controls.
3. Discover real capabilities. Upstream falls back to showing every known target when discovery fails; our UI should instead mark discovery unavailable.
4. Preserve and restore the actual target-device set and base profile. Upstream replaces targets with selected gamepad + keyboard + mouse (with a special touchscreen case for Ayaneo), and its Default branch can restart InputPlumber when a state file exists. Do not assume that is a safe A8 recovery strategy.
5. Read actual state, serialize writes, return failures to the UI and verify results. Upstream relies on `/tmp/.inputplumber.state` for mode deduplication and catches several apply errors only in logs. Do not present cached desired state as successful hardware state.
6. Preserve source mappings and configuration fields. Upstream combined profiles contain version/kind/name/mapping; verify whether additional base-profile fields must survive. Define conflicts between multiple custom profiles rather than merely concatenating them.
7. Keep startup read-only until the user opts into profile automation. Avoid simultaneous automatic writers from this project and DeckyPlumber; design conflict detection and a clear handoff.
8. Implement a tested restore path before automatic game switching. Existing install/reboot and possible EC recovery limitations remain unresolved. No automatic EC reset, firmware changes, or unconditional service restart.

## Proposed milestones and acceptance

1. **Hardware controls + discovery:** port current controls, retain Chinese/English, expose read-only service/device/capability diagnostics. Simulated tests plus A8 check that opening/closing the panel leaves input and hardware unchanged.
2. **Manual virtual targets:** capability-gated choices, snapshot/restore, verified errors. Test input, Guide/QAM, M1/M2, rumble, external-controller coexistence and return to original mode. Restore must work without relying solely on the affected gamepad UI.
3. **A8 button mappings:** independent back buttons where events exist; optional menu swap; base-profile preservation; conflict detection. Test with each hardware M-key mode before declaring support.
4. **Optional per-game profiles:** explicitly enable, restore global state on leaving a game, prevent racing writes and repeated hotplug. Test launch/exit, sleep/wake and Decky reload.
5. **Separate experiments:** gyro controls and stick/trigger tuning only after verifying relevant APIs and hardware behavior. Not promised for the first release.

No implementation or release is included in this research milestone.

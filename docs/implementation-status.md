# Initial implementation status

2026-11-08, development version 0.1.0-alpha.1. This is a reviewable implementation, not a device-validated release or a replacement installation recommendation.

Implemented: independent versioned default/game/template storage; strict embedded A8 discovery; serialized sysfs writes; finite 500 ms physical-device rumble test; capability-gated InputPlumber discovery, fixed Elite activation, durable recovery snapshot and terminal restore; English/Chinese quick panel and settings pages; independent copying and per-game selection; explicit save-versus-apply error handling.

Still pending: production installer, updates and clean uninstall/reinstall; distribution licensing package; multi-output and combined-template editing/conflict preview UI; built-in presets; complete outer-navigation draft protection; validated multi-game identification and sleep/restart recovery. The current editor supports one output per source; the backend validates up to four. Axes pass through and Guide/QAM remain protected.

Device discovery deliberately pins the upstream MS-1T8K internal USB topology. Unknown topologies and missing interfaces are rejected. This may need adjustment from actual A8 diagnostics; it must not be widened to arbitrary controllers. Missing PyYAML/profile-readback/target APIs disable mapping management. Missing physical FF_RUMBLE support disables the rumble test.

Unexpected post-wake/external device state pauses management and requires explicit restore and reactivation; full automatic recovery is not claimed. Actual hardware source events, labels, rumble behavior, held-button transitions, external-controller coexistence and restoration require A8 testing.

See the [Chinese status](../implementation-status.zh-CN.md) for details and README for development tests and explicit terminal recovery. Preserve the recovery snapshot until restoration succeeds.

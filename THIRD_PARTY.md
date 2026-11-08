# Source provenance and planned reuse

Implementation provenance: `backend/hardware.py` derives from the existing v1.0.1 MIT sysfs discovery/read/write implementation, expanded with board/topology checks. Full original notice is retained in `third_party/hardware-controls-MIT.txt`. Build configuration and dependency lockfile also originate from that project.

| Source | Reviewed revision | Declared license | Role |
| --- | --- | --- | --- |
| [sekirofly/msi-claw-a8-back-buttons-rumble](https://github.com/sekirofly/msi-claw-a8-back-buttons-rumble) | v1.0.1 / 5f5dea3667e8dab47fe48aa83c65bebf7a9c2a38 | MIT, copyright 2026 sekirofly | Hardware-control baseline; MIT notice retained. |
| [aarron-lee/DeckyPlumber](https://github.com/aarron-lee/DeckyPlumber) | cebd2fcab2f6bc17968d1d4c4bf8cb9fa992b3a5 | GPL v3 license text; package identifies GPL V3.0 | Research reference and possible future reuse; preserve upstream attribution/notices and distribute corresponding source for derived releases. |
| [ShadowBlip/InputPlumber](https://github.com/ShadowBlip/InputPlumber) | 6aca9202fb8dfd6f31241c3f98b72df4a775c1a1 | See upstream license | External service/API and hardware capability research; not bundled. |

Project license choice: GPL-3.0-only. The GNU GPL v3 text in LICENSE is the standard license text, copied from the reviewed DeckyPlumber LICENSE. This does not imply upstream endorsement. DeckyPlumber is an architectural and API usage reference; its shared-profile store and UI were not copied into this implementation.

Before importing source, record source paths/revisions and preserve each applicable copyright/license notice. Audit Decky API/UI and other dependency requirements when dependencies are introduced. Existing MIT code retains its MIT notice within any GPL-distributed combined work.

Frontend dependency: `@decky/api` 1.1.3 is LGPL-2.1. `scripts/package.py` includes its source/license and this project's rebuildable sources in the CI development archive. React and UI are provided by Decky at runtime. This is a development artifact, not a production installer. Audit any additional dependencies before distribution.

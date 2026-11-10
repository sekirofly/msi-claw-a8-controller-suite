# Implementation status

**v0.1.0** is the first stable release. See the [README](../README.md) for current behavior and operation.

Implemented: independent default/game configurations keyed by Steam IDs; copy isolation; verified internal-A8 discovery; Elite management and installed-system-default restoration; hardware mode/rumble controls; finite physical rumble testing; repair/reinstall/uninstall; bounded logs and event-first game tracking.

The user has validated the UI and core behavior on an A8. Automated checks cover configuration isolation, hardware gates, restoration, installation rollback, maintenance resets, asynchronous UI and focus behavior. Mock tests do not establish compatibility with every Steam/kernel release or quantify power savings.

The editor supports one output per source; the backend retains compatibility with existing multi-output mappings. Other Claw models are outside the supported scope.

[Historical implementation notes](history/implementation-status.md) remain available. Design, integration and research documents are historical references; the README describes current behavior.

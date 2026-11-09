#!/usr/bin/env bash
set -euo pipefail
task_dir=$(mktemp -d)
trap 'rm -rf -- "$task_dir"' EXIT
curl --fail --location --proto '=https' --tlsv1.2 \
  https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/v0.1.0-alpha.19/installer.py \
  --output "$task_dir/installer.py"
python3 "$task_dir/installer.py" "$@"


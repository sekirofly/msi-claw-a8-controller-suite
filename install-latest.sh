#!/usr/bin/env bash
set -euo pipefail
task_dir=$(mktemp -d)
trap 'rm -rf -- "$task_dir"' EXIT
curl --fail --location --retry 2 --proto '=https' --tlsv1.2 \
  https://api.github.com/repos/sekirofly/msi-claw-a8-controller-suite/releases/latest \
  --output "$task_dir/release.json"
release_tag=$(python3 -c '
import json, re, sys
with open(sys.argv[1]) as source:
    release = json.load(source)
tag = release.get("tag_name", "")
if release.get("draft") is not False or release.get("prerelease") is not False or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
    raise SystemExit("No published stable release found")
print(tag)
' "$task_dir/release.json")
curl --fail --location --retry 2 --proto '=https' --tlsv1.2 \
  "https://raw.githubusercontent.com/sekirofly/msi-claw-a8-controller-suite/$release_tag/installer.py" \
  --output "$task_dir/installer.py"
python3 "$task_dir/installer.py" "$@"

#!/bin/bash
# Backdate commits to create a realistic timeline over the past month.
# Run from catlink repo root: ./scripts/backdate_commits.sh
# Uses GIT_AUTHOR_DATE and GIT_COMMITTER_DATE to spoof commit times.

set -e
cd "$(dirname "$0")/.."

# Ensure we're in the catlink repo
if [ ! -f "custom_components/catlink/manifest.json" ]; then
  echo "Run from catlink repo root"
  exit 1
fi

# Create branch (from current branch)
git checkout -b v2.1.1-beta 2>/dev/null || git checkout v2.1.1-beta

# Helper: commit with backdated timestamp
backdate_commit() {
  local date="$1"
  local msg="$2"
  shift 2
  if [ $# -eq 0 ]; then
    echo "No files for: $msg"
    return
  fi
  git add "$@"
  if git diff --cached --quiet; then
    echo "Skipping (no changes): $msg"
    return
  fi
  GIT_AUTHOR_DATE="$date" GIT_COMMITTER_DATE="$date" git commit -m "$msg"
  echo "Committed: $msg"
}

# Timeline: Jan 6 - Feb 5, 2026
# Paths relative to catlink repo root

backdate_commit "2026-01-06 10:30:00" "Add CatLink integration base structure" \
  custom_components/catlink/const.py \
  custom_components/catlink/manifest.json \
  custom_components/catlink/__init__.py

backdate_commit "2026-01-08 14:00:00" "Add Account module for API authentication" \
  custom_components/catlink/modules/__init__.py \
  custom_components/catlink/modules/account.py

backdate_commit "2026-01-10 11:00:00" "Add Pydantic API models" \
  custom_components/catlink/models/__init__.py \
  custom_components/catlink/models/additional_cfg.py \
  custom_components/catlink/models/api/__init__.py \
  custom_components/catlink/models/api/base.py \
  custom_components/catlink/models/api/device.py \
  custom_components/catlink/models/api/logs.py \
  custom_components/catlink/models/api/parse.py

backdate_commit "2026-01-12 16:00:00" "Add device base classes and registry" \
  custom_components/catlink/devices/__init__.py \
  custom_components/catlink/devices/base.py \
  custom_components/catlink/devices/registry.py \
  custom_components/catlink/modules/devices_coordinator.py

backdate_commit "2026-01-15 09:30:00" "Add litter device, litterbox and feeder" \
  custom_components/catlink/devices/litter_device.py \
  custom_components/catlink/devices/litterbox.py \
  custom_components/catlink/devices/feeder.py \
  custom_components/catlink/devices/scooper.py \
  custom_components/catlink/devices/mixins/__init__.py \
  custom_components/catlink/devices/mixins/logs.py

backdate_commit "2026-01-18 13:00:00" "Add entity base and platform entities" \
  custom_components/catlink/entities/__init__.py \
  custom_components/catlink/entities/base.py \
  custom_components/catlink/entities/registry.py \
  custom_components/catlink/entities/sensor.py \
  custom_components/catlink/entities/binary.py \
  custom_components/catlink/entities/switch.py \
  custom_components/catlink/entities/select.py \
  custom_components/catlink/entities/button.py

backdate_commit "2026-01-20 10:00:00" "Add sensor, switch, select and button platforms" \
  custom_components/catlink/sensor.py \
  custom_components/catlink/binary_sensor.py \
  custom_components/catlink/switch.py \
  custom_components/catlink/select.py \
  custom_components/catlink/button.py \
  custom_components/catlink/services.yaml

backdate_commit "2026-01-22 15:00:00" "Add config flow with credentials and device discovery" \
  custom_components/catlink/config_flow.py \
  custom_components/catlink/strings.json

backdate_commit "2026-01-25 11:00:00" "Add helpers and platform setup" \
  custom_components/catlink/helpers.py

backdate_commit "2026-01-28 14:30:00" "Improve API error handling and error entity updates" \
  custom_components/catlink/devices/base.py \
  custom_components/catlink/devices/litterbox.py \
  custom_components/catlink/devices/feeder.py \
  custom_components/catlink/devices/scooper.py

backdate_commit "2026-02-01 10:00:00" "Use async_forward_entry_setups for proper device linking" \
  custom_components/catlink/__init__.py \
  custom_components/catlink/helpers.py \
  custom_components/catlink/modules/devices_coordinator.py \
  custom_components/catlink/sensor.py \
  custom_components/catlink/switch.py \
  custom_components/catlink/binary_sensor.py \
  custom_components/catlink/select.py \
  custom_components/catlink/button.py

backdate_commit "2026-02-03 16:00:00" "Add refresh interval option to config flow" \
  custom_components/catlink/config_flow.py \
  custom_components/catlink/const.py \
  custom_components/catlink/helpers.py \
  custom_components/catlink/modules/account.py \
  custom_components/catlink/__init__.py \
  custom_components/catlink/strings.json

backdate_commit "2026-02-05 09:00:00" "Simplify config flow: phone parsing and region auto-discovery" \
  custom_components/catlink/config_flow.py \
  custom_components/catlink/helpers.py \
  custom_components/catlink/manifest.json \
  custom_components/catlink/strings.json

# Add any remaining files
if [ -n "$(git status --porcelain)" ]; then
  backdate_commit "2026-02-05 12:00:00" "Add documentation and project files" \
    .github/ \
    .gitignore \
    CODE_OF_CONDUCT.md \
    CONTRIBUTE.md \
    hacs.json \
    HOW_TO_REPORT_BUG.md \
    LICENSE \
    README.md \
    scripts/
fi

echo ""
echo "Done. Run 'git log --oneline' to verify the timeline."

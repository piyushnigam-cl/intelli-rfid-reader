#!/usr/bin/env bash
#
# Initialises a git repository for the workspace and each app, and points them at AWS CodeCommit.
#
# Five repositories, deliberately separate:
#   intelli-rfid-workspace   this directory — shared docs only (CLAUDE.md, HANDOVER.md, README.md)
#   intelli-rfid-core        apps/intelli-rfid-core
#   intelli-rfid-reader-test apps/intelli-rfid-reader-test
#   intelli-rfid-tunnel      apps/intelli-rfid-tunnel
#   intelli-rfid-wayside     apps/intelli-rfid-wayside
#
# The workspace repo ignores apps/ entirely, so this is not a monorepo — each app stays
# independently versioned and independently shippable.
#
# This script does NOT push. Review the commits first, then push with the printed commands.
#
# Usage:
#   ./setup-codecommit.sh                      # region from AWS_REGION, or ap-south-1
#   AWS_REGION=ap-south-1 ./setup-codecommit.sh
#   ./setup-codecommit.sh --create             # also create the CodeCommit repositories
#
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
CREATE=false
[[ "${1:-}" == "--create" ]] && CREATE=true

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# "name:relative-path" — "." is the workspace itself
TARGETS=(
  "intelli-rfid-workspace:."
  "intelli-rfid-core:apps/intelli-rfid-core"
  "intelli-rfid-reader-test:apps/intelli-rfid-reader-test"
  "intelli-rfid-tunnel:apps/intelli-rfid-tunnel"
  "intelli-rfid-wayside:apps/intelli-rfid-wayside"
)

echo "Region: $REGION"
echo

for entry in "${TARGETS[@]}"; do
  name="${entry%%:*}"
  rel="${entry#*:}"
  dir="$HERE/$rel"

  if [[ ! -d "$dir" ]]; then
    echo "skip  $name (no directory at $rel)"
    continue
  fi

  cd "$dir"

  if [[ -d .git ]]; then
    echo "ok    $name already a git repository"
  else
    git init -q -b main
    git add -A
    git commit -q -m "Initial commit: $name

Scaffolded against the Silion ModuleAPI_J SDK (SIM7500 / Impinj E710),
targeting a Raspberry Pi CM4 on board the reader."
    echo "init  $name ($(git rev-list --count HEAD) commit)"
  fi

  url="https://git-codecommit.$REGION.amazonaws.com/v1/repos/$name"

  if $CREATE; then
    if aws codecommit get-repository --repository-name "$name" --region "$REGION" >/dev/null 2>&1; then
      echo "      repository already exists in CodeCommit"
    else
      aws codecommit create-repository \
        --repository-name "$name" \
        --repository-description "Intelli RFID: $name" \
        --region "$REGION" >/dev/null
      echo "      created CodeCommit repository"
    fi
  fi

  if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "$url"
  else
    git remote add origin "$url"
  fi
  echo "      origin -> $url"
  echo
done

cat <<NOTE
Nothing has been pushed. Review each commit, then:

  cd "$HERE" && git push -u origin main
  for app in intelli-rfid-core intelli-rfid-reader-test intelli-rfid-tunnel intelli-rfid-wayside; do
    (cd "$HERE/apps/\$app" && git push -u origin main)
  done

Credential setup, if you have not done it on this machine:

  # HTTPS with the AWS CLI credential helper (simplest)
  git config --global credential.helper '!aws codecommit credential-helper \$@'
  git config --global credential.UseHttpPath true

  # or HTTPS Git credentials from IAM (no AWS CLI needed at push time)
  # IAM console -> your user -> Security credentials -> HTTPS Git credentials for CodeCommit

Repositories are NOT created unless you pass --create.
NOTE

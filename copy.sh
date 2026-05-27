#!/usr/bin/env bash
# Usage: ./copy.sh <source_dir> <destination_dir>

set -euo pipefail

SRC="${1:-}"
DST="${2:-}"

if [[ -z "$SRC" || -z "$DST" ]]; then
  echo "Usage: $0 <source_dir> <destination_dir>"
  exit 1
fi

if [[ ! -d "$SRC" ]]; then
  echo "Error: source directory '$SRC' does not exist."
  exit 1
fi

# Resolve absolute path for source
SRC="$(cd "$SRC" && pwd)"

echo "Copying from '$SRC' to '$DST' (excluding .nc files)..."

rsync -av \
  --exclude='*.nc' \
  --filter='protect *.nc' \
  "$SRC/" "$DST/"

echo "Done."
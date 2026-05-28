#!/bin/bash
# ===========================================
# Script to run FBMC
# ===========================================
set -euo pipefail

MAPPING_FILE="${1:-config/run_node_mapping.json}"

if [[ ! -f "$MAPPING_FILE" ]]; then
	echo "Mapping file not found: $MAPPING_FILE" >&2
	exit 1
fi

mapfile -t RUN_ASSIGNMENTS < <(python - "$MAPPING_FILE" <<'PY'
import json
import sys

mapping_path = sys.argv[1]
with open(mapping_path, encoding="utf-8") as f:
	mapping = json.load(f)

if not isinstance(mapping, dict) or not mapping:
	raise SystemExit("Mapping JSON must be a non-empty object of {run_name: node_name}.")

for run_name, node_name in mapping.items():
	if not isinstance(run_name, str) or not run_name.strip():
		raise SystemExit("Each run name must be a non-empty string.")
	if not isinstance(node_name, str) or not node_name.strip():
		raise SystemExit(f"Node for run '{run_name}' must be a non-empty string.")
	print(f"{run_name}\t{node_name}")
PY
)

if [[ ${#RUN_ASSIGNMENTS[@]} -eq 0 ]]; then
	echo "No run assignments found in $MAPPING_FILE" >&2
	exit 1
fi

declare -a PIDS=()
declare -a LABELS=()

for assignment in "${RUN_ASSIGNMENTS[@]}"; do
	IFS=$'\t' read -r run_name node_name <<< "$assignment"

	echo "Starting run '$run_name' on '$node_name'"
	ssh "$node_name" "set -euo pipefail; cd pypsa-fbmc; bash setup.sh; git stash; source prepare.sh; python -m scripts.run.ua_coupling -r '$run_name'" &

	PIDS+=("$!")
	LABELS+=("$run_name@$node_name")
done

failures=0
for i in "${!PIDS[@]}"; do
	if wait "${PIDS[$i]}"; then
		echo "Completed ${LABELS[$i]}"
	else
		echo "Failed ${LABELS[$i]}" >&2
		failures=$((failures + 1))
	fi
done

if (( failures > 0 )); then
	echo "$failures run(s) failed." >&2
	exit 1
fi

echo "All runs completed successfully."


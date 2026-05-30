#!/bin/bash
# ===========================================
# Script to run FBMC
# ===========================================
set -euo pipefail

VERSION="${1:-redload}"
RUN_ID="${2:-default}"
MAPPING_FILE="${3:-config/run_node_mapping.json}"

if [[ ! -f "$MAPPING_FILE" ]]; then
	echo "Mapping file not found: $MAPPING_FILE" >&2
	exit 1
fi

mapfile -t RUN_ASSIGNMENTS < <(python - "$MAPPING_FILE" <<'PY'
import io
import json
import sys

try:
	string_types = (basestring,)
except NameError:
	string_types = (str,)

mapping_path = sys.argv[1]
with io.open(mapping_path, "r", encoding="utf-8") as f:
	mapping = json.load(f)

if not isinstance(mapping, dict) or not mapping:
	raise SystemExit("Mapping JSON must be a non-empty object of {run_name: node_name}.")

for run_name, node_name in mapping.items():
	if not isinstance(run_name, string_types) or not run_name.strip():
		raise SystemExit("Each run name must be a non-empty string.")
	if not isinstance(node_name, string_types) or not node_name.strip():
		raise SystemExit("Node for run '{0}' must be a non-empty string.".format(run_name))
	sys.stdout.write("{0}\t{1}\n".format(run_name, node_name))
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
	ssh "$node_name" "RUN_NAME='$run_name' RUN_ID='$RUN_ID' VERSION='$VERSION' bash -lc 'set -euo pipefail; cd pypsa-fbmc; module load Python/3.11.5-GCCcore-13.2.0; module load gurobi/9.5; module load Miniconda3/23.10.0-1; source prepare.sh; python -m scripts.run.ua_coupling -r \"\$RUN_NAME\" -id \"\$RUN_ID\" -v \"\$VERSION\"'" &

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


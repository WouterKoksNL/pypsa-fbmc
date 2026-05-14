#!/bin/bash
# ===========================================
# Script to run FBMC
# ===========================================
set -e  # Exit immediately if any command fails
# --- USAGE ---
# bash run.sh
# --- CONFIG ---
module load Python/3.11.5-GCCcore-13.2.0
module load gurobi/9.5
module load Miniconda3/23.10.0-1
source .venv/bin/activate
git pull

# --- UPDATE PATHS ---
INPUT_DIR="/mnt/beegfs/users/wouterko/fbmc/input"
UNPROCESSED_DIR="/mnt/beegfs/users/wouterko/fbmc/input"

sed -i "s|input_networks_dir = \".*\"|input_networks_dir = \"$INPUT_DIR\"|" paths.toml
sed -i "s|unprocessed_input_networks_dir = \".*\"|unprocessed_input_networks_dir = \"$UNPROCESSED_DIR\"|" paths.toml

python main.py
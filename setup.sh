#!/bin/bash

# Setup virtual env on cluster

module load Python/3.11.5-GCCcore-13.2.0
python -m venv .venv
pip install -r requirements.txt
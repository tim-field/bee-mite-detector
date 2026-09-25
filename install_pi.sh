#!/usr/bin/env bash
# User-local installation; does not upgrade drivers or install system packages.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
source ./setup_env.sh

# Use the API generation this application's detection.py was written against.
# Its upstream setup.py compiles redundant C++ plugins, downloads all models,
# and pins NumPy <2 (incompatible with Python 3.13). Use only the Python helpers;
# the postprocessor and NumPy/OpenCV come from Raspberry Pi OS instead.
infra_commit=4e428ccdcbcde1e91c85beca3334b1073e8c9c8f # upstream tag 25.3.1
infra_dir="$PWD/.deps/hailo-apps-infra"
if [[ ! -e "$infra_dir" ]]; then
    mkdir -p .deps
    git clone --depth 1 --branch 25.3.1 https://github.com/hailo-ai/hailo-apps-infra.git "$infra_dir"
fi
if [[ "$(git -C "$infra_dir" rev-parse HEAD)" != "$infra_commit" ]]; then
    echo "Unexpected Hailo helper revision in $infra_dir; refusing to overwrite it." >&2
    exit 1
fi
python -m pip install -r requirements-pi.txt
source ./setup_env.sh
python -c 'import flask, setproctitle, picamera2; from hailo_apps_infra.detection_pipeline import GStreamerDetectionApp; print("Application imports OK")'
echo "Installation complete. Run: source setup_env.sh && python app.py"

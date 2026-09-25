#!/usr/bin/env bash
# Source this file from Bash. System Hailo/camera packages remain managed by apt.
if [[ -z "${BASH_VERSION:-}" ]]; then
    echo "Please use Bash: bash, then source setup_env.sh" >&2
    return 1
fi
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "Run: source setup_env.sh (do not execute this script)." >&2
    exit 1
fi

_bee_setup_env() {
    local project_dir venv_dir postproc_dir identification arch infra_dir
    project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || return 1
    venv_dir="$project_dir/.venv"
    infra_dir="$project_dir/.deps/hailo-apps-infra"

    if ! pkg-config --exists hailo-tappas-core; then
        echo "Missing hailo-tappas-core. Install the Raspberry Pi Hailo packages first." >&2
        return 1
    fi
    postproc_dir="$(pkg-config --variable=tappas_postproc_lib_dir hailo-tappas-core)"
    if [[ ! -f "$postproc_dir/libyolo_hailortpp_post.so" ]]; then
        echo "Missing YOLO postprocessor in $postproc_dir" >&2
        return 1
    fi
    if [[ ! -x "$venv_dir/bin/python" ]]; then
        python3 -m venv --system-site-packages "$venv_dir" || return 1
    fi
    # Do not activate the non-portable virtualenv committed by the original author.
    source "$venv_dir/bin/activate" || return 1
    python -c 'import gi, hailo, hailo_platform, cv2, numpy' || {
        echo "Missing system Python bindings; see docs/raspberry-pi-setup.md." >&2
        return 1
    }
    identification="$(hailortcli fw-control identify | tr -d '\000')" || return 1
    arch="$(printf '%s\n' "$identification" | awk -F': ' '/Device Architecture/ {print $2}')"
    if [[ "$arch" != HAILO8 && "$arch" != HAILO8L ]]; then
        echo "Unsupported or unavailable accelerator: $arch (this HEF requires Hailo-8/8L)." >&2
        return 1
    fi
    export TAPPAS_POST_PROC_DIR="$postproc_dir"
    export DEVICE_ARCHITECTURE="$arch"
    if [[ -d "$infra_dir/hailo_apps_infra" ]]; then
        case ":${PYTHONPATH:-}:" in
            *":$infra_dir:"*) ;;
            *) export PYTHONPATH="$infra_dir${PYTHONPATH:+:$PYTHONPATH}" ;;
        esac
    else
        echo "Hailo application helpers not installed yet. Run: bash install_pi.sh"
    fi
    echo "Environment: $venv_dir"
    echo "TAPPAS: $(pkg-config --modversion hailo-tappas-core); accelerator: $arch"
}
_bee_setup_env
_bee_setup_result=$?
unset -f _bee_setup_env
return "$_bee_setup_result"

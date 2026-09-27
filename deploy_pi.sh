#!/usr/bin/env bash
# Deploy this checkout to the working Raspberry Pi over SSH.
#
# Formalises the handoff procedure ("copying selected working files with scp"):
# syncs working-tree files with rsync (never --delete) while preserving the Pi's
# live state: .venv/, .deps/, *.log, SQLite history (*.db), and camera captures.
# The tracked example bee_health.db is never copied; the Pi keeps its own history.
#
# No sudo, no driver/firmware changes, no pip installs, no email credentials.
# See docs/agent-handoff.md and docs/raspberry-pi-setup.md before use.
#
# Usage:
#   bash deploy_pi.sh [options]
#   PI_SSH=tim@192.168.8.219 PI_DIR=/home/tim/bee-mite-detector bash deploy_pi.sh
#
# Options:
#   -n, --dry-run        validate + show what would change, deploy nothing
#       --check-only     alias for --dry-run
#       --no-restart     never restart the bee-mite-detector user unit
#       --restart        always restart the unit (default: restart only when
#                        runtime files changed)
#       --force          deploy even while detection is active (default: abort;
#                        only one camera consumer may run at a time)
#       --skip-hef       skip the 10MB first_15k.hef model file (use when it is
#                        known-unchanged on a slow link)
#       --remote-tests   run the hardware-independent unittest suite on the Pi
#                        after syncing (uses a temp DB, leaves production DB alone)
#   -h, --help           show this help

set -euo pipefail

PI_SSH="${PI_SSH:-tim@192.168.8.219}"
PI_DIR="${PI_DIR:-/home/tim/bee-mite-detector}"
PI_WEB_URL="${PI_WEB_URL:-http://192.168.8.219:5000}"
UNIT="${UNIT:-bee-mite-detector}"

DRY_RUN=0
FORCE=0
SKIP_HEF=0
REMOTE_TESTS=0
RESTART_MODE="auto" # auto | always | never

usage() {
    sed -n '2,/^$/p' -- "$0" | sed 's/^# \{0,1\}//'
    echo "Defaults: PI_SSH=$PI_SSH PI_DIR=$PI_DIR PI_WEB_URL=$PI_WEB_URL"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--dry-run|--check-only) DRY_RUN=1; shift ;;
        --no-restart) RESTART_MODE="never"; shift ;;
        --restart) RESTART_MODE="always"; shift ;;
        --force) FORCE=1; shift ;;
        --skip-hef) SKIP_HEF=1; shift ;;
        --remote-tests) REMOTE_TESTS=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1 (see --help)" >&2; exit 2 ;;
    esac
done

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$PROJECT_DIR"

log() { printf '%s\n' "$*"; }
die() { printf 'deploy_pi: %s\n' "$*" >&2; exit 1; }

command -v rsync >/dev/null || die "rsync is required locally."
command -v ssh >/dev/null || die "ssh is required."
command -v curl >/dev/null || die "curl is required for pre/post checks."
[[ -f app.py && -f detection.py && -f setup_env.sh && -f install_pi.sh ]] \
    || die "run from the bee-mite-detector checkout."

# --- Local validation -------------------------------------------------------
log "==> Local checks"
git diff --check || die "git diff --check failed; fix whitespace errors first."
bash -n setup_env.sh || die "setup_env.sh has a syntax error."
bash -n install_pi.sh || die "install_pi.sh has a syntax error."
bash -n deploy_pi.sh || die "deploy_pi.sh has a syntax error."
python3 -m py_compile app.py bee_health_db.py detection.py email_service.py \
    tests/test_runtime.py \
    || die "Python compilation failed."
# Scan the working tree only (never .git history, vendored helpers, or this
# script's own pattern text): email must stay opt-in, no hard-coded secrets.
if grep -rn --exclude-dir=.git --exclude-dir=.deps --exclude-dir=.venv \
        --exclude-dir=venv_hailo_rpi5_examples --exclude-dir=node_modules \
        --include='*.py' --include='*.sh' --include='*.md' \
        -E 'BEE_MONITOR_EMAIL(_PASSWORD)?=.+|BEE_MONITOR_EMAIL_RECIPIENT=.+' . 2>/dev/null \
        | grep -v '^\./deploy_pi\.sh:' \
        | grep -v 'os.environ.get' \
        | grep -vE 'Check BEE_MONITOR|explicitly exported|BEE_MONITOR_EMAIL.", ' \
        | grep -q .; then
    die "possible hard-coded email credential; email must stay opt-in (see handoff)."
fi
if [[ -n "$(git status --short)" ]]; then
    log "NOTE: working tree has uncommitted changes (they will deploy as-is):"
    git status --short
fi

# --- Pi connectivity + runtime state (recheck, never assume) -----------------
log "==> Checking Pi connectivity ($PI_SSH)"
ssh -o ConnectTimeout=10 -o BatchMode=yes "$PI_SSH" 'echo SSH_OK' \
    | grep -q SSH_OK || die "SSH to $PI_SSH failed (key access required)."
ssh -o ConnectTimeout=10 "$PI_SSH" "test -d '$PI_DIR'" \
    || die "remote dir $PI_DIR not found on $PI_SSH."

ACTIVE=""
if STATS="$(curl -fsS -m 8 "$PI_WEB_URL/get_stats" 2>/dev/null)"; then
    ACTIVE="$(printf '%s' "$STATS" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("active", ""))' 2>/dev/null || true)"
    log "Dashboard $PI_WEB_URL/get_stats reachable; detection active: ${ACTIVE:-unknown}"
    if [[ "$ACTIVE" == "True" && "$FORCE" -eq 0 && "$DRY_RUN" -eq 0 ]]; then
        die "detection is ACTIVE; stop it first (dashboard Stop button or POST /stop_detection) or re-run with --force."
    fi
else
    log "NOTE: dashboard not reachable at $PI_WEB_URL (server may be stopped); continuing."
fi
REMOTE_UNIT_STATE="$(ssh -o ConnectTimeout=10 "$PI_SSH" "systemctl --user is-active '$UNIT' 2>&1" || true)"
log "Remote unit $UNIT state: $REMOTE_UNIT_STATE"

# --- Sync (no --delete: preserve .venv, .deps, logs, SQLite history) ---------
# Excludes: runtime state + history + local-only/dev artefacts. The tracked
# example bee_health.db, logs, captures, venvs, .git and secrets never sync.
EXCLUDES=(
    --exclude='.git/'
    --exclude='.venv/'
    --exclude='.deps/'
    --exclude='__pycache__/'
    --exclude='*.pyc'
    --exclude='*.pyo'
    --exclude='*.log'
    --exclude='*.db'
    --exclude='*.db-journal'
    --exclude='*.db-wal'
    --exclude='*.db-shm'
    --exclude='camera-check.jpg'
    --exclude='.vscode/'
    --exclude='venv_hailo_rpi5_examples/'
    --exclude='node_modules/'
    --exclude='.pytest_cache/'
    --exclude='.hypothesis/'
    --exclude='.coverage*'
    --exclude='htmlcov/'
    --exclude='docs/001252261-FYP_Report.pdf'
    --exclude='docs/images/'
    --exclude='.env'
    --exclude='.env.*'
    --exclude='.DS_Store'
    --exclude='*.egg-info/'
    --exclude='dist/'
    --exclude='build/'
)
if [[ "$SKIP_HEF" -eq 1 ]]; then
    EXCLUDES+=(--exclude='first_15k.hef')
fi

# --checksum: the Pi's files were originally copied with scp, so mtimes differ
# even when content is identical. Checksums avoid spurious re-transfers and
# spurious server restarts; only real content changes trigger a restart.
RSYNC_OPTS=(-azh --checksum --itemize-changes --compress --omit-dir-times)
if [[ "$DRY_RUN" -eq 1 ]]; then
    RSYNC_OPTS+=(--dry-run)
fi

log "==> Syncing to $PI_SSH:$PI_DIR/ (no --delete)"
RSYNC_OUT="$(rsync "${RSYNC_OPTS[@]}" "${EXCLUDES[@]}" \
    ./ "$PI_SSH:$PI_DIR/" 2>&1)"
printf '%s\n' "$RSYNC_OUT" | grep -vE ' \./$' || true

if [[ "$DRY_RUN" -eq 1 ]]; then
    log "Dry run complete; nothing changed on the Pi."
    exit 0
fi

# --- Remote validation ------------------------------------------------------
log "==> Remote validation"
ssh -o ConnectTimeout=15 "$PI_SSH" "cd '$PI_DIR' && bash -n setup_env.sh && bash -n install_pi.sh && python3 -m py_compile app.py bee_health_db.py detection.py email_service.py" \
    || die "remote validation failed."
if [[ "$REMOTE_TESTS" -eq 1 ]]; then
    log "Running hardware-independent tests on the Pi (temp DB; production DB untouched)..."
    ssh -o ConnectTimeout=15 "$PI_SSH" "cd '$PI_DIR' && source ./setup_env.sh && python -m unittest tests.test_runtime" \
        || die "remote tests failed."
fi

# --- Restart if runtime files changed ---------------------------------------
# Docs/README-only changes do not need a server restart. Accept both rsync's
# '>' and the macOS openrsync '<' direction markers. New test-only files or
# install_pi.sh alone never force a restart.
RUNTIME_CHANGED=0
if printf '%s\n' "$RSYNC_OUT" | grep -qE '^[<>]f[^ ]* (app\.py|detection\.py|bee_health_db\.py|email_service\.py|setup_env\.sh|requirements-pi\.txt|labels\.json|first_15k\.hef|templates/|static/)'; then
    RUNTIME_CHANGED=1
fi

SHOULD_RESTART=0
case "$RESTART_MODE" in
    always) SHOULD_RESTART=1 ;;
    never) SHOULD_RESTART=0 ;;
    auto) [[ "$RUNTIME_CHANGED" -eq 1 ]] && SHOULD_RESTART=1 ;;
esac

if [[ "$SHOULD_RESTART" -eq 0 ]]; then
    log "No restart requested (mode=$RESTART_MODE, runtime files changed: $RUNTIME_CHANGED)."
    log "Done. Dashboard: $PI_WEB_URL"
    exit 0
fi

log "==> Restarting $UNIT on the Pi"
if ssh -o ConnectTimeout=15 "$PI_SSH" "systemctl --user restart '$UNIT'"; then
    sleep 4
    ssh -o ConnectTimeout=10 "$PI_SSH" "systemctl --user is-active '$UNIT'" \
        || die "unit $UNIT is not active after restart; inspect: ssh $PI_SSH 'tail -n 50 $PI_DIR/app.log'."
    for _ in 1 2 3 4 5 6; do
        if curl -fsS -m 8 "$PI_WEB_URL/get_stats" >/dev/null 2>&1; then
            log "Dashboard healthy: $PI_WEB_URL (error field should be null when idle)."
            curl -fsS -m 8 "$PI_WEB_URL/get_stats" | head -c 400; echo
            log "Done."
            exit 0
        fi
        sleep 3
    done
    die "unit restarted but dashboard did not answer at $PI_WEB_URL/get_stats."
else
    cat >&2 <<EOF
deploy_pi: unit $UNIT could not be restarted (it is transient and may be gone
after a reboot). Start it manually per docs/raspberry-pi-setup.md:

  ssh $PI_SSH
  cd $PI_DIR
  systemd-run --user --unit=$UNIT \\
    --working-directory="\$HOME/bee-mite-detector" \\
    --property="StandardOutput=append:\$HOME/bee-mite-detector/app.log" \\
    --property="StandardError=append:\$HOME/bee-mite-detector/app.log" \\
    /bin/bash -c 'source ./setup_env.sh && exec python -u app.py'

Files were synced; the server was NOT restarted.
EOF
    exit 1
fi

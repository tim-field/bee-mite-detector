# Agent handoff: working Raspberry Pi varroa detector

> **Training continuation:** the user has completed manual curation and exported
> `training-artifacts/image-review/exports/bee-v14-entrance-v2` on the Mac
> (277 training / 14 validation images). No training on this export has started.
> Read the latest checkpoint at the top of [`training-handoff.md`](training-handoff.md)
> for exact state and next steps, plus the earlier RTX 3060 Ti / WSL2 baseline.
> The Pi deployment described below is unchanged.

## User intent and constraints

The user is replicating this project using a Raspberry Pi, an IMX477 HQ camera,
and a newer Hailo accelerator. Initial goal: get the README's application working.
That goal has been operationally demonstrated. The user subsequently wants to
**discuss training their own model**. Possible follow-ups include browser video
preview and boot-time startup, but neither has been requested for implementation
yet. Ask what they want next.

The user subsequently **authorized commits** of the setup work, grouped by logical
fix. The earlier no-commits instruction is no longer applicable. See `git log` for
the resulting commits; nothing has been pushed. Preserve unrelated user files.

## Where things live

- Mac development checkout: `/Users/tim/dev/bee-mite-detector`.
- Git origin: `git@github.com:tim-field/bee-mite-detector.git`.
- Pi: `ssh tim@192.168.8.219` (key-based access worked).
- Pi deployment: `/home/tim/bee-mite-detector`.
- Dashboard: `http://192.168.8.219:5000`.
- Detailed installation/use guide: [`raspberry-pi-setup.md`](raspberry-pi-setup.md).

The remote deployment was created by **copying selected working files with scp**,
not by cloning this fork. Do not assume it has Git history or that local edits are
automatically deployed. The remote `.deps/hailo-apps-infra` is a separate upstream
Git clone. Avoid `rsync --delete`; preserve remote `.venv`, `.deps`, logs, and SQLite
history. The original repository's example `bee_health.db` was **not** copied to
the Pi; its database contains actual setup/test sessions.

The Pi requires a password for sudo; `sudo -n true` failed. No privileged package
changes, boot edits, or driver upgrades were performed by the agent.

## Verified platform

- Raspberry Pi 5, 64-bit Raspberry Pi OS / Debian **Trixie**.
- Python **3.13.5**.
- Accelerator identifies as **HAILO8**, not HAILO8L or Hailo-10.
- HailoRT / PCIe driver **4.23.0**; TAPPAS **5.1.0**.
- System NumPy **2.2.4**, OpenCV **4.10.0**.
- IMX477 HQ ribbon camera, configured on **CAM0**.
- Existing `/boot/firmware/config.txt` had `camera_auto_detect=0` and
  `dtoverlay=imx477,cam0`. Those settings were left unchanged.

Initially no camera was detected and the kernel showed a chip-ID read failure
with error `-121`. The user found a **loose ribbon cable**, reseated it, and rebooted.
The camera then enumerated and captured normally. Don't reopen this as a missing
camera-driver problem without checking the current evidence.

The installed GStreamer `libcamerasrc` plugin was absent. It is **not needed** for
this working pipeline: `--input rpi` uses Picamera2 feeding GStreamer appsrc.

## Model compatibility and limits

`first_15k.hef` is compiled for **HAILO8L**, with:

- RGB UINT8 NHWC input: **640 × 640 × 3**.
- Two-class YOLOv8 NMS output, network group `best`.
- Output `best/yolov8_nms_postprocess`.

It ran successfully on the Hailo-8. Hailo warns it will perform less well than a
native Hailo-8 compilation. A five-second accelerator-only test completed 538
frames (~107 FPS), but **that is not full application FPS or accuracy evidence**.
The full live-camera application consistently reported **~30 FPS**.

Keep `labels.json`'s background entry for the installed TAPPAS postprocessor;
there are still only two model classes (bee/varroa). Training/compiling a replacement
requires verifying class order, preprocessing, output format, and postprocessing.
No training checkpoint or ONNX source was found in the top-level checkout; the
HEF is a deployment artifact, not a practical fine-tuning starting point.

No detection accuracy evaluation on representative bees/mites was performed.
The camera scene during tests produced zero bee/varroa counts. Tracker IDs are
not guaranteed unique individual animals; the inherited infestation thresholds
are not validated colony-health recommendations. Zero bees now shows **Unknown**
risk rather than falsely asserting Low risk.

## Current runtime state (recheck)

At handoff:

- `systemctl --user is-active bee-mite-detector` returned `active`.
- Dashboard running; **detection stopped**; `/get_stats` reported `error: null`.
- Latest completed browser test processed 537 frames, approximately 30 FPS.
- The server runs as a **transient user systemd unit**, surviving SSH disconnects
  under the current session setup, but **not configured to start after reboot**.
- Logs: `/home/tim/bee-mite-detector/app.log`.
- `journalctl --user` had no accessible journal entries, so file logging was used.
- No email credentials/recipient are configured by this setup.

Quick checks:

```bash
ssh tim@192.168.8.219 'systemctl --user status bee-mite-detector --no-pager'
curl -fsS http://192.168.8.219:5000/get_stats
```

Start/stop **inference** through the UI or:

```bash
curl -fsS -X POST http://192.168.8.219:5000/start_detection
curl -fsS -X POST http://192.168.8.219:5000/stop_detection
```

Restart the existing server unit after deploying Python changes:

```bash
ssh tim@192.168.8.219 'systemctl --user restart bee-mite-detector'
```

If the unit no longer exists (e.g. after reboot), use the `systemd-run` command in
`raspberry-pi-setup.md`, or run interactively:

```bash
ssh tim@192.168.8.219
cd ~/bee-mite-detector
source setup_env.sh
python app.py
```

Only run one camera consumer/server at a time. Stop inference before separate
camera tests. The Flask server binds port 5000 with debug/reloader disabled. It is
**unauthenticated**: do not expose it to the public internet.

## Implemented changes

### Environment/dependency setup

- `setup_env.sh`: rewritten for Bash, resolves paths relative to itself, creates
  `.venv --system-site-packages`, checks native imports and accelerator, discovers
  TAPPAS postprocessing libraries with pkg-config. Replaces the obsolete exact
  3.30/3.31 version allowlist with required-capability checks.
- `install_pi.sh`: new user-local installer, no sudo or driver changes.
- `requirements-pi.txt`: Flask, python-dotenv, setproctitle.
- Hailo Python helpers pinned to upstream commit
  `4e428ccdcbcde1e91c85beca3334b1073e8c9c8f` (tag `25.3.1`) in
  `.deps/hailo-apps-infra`; `setup_env.sh` exports this via `PYTHONPATH`.
- Upstream helper `setup.py` is deliberately **not run**: it compiles redundant
  C++ postprocessors, downloads unrelated models, and pins NumPy <2, unsuitable
  for this Python 3.13 system. Native libraries come from the installed OS stack.
- The original tracked `venv_hailo_rpi5_examples/` was left untouched but is not
  used. Its activation scripts refer to the original author's machine.

### Application

- `detection.py`: subclasses the old Hailo helper to use the OS-matched
  `libyolo_hailortpp_post.so`; defaults to headless `fakesink`; guards missing
  frames and flushes callback output.
- `app.py`: removes `/home/ergi/...` paths; launches the active interpreter with
  unbuffered output and argument-list subprocess execution; defaults to `rpi`;
  merges/drains stderr; stops only its own process group instead of killing
  unrelated GStreamer processes or removing global IPC resources. Adds lifecycle
  locks, error/active fields in `/get_stats`, opt-in debug output, configurable DB
  and input/model paths, and disables the Flask debug reloader.
- The original dashboard has **no browser live-video stream**. It shows counts
  and charts. Optional separate Pi desktop preview: start the server from a
  desktop terminal with `BEE_VIDEO_SINK=autovideosink`. Don't force DISPLAY=:0 over
  SSH as the old code did.

### Email/security

The original `email_service.py` contained real-looking hard-coded Gmail credentials
and an author recipient, and attempted to send a summary automatically at session
end. They were discovered **after the first live start/stop test**, so that first
test may have attempted a notification. The user was informed. Its database row
had `email_sent=0`; no successful send was recorded. Do not claim proof that no
SMTP attempt occurred.

- Hard-coded credentials/recipient removed; now requires explicitly exported
  `BEE_MONITOR_EMAIL`, `BEE_MONITOR_EMAIL_PASSWORD`, and
  `BEE_MONITOR_EMAIL_RECIPIENT`.
- SMTP authentication debug logging disabled.
- Do not restore, reproduce in documentation, or use the published credentials.
  They still exist in upstream Git history; removing working-tree defaults does
  not revoke them or purge history.

### Documentation/tests

- Updated README points to `docs/raspberry-pi-setup.md` over its historical setup.
- `.gitignore` includes local dependency/runtime artifacts.
- `tests/test_runtime.py`: **9 hardware-independent unittest regression tests**.
- `AGENTS.md` and this handoff added for subsequent sessions.

Unrelated `.vscode/` appeared as an untracked directory during the session. It was
not created/edited by this agent; leave it alone. Inspect `git status`/diff before
new changes. The setup work has since been organized into local commits at the
user's request; no changes have been pushed.

## Validation performed

1. Device identification, HEF parsing, real accelerator-only inference.
2. `rpicam-still` capture after cable repair (remote `camera-check.jpg`).
3. Bounded direct camera → Hailo pipeline smoke test (remote `detection-smoke.log`).
4. Repeated HTTP start/stop/restart, live stats near 30 FPS, session/metric storage.
5. Chrome inspection of the dashboard and actual Start/Stop button interaction;
   charts/dependencies loaded and Active/Inactive state updated.
6. `python -m unittest tests.test_runtime`: **9 passed** on the Pi.
7. Bash syntax checks, Python compilation, and `git diff --check` passed.

Run the added tests on the Pi without touching its production DB:

```bash
cd ~/bee-mite-detector
source setup_env.sh
python -m unittest tests.test_runtime
bash -n setup_env.sh install_pi.sh
```

The **entire inherited test suite was not run**. Its tests include historical DB
assumptions and old process/thread mocks that may need updating for the safer
lifecycle. Do not describe the 9 new tests as validation of the entire suite.

## Suggested continuation

Ask the user which direction they want:

- **Custom model training discussion** (their stated next goal): obtain original
  weights/source if available, define camera geometry and required detections,
  collect representative local data, annotation/class definitions, hive/date-split
  evaluation, tiny-object resolution/lighting, and a Hailo-8 compilation path.
  Separate training accuracy from meaningful bee/infestation counting validation.
- **Live preview in the browser**: new feature; no stream endpoint exists yet.
- **Autostart/reliability**: persistent service, logging/rotation, health checks,
  camera failure handling, and long-duration testing. Avoid running multiple web
  workers against the same camera/global detection state.
- **Detection validation**: focus/lighting, representative images or video, labels,
  confidence thresholds and tracking behaviour before trusting colony metrics.

Keep the existing working hardware stack intact. Keep future commits logically
scoped and do not push without the user's request.

# Raspberry Pi setup (updated fork)

## Verified hardware/software

This fork has been exercised on Raspberry Pi OS **Trixie, 64-bit**, Python
**3.13**, **Hailo-8**, HailoRT **4.23.0**, TAPPAS **5.1.0**, and the **IMX477 HQ
camera**. The supplied `first_15k.hef` targets Hailo-8L, but successfully runs on
Hailo-8 with a runtime warning about reduced performance versus a native Hailo-8
build. Do not assume it works on Hailo-10 or other architectures.

The model expects RGB 640×640 and produces two detection classes. Keep the supplied
`labels.json` (including its background entry) for the TAPPAS postprocessor.

## 1. Check the installed platform first

```bash
hailortcli fw-control identify
pkg-config --modversion hailo-tappas-core
python3 -c 'import hailo, hailo_platform, gi, cv2, numpy, picamera2'
rpicam-hello --list-cameras
rpicam-still --nopreview --timeout 1000 --output /tmp/camera-check.jpg
```

For a Pi that already passes these checks, **do not reinstall/downgrade drivers**
using the older main README's download links or `pip install hailort` instructions.
Use the Raspberry Pi OS packages appropriate to the accelerator. Driver, firmware,
runtime and native Python bindings must match.

If prerequisite tools are missing, the typical Pi OS packages are:

```bash
sudo apt update
sudo apt install git pkg-config python3-venv python3-pip python3-gi \
  python3-opencv python3-numpy python3-picamera2 \
  gir1.2-gstreamer-1.0 gstreamer1.0-tools gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad
# Install the appropriate Raspberry Pi Hailo package separately if needed.
# Hailo-8/8L installations commonly use hailo-all.
```

A ribbon camera uses `rpi` / Picamera2, **not** `/dev/video0`. The absence of
`libcamerasrc` is not a blocker: this pipeline feeds Picamera2 frames into appsrc.

## 2. Install project-local dependencies

From this checkout on the Pi, in **Bash**:

```bash
bash install_pi.sh
source setup_env.sh
```

The installer:

- Creates `.venv` with `--system-site-packages` so native Pi packages remain usable.
- Ignores the original author's committed, non-portable `venv_hailo_rpi5_examples`.
- Installs the small web/application dependencies from `requirements-pi.txt`.
- Fetches Hailo's Python helpers into `.deps/hailo-apps-infra`, pinned to upstream
  commit `4e428ccdcbcde1e91c85beca3334b1073e8c9c8f` (tag `25.3.1`).
- Uses the **installed TAPPAS** YOLO postprocessor rather than compiling an old
  binary or downloading unrelated models. The older upstream installer pins
  NumPy <2, which is unsuitable for this Python 3.13 system, so it is not run.

Source `setup_env.sh` in each new shell. It resolves paths relative to the checkout,
exports TAPPAS paths via pkg-config, checks Python bindings and identifies the device.
It checks required capabilities instead of rejecting every TAPPAS version newer
than 3.31. This does not imply all future versions are compatible.

## 3. Test inference and start the dashboard

Optional direct camera test (Ctrl-C to stop):

```bash
python -u detection.py --input rpi --hef-path first_15k.hef --labels-json labels.json
```

Then:

```bash
python app.py
```

Open `http://<pi-ip>:5000`, then click **Start Detection**. The database is created
on first app startup; running `python bee_health_db.py` is not necessary. The
upstream repository includes an example `bee_health.db`; set `BEE_DB_PATH` to a new
file if you want to retain that file but start your own history:

```bash
BEE_DB_PATH="$PWD/my-bee-health.db" python app.py
```

The dashboard displays counts, FPS and charts. **It does not stream video to the
browser.** Inference defaults to `fakesink` (headless). For a separate preview
window, run from a terminal in the Pi's desktop session:

```bash
BEE_VIDEO_SINK=autovideosink python app.py
```

Other options (set before starting the server):

- `BEE_INPUT=rpi` (default), `/dev/video0` for a USB camera, or a video filename.
- `BEE_HEF=/absolute/path/to/model.hef` to select another compatible model.
- `BEE_DEBUG=1` for verbose detection output.
- `BEE_DB_PATH=/absolute/path/to/history.db` for a separate database.

This is an **unauthenticated development server**, with Flask debug/reloader disabled.
Keep it on a trusted LAN; do not forward port 5000 to the internet. Email alerts
are disabled unless `BEE_MONITOR_EMAIL`, `BEE_MONITOR_EMAIL_PASSWORD`, and
`BEE_MONITOR_EMAIL_RECIPIENT` are explicitly exported before server startup.
The original repository's hard-coded credentials/recipient have been removed;
SMTP authentication debug logging is also disabled. Never reuse those published
credentials (removing them from this file does not remove them from Git history).

### Keep it running after SSH disconnects (until reboot)

For a checkout in `~/bee-mite-detector`, on a Pi with a user systemd session:

```bash
systemd-run --user --unit=bee-mite-detector \
  --working-directory="$HOME/bee-mite-detector" \
  --property="StandardOutput=append:$HOME/bee-mite-detector/app.log" \
  --property="StandardError=append:$HOME/bee-mite-detector/app.log" \
  /bin/bash -c 'source ./setup_env.sh && exec python -u app.py'

systemctl --user status bee-mite-detector
# Stop the server (and its detection subprocess):
systemctl --user stop bee-mite-detector
```

This is a transient unit, **not boot-time autostart**. Only run one server/camera
consumer at a time. A permanent service can be added once the setup is validated.

## Validation and limits

Verified on the setup above:

- Supplied HEF loads and completes inference on Hailo-8.
- Camera → inference → postprocessor → tracker → dashboard runs around **30 FPS**.
- Start/stop/restart releases the camera and records sessions/metrics in SQLite.
- Hardware-independent regression tests: `python -m unittest tests.test_runtime`.

This is operational validation, **not detection-accuracy validation**. Test with
representative bees/mites, correct focus, scale and lighting before relying on
counts. Tracker IDs can fragment or be assigned again when an animal re-enters the
view; “unique bees” is not a guaranteed count of distinct animals. The inherited
risk thresholds are not validated colony-health advice. With zero detected bees,
health is shown as **Unknown**, not Low.

For custom training, retain the original PyTorch weights and/or ONNX model. The
compiled HEF is a deployment artifact, not a practical training checkpoint. A
future model must also have matching class order, preprocessing and Hailo
postprocessing/compilation settings.

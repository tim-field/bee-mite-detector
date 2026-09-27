> **Archived long-form handoff.** Superseded by the concise `training-handoff.md`;
> retained only for historical detail (session logs, WSL install history, dataset audit notes).

# Training handoff: bee/varroa YOLOv8n baseline

## Latest checkpoint: curated export inspected; provisional baseline evaluation done

The user completed manual review and exported **`bee-v14-entrance-v2`**, then
chose to inspect it, transfer it to WSL, and re-evaluate the saved baseline on
the revised validation subset. That run is **provisional**: the labels it
measures against are partly unresolved.

Mac location (frozen, keep intact):

```text
/Users/tim/dev/bee-mite-detector/training-artifacts/image-review/exports/bee-v14-entrance-v2
```

Post-export revisions live in the same `exports/` directory: `bee-v14-entrance-v3`
(`65_jpg` bee label), `v4` (`52_jpg` partial bees), and `v5` (`61_jpg` moved to
train). **v6 is the current dataset revision**; v2-v5 remain frozen.

| Split | Images | Filename groups | Bee boxes | Varroa boxes |
| --- | ---: | ---: | ---: | ---: |
| Train | 277 | 63 | 474 | 783 |
| Validation | 14 | 9 | 28 | 15 |

The export is verified: `COMPLETE` exists; all **582 image/label file hashes**
match `review.json`; no test directory; labels well-formed; no group crosses
train/valid. It records **76 kept / 52 excluded review groups** and **25 manual
review partitions**; reasons were brood (40), close-up (11), off-topic (1).
User choices/provenance are in the export's `review.json`; ongoing review state
is `training-artifacts/image-review/decisions.json` at revision 206. These
artifacts are Git-ignored local files: do not assume a fresh clone has them.

Coverage/label inspection findings:

- Five of the eight current validation groups are exact mirror pairs, so the
  validation subset is only **8 unique scenes** (13 images). Validation varroa
  coverage is **15 boxes**, all >= 32 px short side; tiny-mite and empty-scene
  performance remain unmeasurable. Train still holds 186 varroa boxes below
  32 px (plus the moved `61_jpg` entrance scene).
- All eight earlier label-review items are now resolved: `17_jpg` and `98_jpg`
  excluded, `12_jpeg` confirmed as-is (flower object is a varroa mite;
  partial-bee box convention accepted), `65_jpg` fixed in v3, `52_jpg` in v4,
  `61_jpg` moved to train in v5, and `68_jpg` labelled in v6 (below).

Transfer and evaluation:

- Copied to WSL `datasets/bee-v14-entrance-v2/`; all 582 hashes re-verified; the
  copy's `data.yaml` path was updated to its WSL location.
- **Provisional baseline evaluation** with the unchanged
  `runs/bee-v14-baseline/weights/best.pt`: bee AP50 37.27% (was 36.63%), varroa
  AP50 76.71% (was 95.99%), mean AP50 56.99% (was 66.31%), mean AP50-95 39.69%.
  All four missed mite boxes and 14 of 19 missed bee boxes at confidence 0.25
  fall in the flagged images (`65_jpg`, `61_jpg`, `68_jpg`). Full report:
  [`bee-v14-entrance-v2-baseline-validation.md`](bee-v14-entrance-v2-baseline-validation.md).
- **Revision v3 label fix:** the user confirmed all five `65_jpg` mite labels are
  valid varroa and requested the missing bee label. Export `bee-v14-entrance-v3`
  records the edit (`LABEL-EDITS.md`, `review.json` `post_export_edits`; v2
  frozen), was transferred to WSL, and re-evaluated: bee AP50 41.64%, varroa
  AP50 76.71% (unchanged), mean AP50 59.18%, mean AP50-95 41.20%. The four
  remaining mite misses in `65_jpg` are therefore confirmed real detection
  failures, not label noise. Note the mirror-pair/unique-scene and tiny-mite/
  empty-scene coverage gaps above still apply to v3.
- **Revision v4 label fix:** the user chose to label the two partial background
  bees in `52_jpg` and its mirror. Export `bee-v14-entrance-v4` adds two bee
  boxes per image (same provenance pattern; v3 frozen), was transferred to WSL,
  and re-evaluated: bee AP50 39.60%, varroa AP50 76.71% (unchanged), mean AP50
  58.16%, mean AP50-95 40.49%. Bee metrics dip because the model detects the
  partial bees in one mirror image but not the other, adding two genuine false
  negatives.
- **Revision v5 split change:** `61_jpg` was moved from validation to train
  (labels unchanged) because it is under-annotated and the baseline scores at
  most 0.11 in it. Export `bee-v14-entrance-v5` records the move
  (`review.json` `post_export_edits`, `splits_preserved: false`) and was
  re-evaluated: bee AP50 66.13%, varroa AP50 76.81%, mean AP50 71.47%, mean
  AP50-95 48.30%. The jump is removal of the hardest validation scene, not
  model improvement; the capability gap remains and the scene is retained in
  train.
- **Revision v6 label fix:** `68_jpg` had only two bees labelled despite more
  visible. Export `bee-v14-entrance-v6` adds six bee boxes per image (same
  provenance pattern; v5 frozen), was transferred to WSL, and re-evaluated:
  bee AP50 45.88%, varroa AP50 76.81% (unchanged), mean AP50 61.34%, mean
  AP50-95 42.14%. The dip is measured truth: the model misses all 8 bee boxes
  per image and calls 5 of them mites (0.34-0.76). Validation is now 13 images
  / 8 groups / 31 bee / 15 varroa.
- `tools/evaluate_bee_baseline.py` is now generalized (`--dataset`,
  `--checkpoint`); 7 tests pass. Runs v2-v6 are preserved in WSL
  `evaluations/bee-v14-entrance-v{2,3,4,5,6}-baseline-val-review-v1/` and
  mirrored to the corresponding Git-ignored `training-artifacts/` directories
  on the Mac; the v6 run reflects the current dataset revision.
- No training occurred. The test split, Pi deployment, and review workspace were
  untouched.

**Next session:** the label queue is complete; the next work is coverage and
data. Agree the next data step (representative IMX477 entrance capture,
genuinely small mites, negative/empty scenes, additional unique capture groups;
check rights for the paper's other datasets) before any new training run. A
fresh review-tool export will not contain any of the v3-v6 edits (the review
source is unmodified), so carry them forward when building a later revision.
Re-evaluate the v6 validation split with this same checkpoint before comparing a
newly trained model. Keep the original test holdout closed. Recheck WSL
connectivity and environment; do not assume the training host state persists.

## Purpose and current authorization

The user wants to train a bee/varroa detector and eventually compile it for their
Raspberry Pi's **Hailo-8**. A small-dataset baseline is complete. This document is
an implementation plan for the next agent, not authorization to automatically run
all experiments, download large datasets, install Hailo tooling, or deploy a model.
Explain the next bounded action to the user and agree on longer-running work.

Read `AGENTS.md`, `docs/agent-handoff.md`, and `docs/raspberry-pi-setup.md` before
setup/deployment work. Preserve the working Pi stack. No new model was deployed.

## Verified training machine and access

Verified during this conversation on 2026-09-25; recheck before relying on state:

```bash
ssh -p 2222 tim@192.168.8.238
```

This connects **directly into Ubuntu under WSL2**, not a Windows shell.
SSH key authentication works from the Mac.

- Windows GPU: NVIDIA GeForce **RTX 3060 Ti**, **8 GB VRAM**.
- Windows physical RAM: approximately 32 GB.
- WSL: Ubuntu **26.04.1 LTS**, x86_64.
- System Python: 3.14.4; left unchanged.
- Windows NVIDIA driver: 610.88; left unchanged. GPU works inside WSL.
- With user permission, changed only `memory=1GB` to `memory=16GB` in
  `C:\Users\tim\.wslconfig`; backup:
  `C:\Users\tim\.wslconfig.backup-20260925-220911`.
- User restarted WSL. `free -h` then reported about 15 GiB RAM and 4 GiB swap.
- Windows C: had about **383 GB free**. WSL's virtual filesystem reported much
  more capacity; use the Windows backing-drive free space when planning downloads.
- `tmux` is installed. It survives SSH disconnects, **not Windows/WSL shutdown**.
  Keep Windows awake during runs.

### Isolated environment

Everything for training lives under `/home/tim/bee-mite-training` in the WSL
Linux filesystem, not `/mnt/c`. No system Python packages or Linux NVIDIA driver
were installed.

- Managed Python **3.11.16**: `tools/python/`.
- Virtual environment: `.venv/`.
- uv **0.12.19**: `tools/uv-x86_64-unknown-linux-gnu/uv`.
- uv release provenance/checksum: `tools/uv-release.json`.
- PyTorch **2.11.0+cu128**, torchvision **0.26.0+cu128**.
- Ultralytics **8.4.162**.
- PyTorch installed from `https://download.pytorch.org/whl/cu128`; Ultralytics
  from PyPI. Resolved versions saved in `requirements-resolved.txt`.
- uv cache: `tools/cache/`. When using uv, set `UV_CACHE_DIR` and
  `UV_PYTHON_INSTALL_DIR` to these workspace-local paths.
- Scripts set `YOLO_CONFIG_DIR` and `MPLCONFIGDIR` under `.config/` and disable
  Ultralytics settings synchronization (`sync=False`).
- Training uses four PyTorch CPU threads and two data-loader workers.

The installed package versions are verified for **training**, not yet for
Hailo-compatible ONNX export. Do not assume the compiler supports this newest
Ultralytics exporter; use a separate export/compiler environment if needed.

## Files and artifacts on WSL

```text
/home/tim/bee-mite-training/
  requirements-resolved.txt
  gpu-check.py                    # Synthetic two-class YOLO forward/backward test
  prepare-bee-v14.py              # Reproducible preparation; refuses overwrite
  train-bee-v14-pilot.py           # Five-epoch pilot; refuses overwrite
  train-bee-v14-baseline.py        # Baseline; refuses overwrite
  yolov8n.pt                      # Original pretrained starting weights
  datasets/
    bee-v14-transfer.tar.gz
    raw/bee-v14/                  # Unmodified downloaded contents
    bee-v14-grouped-v1/
      data.yaml
      audit.json
      manifest.json              # Input paths/hashes, groups, converted boxes/splits
      README.dataset.txt
      README.roboflow.txt
      training-label-sample.jpg
      train/{images,labels}/
      valid/{images,labels}/
      test/{images,labels}/
  runs/
    bee-v14-pilot/                # args.yaml, results.csv, plots, weights
    bee-v14-baseline/             # args.yaml, results.csv, plots, weights
  logs/
    install-pytorch.log
    install-ultralytics.log
    gpu-check.log
    gpu-check.json
    bee-v14-pilot.log
    pilot-summary.json
    bee-v14-baseline.log
    bee-v14-baseline-status.json
```

Scripts above are saved on WSL, **not yet committed to this repo**. Temporary
copies were made under `/tmp` on the Mac; do not rely on their persistence.
Preserve the remote scripts/artifacts. Bring reusable scripts into the repo with
review and tests if the user wants ongoing training infrastructure. Do not commit
large datasets, credentials, caches, or checkpoints.

## Dataset audit and preparation already performed

Original Mac download, untouched:
`/Users/tim/Downloads/bee.v14i.yolov8`.

Source: <https://universe.roboflow.com/alice-fsfw8/bee-0flyv/dataset/14>.
The export identifies its license as **CC BY 4.0**; retain attribution and verify
upstream licensing/provenance before redistribution or product use.

Actual export: **537 images**, not 436 total:

| Original split | Images |
| --- | ---: |
| Train | 436 |
| Validation | 70 |
| Test | 31 |

Class order is **0=bee, 1=varroa**. Do not train a background class. The Pi's
`labels.json` background entry is a runtime postprocessor convention only.

Findings:

- Export already stretched images to 640x640 and included horizontal flips.
  Filenames also identify pre-existing rotated versions.
- No byte-identical image duplicates found; no missing/orphan label files.
- **141 annotation rows were polygons**, mixed with YOLO detection boxes.
  These were converted to enclosing axis-aligned boxes, not discarded.
- **33 filename-derived source groups crossed the original splits** after
  removing `.rf.<hash>` and `_rotated_<degrees>_degrees` suffixes.
- Rebuilt splits using seed 42, approximately 80/10/10 by source group.
  Also checked exact decoded-pixel matches across flips and quarter-turns.
- All images decoded as 640x640; annotation ranges/nonzero dimensions/bounds were
  checked. Assertions verify that source groups, byte hashes, and canonical exact
  pixel hashes do not cross the new splits.
- **This is not a complete perceptual near-duplicate or capture-provenance audit.**
  Different filenames, crops or recompressed images can still be related.

Prepared `bee-v14-grouped-v1`:

| Split | Images | Inferred source groups | Bee boxes | Varroa boxes |
| --- | ---: | ---: | ---: | ---: |
| Train | 456 | 92 | 502 | 1,325 |
| Validation | 53 | 11 | 28 | 118 |
| Test | 28 | 12 | 57 | 137 |

Augmented variants were retained in all splits; image counts overstate independent
scene counts. Validation has only **11 source groups and 28 bee annotations**.
Do not treat its metrics as precise estimates of field accuracy.

A training-only contact sheet was visually inspected. It contains close-up bee
photos, magnified/isolated mites, artificial rotation borders and watermarks.
Some visible bees appear unlabelled. Conversion fixes annotation format, **not
semantic correctness or annotation completeness**. No relabelling was performed.

The new test split has **not been evaluated or visually inspected for tuning**.
Label/count/integrity checks did include all splits. The original downloaded split
boundaries were replaced before training because of leakage concerns.

## Experiments completed

### GPU smoke test

`gpu-check.py`: synthetic batch of eight 640x640 RGB images, YOLOv8n with two
classes, AMP forward pass, detection loss, backpropagation, AdamW step. Passed.
This was a machinery test, not accuracy validation.

### Five-epoch pilot

- Started from original COCO-pretrained `yolov8n.pt`.
- 640x640, batch 8, AdamW, LR 0.001, cosine schedule, warmup 1 epoch.
- Mosaic 0.5, mixup 0; default HSV settings; AMP, seed 42.
- About **34.5 seconds** including setup and validation; reported GPU memory
  approximately 1.35 GB.
- Final best-checkpoint validation mAP50 **0.536**, mAP50-95 **0.315**.

### Baseline (complete; not still running)

`train-bee-v14-baseline.py` was launched in tmux session `bee-v14-baseline`.
That session can disappear normally when the script finishes.

- Again started from **original pretrained `yolov8n.pt`**, not pilot weights.
- Maximum 100 epochs; early stopping patience 20.
- 640x640, batch 8, workers 2, AdamW, LR 0.001, cosine schedule.
- Warmup 3 epochs, mosaic 0.5, close_mosaic 10, mixup 0.
- AMP, seed 42, deterministic=True, no image cache.
- `args.yaml` is authoritative for all resolved settings.
- Stopped normally at **epoch 58**, best checkpoint from **epoch 38**.
- Total elapsed **239.58 seconds** (about four minutes).
- Because early stopping occurred before the final ten scheduled epochs,
  `close_mosaic=10` did not result in a final mosaic-free phase.

Final validation of saved `best.pt` on 53 validation images / 146 objects:

| Metric (mean across classes) | Value |
| --- | ---: |
| Precision | 0.863 |
| Recall | 0.609 |
| mAP50 | 0.666 |
| mAP50-95 | 0.392 |

The epoch-38 CSV metrics are slightly different from final checkpoint validation
(e.g. mAP50 0.66434); distinguish those rather than claiming exact identity.
Precision/recall are validator summary operating-point metrics, not measurements
at the Pi application's fixed confidence threshold. Per-class results and failure
analysis are **not yet done**. Best checkpoint:

```text
/home/tim/bee-mite-training/runs/bee-v14-baseline/weights/best.pt
```

Do not compare these numbers directly with the PDF's reported 89.8% mAP50:
curation, amount of data and evaluation splits differ substantially.

## Validation review completed after this handoff

The user authorized the bounded validation review. It is complete; see
[`bee-v14-baseline-validation.md`](bee-v14-baseline-validation.md) and
[`reports/bee-v14-baseline-validation.json`](reports/bee-v14-baseline-validation.json).

- Rechecked SSH/GPU and baseline status; originals preserved and hashes unchanged.
- Completed output: WSL `evaluations/bee-v14-baseline-val-review-v2/`, relative to
  `/home/tim/bee-mite-training`; Mac `training-artifacts/bee-v14-baseline-val-review-v2/`
  (Git-ignored). The partial v1 attempt stopped after validation on an API access
  error; v2 corrected it without overwriting the first attempt or baseline.
- Explicit FP32 validation: bee AP50 **0.3663**, varroa AP50 **0.95994**, mean
  **0.66312**. Settings differ from training-end validation; no retraining occurred.
- Important limitation: **no validation mite box has a short side below 32 px** at
  640 input. Two filename groups contain 85/118 mite labels. Visual review shows
  repeated close-ups and also unrelated photos sharing some filename groups.
- Bee misses, whole bees misclassified as mites, and suspected incomplete labels
  are documented with examples and a human label-review queue. The high mite AP
  does not demonstrate field/tiny-mite performance.
- Script now in repo: `tools/evaluate_bee_baseline.py`; six package-independent
  tests in `tests/test_training_evaluation.py` pass. Curves, threshold counts,
  predictions and labelled examples are saved. No test images were opened.
- **Next:** agree label/scope policy, review suspect annotations, and audit more
  representative scenes before another training run. No label changes, further
  dataset downloads, compiler installation or deployment were authorized by this
  bounded review. Pi and test split remain untouched.
- WSL `nvidia-smi` is available at `/usr/lib/wsl/lib/nvidia-smi`, not the noninteractive
  SSH PATH. An initial package-version import without `YOLO_CONFIG_DIR` created
  default `/home/tim/.config/Ultralytics/settings.json`; subsequent evaluation used
  the workspace-local config and `sync=False`. No package/driver changes occurred.

## Local dataset curation tool (subsequent user request)

The user asked to personally exclude magnified mites and brood images for a
hive-entrance deployment, then authorized building a review tool. See
[`dataset-review.md`](dataset-review.md) for usage, safety and restart commands.

- Implemented `tools/review_dataset.py` + `tools/review_dataset.html`, standard-library
  Python only, localhost web UI. Tests: `tests/test_dataset_review.py` (16 passed).
- Selectively copied prepared train/valid images/labels and metadata from WSL to
  Mac `training-artifacts/review-source/bee-v14-grouped-v1/`. **509 images, 103 original
  review groups. No test images/labels were copied or viewed.**
- User review is at **http://127.0.0.1:8765**, workspace
  `training-artifacts/image-review/`; detached server PID recorded in `server.pid`,
  logs in `server.log`. Recheck process/URL; it is not configured for boot startup.
- Keep/Exclude/Unsure, label overlays, exclusion reasons/notes, persistent atomic
  decisions, undo, filters, and export preview. Mixed filename groups can be
  manually partitioned into review subsets; original source-group IDs and dataset
  splits never change. Review partitions persist and require fresh decisions.
- Export makes a new version with paired images/labels, provenance and attribution;
  no source changes, no overwritten versions, and no test export. Requires all
  decisions resolved and both classes retained in each split. Update exported
  `data.yaml` path after transferring from Mac to WSL. No training was launched.
- User workspace was verified **revision 0, all 509 images unreviewed** at handoff.
  Do not overwrite subsequent user decisions or treat this historical state as current.
- Browser smoke test used separate `training-artifacts/image-review-smoke/` on 8766
  (now stopped). Its `smoke-only-not-for-training` export is NOT user curation.
  Combined review/evaluation-helper tests: 22 passed; full app suite not run.
- Prepared/raw WSL data and the Pi deployment were not modified. No commits/pushes.

## Ordered next steps

### 1. Preserve the baseline and inspect validation failures (completed; see above)

1. Recheck SSH, status JSON, `results.csv`, `args.yaml`, and saved checkpoints.
2. Preserve hashes of the dataset manifest and checkpoint alongside results.
   Consider copying small scripts/results to the Mac; leave the original run intact.
3. Validate **best.pt on `split=val`**, with explicit `imgsz=640`, batch size and
   device; save into a **new named evaluation directory**, not over the baseline.
4. Save per-class AP50, AP50-95, precision and recall, the confidence/PR curves,
   and confusion matrix. Inspect validation predictions versus annotations.
5. Summarize specific failure modes: missed tiny mites, isolated mites versus mites
   on bees, bee-body false positives, omitted labels, blur and unusual object scale.
6. Assess confidence-threshold tradeoffs on validation only. Do not confuse
   Ultralytics validation's low collection threshold with a deployment threshold.

Deliverable: concise failure-analysis report and examples, with a recommendation
on whether label repair or additional representative data is highest leverage.
**Keep the test set closed while making those decisions.**

### 2. Improve data quality and diversity before chasing more epochs

- Agree on label policy: which visible bees/mites should be boxed, treatment of
  partial/occluded objects, and whether isolated mites are in deployment scope.
- Review suspected missing/wrong labels. Save corrections as a new dataset version
  with provenance; do not edit the raw download or silently invalidate old scores.
- Audit other source datasets below for actual contents, licenses, annotation
  formats and label mapping. Counts in the PDF are not guaranteed current.
- Detect duplicates/near-duplicates **across all datasets**, not only within each.
  No new training data should duplicate reserved validation/test scenes.
- Prefer grouping by source image/video/hive/capture day where available. Avoid
  random frame-level splits or splitting before grouping augmented variants.
- Collect representative IMX477 footage using the intended lens, distance, exposure
  and hive/tunnel geometry. Verify mites retain enough pixels at model input size.
- Include healthy bees, empty/background scenes and confusing objects. Avoid
  treating unlabelled objects as true negative examples.
- Reserve separate real-camera evaluation scenes before training. Dataset mAP
  alone does not validate bee counts, tracker uniqueness or colony infestation risk.

Other links extracted from the PDF's bibliography:

| Dataset | Link |
| --- | --- |
| Bolo Beehive Detection v2 | https://universe.roboflow.com/bolo-q0wr5/beehive-detection/dataset/2 |
| Alice Beehive v7 | https://universe.roboflow.com/alice-fsfw8/beehive-a1iyw/dataset/7 |
| Bee Beehive v5 | https://universe.roboflow.com/bee-9phqe/beehive-qyqml/dataset/5 |

The report describes progressive training across curated subsets; exact corrected
labels, split manifests and original trained weights were not supplied. A clean
combined-data baseline is reasonable; exact reproduction is not promised.

### 3. Train a controlled improved baseline

- Keep standard **YOLOv8n**, 640x640, two classes for the first improved dataset.
  Avoid the report's custom YOLOv8n-SO variant until there is clear evidence it is
  needed and a verified Hailo compilation route.
- Use a new run name and pinned environment; save dataset manifest and settings.
- Start from pretrained weights for a clean comparison; if fine-tuning the current
  checkpoint instead, explicitly record that choice.
- Change one major factor at a time. Keep validation groups fixed where practical
  and report when changes prevent direct score comparisons.
- Batch 8 works comfortably. Increase only after measuring memory/throughput.
- Use early stopping; do not assume 100 epochs are required or that more epochs
  compensate for bad labels. Report class-specific metrics, not just mean mAP.
- Once the model/threshold choice is frozen, evaluate the held-out test set once
  for the agreed comparison. If used to guide later improvements, it is no longer
  an untouched final test set; obtain a fresh holdout.

### 4. Validate export and Hailo-8 compilation separately

- First perform a small compatibility check on this baseline rather than wait for
  a large final training run. Obtain agreement before installing compiler tooling.
- Keep `best.pt`, model/class metadata and an unquantized ONNX export.
- Verify Hailo Dataflow Compiler / Model Zoo support matrix and licensing/access.
  Ubuntu 26.04 and the current Ultralytics exporter are **not established compatible**.
  Use a separate supported Linux environment/container or WSL distro as necessary;
  do not downgrade the working training or Pi environment.
- The report used ONNX opset 11, but do not blindly reuse that setting with modern
  exporters. Confirm the selected compiler's input/output node expectations.
- Target **hailo8**, not hailo8l. Compile with two classes and compatible YOLOv8
  NMS output, checking RGB/normalization, 640x640 input, class order and thresholds.
- Use representative training-side calibration images. Do not consume the final
  test set for calibration. Quantization needs data representative of real scenes.
- Compare PyTorch, ONNX and quantized/HEF predictions on the same agreed evaluation
  samples, especially small-mite recall. Calibration/quantization can lose accuracy.
- Save compiler versions, scripts, model config, calibration manifest and logs.

### 5. Deploy only after accuracy/compatibility checks and user approval

- Follow the existing Pi deployment documentation and recheck runtime state.
- Preserve `first_15k.hef` as rollback; install a newly named HEF and switch via
  `BEE_HEF` only when approved. Do not replace it in place.
- Preserve the runtime label convention (`background`, `bee`, `varroa`) while the
  model itself still has just two classes.
- Match postprocessing/NMS behavior and confidence settings, then verify camera
  operation, counts, performance and stopping/restarting the application.
- Real-world missed mites, false alarms and repeated tracking counts matter more
  than accelerator-only FPS. The application's inherited colony-risk thresholds
  remain unvalidated.

## Corrections to earlier conversation advice

- The PDF is not a complete reproducible recipe: important curation/splits and
  source scripts are missing. Public datasets alone do not guarantee its results.
- Segmentation polygons **can** be converted to detection boxes; do not discard
  them automatically. This dataset required that conversion.
- The PDF's ambiguous `HSV=0.5` does **not** justify setting `hsv_h=0.5`.
  We used Ultralytics defaults instead.
- A modern Mac can train small models using MPS; the earlier claim that it is
  useful only for a small smoke test was too categorical. The RTX machine is our
  chosen and verified training host.
- The existing Hailo-8L HEF already ran on the Pi's Hailo-8. Native recompilation
  may improve performance; it does not by itself improve learned detection quality.

## Local checkout safety

At handoff creation, pre-existing unrelated changes were present:

```text
 M docs/raspberry-pi-setup.md
?? .vscode/
?? deploy_pi.sh
?? tests/test_deploy_script.py
```

Do not overwrite, revert or claim these as training work. No commits or pushes
were made for this training session. The working hardware deployment is separate
from the Mac checkout; local edits are not automatically deployed.

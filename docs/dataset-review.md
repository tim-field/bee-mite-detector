# Local image review tool

Open **http://127.0.0.1:8765** on the Mac while the review server is running.
This is separate from the Pi dashboard. It requires only Python 3.10+ on macOS or
Linux/WSL; it does not install packages, train a model, or contact cloud services.

## Review workflow

1. Click an image card to open its **review group**. Initially there are 103 groups
   containing 509 prepared training/validation images (456 train, 53 validation).
2. Inspect the thumbnails. Cyan boxes are existing bee annotations; orange boxes
   are varroa annotations, **not predictions**. Toggle labels off to see details.
3. Choose **Keep (K)**, **Exclude (X)**, or **Unsure (U)**. Select an exclusion
   reason and optionally add notes before saving. A decision applies to every
   image in that review group. Nothing is deleted.
4. Decisions save automatically when you click a decision button or use its
   shortcut. Notes alone are not saved until you choose a decision. Use arrow
   keys to navigate; optionally turn off “Advance after saving.” Shortcuts are
   disabled while typing in inputs.
5. Filter by status, split or filename to revisit decisions. **Undo last decision**
   restores decisions made in the current browser session. After reopening the
   page, change a decision directly or use **Reset to unreviewed**.

### Mixed groups: don't throw away useful scenes

The original filename-derived groups are conservative. Some contain unrelated
photos with the same numbered filename. For example, `10_jpg` includes both
magnified mites and adult bees. Grouping is not a perfect near-duplicate audit.

Inside a mixed group, expand **“Different scenes in this group? Separate them for
review.”** Select **all variants of one scene**, then click **Separate selected
images**. The selected and remaining images become independently reviewable groups,
both reset to Unreviewed. You can then exclude the close-up scene and keep the
adult-bee scene. Selecting none or all is rejected.

This partitions **review decisions only**. The original manifest source-group IDs
and train/validation membership stay unchanged. Even if related variants are
separated for review, no image crosses a dataset split. You still need to select
all unwanted variants when excluding a scene; the tool does not infer biological
content or run a new perceptual similarity algorithm.

Partitions persist and are not undone by the decision Undo button (that button's
history clears after partitioning). You can still change every group's decision.
Use Unsure for uncertain annotations or scope rather than guessing. Keeping an
image does not certify its labels; this tool is an exclusion tool, not a box editor.

## Export a new dataset version

Click **Export reviewed dataset**. It shows the kept image/class counts by split.

Export requires:

- Every review group marked Keep or Exclude; Unsure/unreviewed groups block it.
- At least one retained image and labels for **both bee and varroa** in each split.
- An unused version name (letters, numbers, dashes and underscores).
- Source files still matching the reviewed hashes.

Export creates a **copy**, never edits the original. Only kept images and their
matching `.txt` labels are copied. It preserves the original split and class order
(`0=bee`, `1=varroa`), source-group metadata, attribution files, decisions, file
hashes and source fingerprint. It never resizes, relabels or re-splits images.

Output location on this Mac:

```text
/Users/tim/dev/bee-mite-detector/training-artifacts/image-review/exports/<version>/
  train/{images,labels}/
  valid/{images,labels}/
  data.yaml
  manifest.json
  review.json
  README.dataset.txt
  README.roboflow.txt
  REVIEW-NOTES.md
  COMPLETE
```

**Test images are not copied, displayed, or exported.** The original test holdout
remains on WSL. `data.yaml` intentionally contains no test split. Its dataset path
points to the new Mac directory; update that path when transferring the export to
WSL for training. Do not train from an export without the `COMPLETE` marker; an
interrupted export may leave an incomplete directory, which is never overwritten.
Choose a new version name for another export.

After curation, we should review retained class/scene coverage, audit questionable
labels and collect representative hive-entrance footage. Re-evaluate the old
baseline and new model on the **same revised validation set** before comparing
scores. Keep the original final holdout closed during model selection; a future
representative camera holdout will also be needed.

## Starting or restarting

From a Mac terminal:

```bash
cd /Users/tim/dev/bee-mite-detector
python3 tools/review_dataset.py \
  --dataset training-artifacts/review-source/bee-v14-grouped-v1 \
  --workspace training-artifacts/image-review \
  --port 8765
```

Leave the terminal running, then open <http://127.0.0.1:8765>. Stop a foreground
server with Ctrl+C. Reopening it resumes saved decisions. A process lock prevents
two servers writing to the same review workspace. To serve a different independent
review, provide a different workspace and port.

The setup session started the user's server detached on port 8765. Its PID is saved
in `training-artifacts/image-review/server.pid`; output is in `server.log`. That
process survives an SSH/tool session ending but is not a boot-time service. Check
that a PID still belongs to `tools/review_dataset.py` before stopping it; PIDs can
be reused. If the workspace is already open, use the existing URL rather than
starting another server.

All decisions/partitions are stored atomically in:

```text
training-artifacts/image-review/decisions.json
```

Back up that file **and** the prepared review source if you want a durable manual
backup. The file is tied to exact source hashes and cannot silently be applied to a
different dataset. To start an independent review, use a new workspace rather than
modifying the existing decisions JSON by hand.

### Where this review copy came from

Only `train/`, `valid/`, `manifest.json`, and the two attribution README files were
copied from the **prepared**, leakage-grouped WSL dataset:

```text
tim@192.168.8.238:2222
/home/tim/bee-mite-training/datasets/bee-v14-grouped-v1
```

Mac review source:

```text
/Users/tim/dev/bee-mite-detector/training-artifacts/review-source/bee-v14-grouped-v1
```

The manifest contains reserved-test metadata for cross-split integrity checks,
but there are **no test images or label files in the Mac review copy**. No raw
Roboflow folders were used as a replacement for the prepared splits. Source image
hashes and converted boxes are checked against the manifest on startup. Do not
manually move/delete files from this review source: that invalidates the review.

Dataset attribution: Alice, Bee v14,
<https://universe.roboflow.com/alice-fsfw8/bee-0flyv/dataset/14>.
Export identifies [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Retain upstream attribution and verify underlying image rights before publishing.

## Safety and validation

- Bound to **127.0.0.1 only**; no LAN/public exposure or Pi runtime changes.
- Local Host/Origin checks and per-server write token protect against accidental
  cross-site requests. No arbitrary filesystem path is served by the image API.
- Only known train/valid image IDs are served; metadata returned to the browser
  excludes test rows. Source groups, byte hashes and recorded pixel hashes are
  checked for crossing split boundaries before review opens.
- Writes check the revision to avoid stale tabs overwriting newer decisions.
- Export paths are constrained to the workspace, use new version names, verify
  source/copy hashes, and never overwrite an existing dataset version.
- Images, checkpoints, decisions, local logs and exports stay under the existing
  Git-ignored `training-artifacts/` directory.

Tests:

```bash
python3 -m unittest tests.test_dataset_review tests.test_training_evaluation
```

22 tests passed (16 review tests, 6 existing evaluation-helper tests). Coverage
includes persistence, group partitioning, image/label pairing, original split
preservation, hidden test assets, source mutation, stale writes, export overwrite
protection, filesystem paths and HTTP request checks. This is not a full application
regression suite.

Browser smoke testing used a **separate** workspace on port 8766:
`training-artifacts/image-review-smoke/`. It exercised labels/thumbnails,
exclude/undo, mixed-group partitioning, reload persistence, blocked incomplete
export and a successful 507-image export. That export is named
`smoke-only-not-for-training`; its automatic choices are **not human curation**.
The user's workspace started with all 509 images unreviewed and no partitions.

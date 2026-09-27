# Bee/varroa baseline: provisional review on the curated entrance export

## Status: provisional

The saved `bee-v14-baseline` checkpoint was re-evaluated on the user-curated
`bee-v14-entrance-v2` validation subset. **Treat these numbers as provisional**:
All label-review queue items are now resolved (v3-v6 label edits, exclusions,
and confirmations), so the label-queue caveat above no longer applies. The
numbers remain provisional in a different sense: coverage is thin — **8 unique
validation scenes** (5 of 8 groups are mirror pairs), no mite box below 32 px,
and no empty/background scenes. Do not treat them as field-accuracy evidence.

This evaluation trained nothing, opened no test images, and left the Pi untouched.

## What was evaluated

- Checkpoint: `runs/bee-v14-baseline/weights/best.pt` (unchanged, hashed).
- Dataset: `datasets/bee-v14-entrance-v2` on WSL — the user-curated export
  (277 train / 14 valid images after excluding brood and magnified-mite groups).
- Validation subset: **14 images in 9 filename groups**, 28 bee boxes,
  15 varroa boxes. Five of the nine groups are exact mirror pairs, so there are
  **9 unique scenes, not 14**.
- Settings: FP32, `imgsz=640`, batch 8, CUDA, collection confidence 0.001,
  NMS IoU 0.7, max 300 detections; identical to the earlier review.

## Results

| Class | Precision\* | Recall\* | AP50 | AP50–95 |
| --- | ---: | ---: | ---: | ---: |
| Bee | 77.53% | 28.57% | 37.27% | 21.87% |
| Varroa | 80.31% | 73.33% | 76.71% | 57.52% |
| Mean | 78.92% | 50.95% | 56.99% | 39.69% |

\* Ultralytics summary operating-point metrics, not precision/recall at a fixed
application threshold.

### Change versus the original 53-image validation split

| Class | AP50 before → after | AP50–95 before → after |
| --- | --- | --- |
| Bee | 36.63% → 37.27% | 21.57% → 21.87% |
| Varroa | 95.99% → 76.71% | 56.43% → 57.52% |
| Mean | 66.31% → 56.99% | 39.00% → 39.69% |

Bee metrics are essentially unchanged (the same 28 bee boxes were retained).
Varroa AP50 falls sharply once the easy brood close-ups are removed, while
AP50–95 is flat. The earlier 96% mite AP50 was largely a property of the removed
scenes, not evidence of robust mite detection.

### Fixed-confidence tradeoffs (diagnostic matching, IoU ≥ 0.5)

| Confidence | Mite TP/FP/FN | Mite precision | Mite recall | Bee TP/FP/FN | Bee precision | Bee recall |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| 0.10 | 11/11/4 | 50.0% | 73.3% | 9/28/19 | 24.3% | 32.1% |
| 0.25 | 11/7/4 | 61.1% | 73.3% | 9/8/19 | 52.9% | 32.1% |
| 0.30 | 11/7/4 | 61.1% | 73.3% | 9/7/19 | 56.2% | 32.1% |
| 0.50 | 11/3/4 | 78.6% | 73.3% | 8/1/20 | 88.9% | 28.6% |
| 0.70 | 11/1/4 | 91.7% | 73.3% | 5/0/23 | 100.0% | 17.9% |

FP means unmatched against existing annotations, not a confirmed biological
false alarm. Missing labels make sensible predictions count as FPs.

### Revision v3: `65_jpg` bee label added

The user reviewed `65_jpg` and confirmed all five labelled regions are valid
varroa mites, and asked that the missing bee label be added. Export
`bee-v14-entrance-v3` records exactly that edit (v2 remains frozen; the edit is
documented in the export's `LABEL-EDITS.md` and `review.json`). The same
checkpoint was re-evaluated:

| Class | v2 AP50 → v3 | v2 AP50–95 → v3 |
| --- | --- | --- |
| Bee | 37.27% → 41.64% | 21.87% → 24.88% |
| Varroa | 76.71% → 76.71% | 57.52% → 57.52% |
| Mean | 56.99% → 59.18% | 39.69% → 41.20% |

Validation now holds 29 bee boxes and 15 varroa boxes. The added bee box matches
the model's existing `bee 0.67` prediction. The four mite boxes still missed in
`65_jpg` are now **confirmed real mites**, so those four misses are genuine
detection failures rather than label noise. The other queue items below remain
unresolved.

### Revision v4: `52_jpg` partial-bee labels

The user chose to label the two partial background bees visible at the frame
corners in `52_jpg` and its mirror. Export `bee-v14-entrance-v4` adds two bee
boxes per image; the queue's "blurred lowest mite" concern had already left with
the excluded mirror image. The same checkpoint was re-evaluated:

| Class | v3 AP50 → v4 | v3 AP50–95 → v4 |
| --- | --- | --- |
| Bee | 41.64% → 39.60% | 24.88% → 23.46% |
| Varroa | 76.71% → 76.71% | 57.52% → 57.52% |
| Mean | 59.18% → 58.16% | 41.20% → 40.49% |

Bee metrics dip slightly because the model detects the partial bees in one
mirror image but not the other, so the added labels contribute two genuine
false negatives. At confidence 0.25 bee is 12 TP / 5 FP / 21 FN (was 10/7/19).

### Revision v5: `61_jpg` moved to train

`61_jpg` (14 bee boxes, all missed by the checkpoint, at most 0.11 confidence
anywhere) was the under-annotated hive-entrance scene identified as needing
additional labels. Rather than exhaustively relabelling it, the user chose to
move it out of validation while keeping it for training. Export
`bee-v14-entrance-v5` relocates the image and label to `train/` and records
`splits_preserved: false` in its metadata. Validation is now 13 images / 8 groups
/ 19 bee / 15 varroa boxes.

| Class | v4 AP50 → v5 | v4 AP50–95 → v5 |
| --- | --- | --- |
| Bee | 39.60% → 66.13% | 23.46% → 39.03% |
| Varroa | 76.71% → 76.81% | 57.52% → 57.56% |
| Mean | 58.16% → 71.47% | 40.49% → 48.30% |

The jump reflects removing the hardest validation scene, **not** model
improvement. The model still fails that entrance scene; its labels now live in
train, where they may help future training. Varroa coverage is unchanged: no
box below 32 px short side.

### Revision v6: `68_jpg` additional bee labels

`68_jpg` had only two bees labelled per image despite several more visible
flying bees. The user chose to label them: export `bee-v14-entrance-v6` adds six
bee boxes per image (mirrored). Validation is now 13 images / 31 bee / 15 varroa
boxes.

| Class | v5 AP50 → v6 | v5 AP50–95 → v6 |
| --- | --- | --- |
| Bee | 66.13% → 45.88% | 39.03% → 26.73% |
| Varroa | 76.81% → 76.81% | 57.56% → 57.56% |
| Mean | 71.47% → 61.34% | 48.30% → 42.14% |

The dip is the measured truth: the checkpoint misses all 8 bee boxes per image
and classifies 5 of them as mites (0.34–0.76). The whole-bee-as-mite confusion
is now quantified instead of hidden by missing labels.

## What the errors show

*These bullets describe the v2 run; the v3/v4 revisions above changed some of
these labels, so treat the specific counts here as v2-era observations.*

- **All four missed mite boxes** (at confidence 0.25) are in `65_jpg` — the
  magnified close-up whose labels were later confirmed valid in v3, so these
  are genuine misses. The model also draws a whole-bee box and an extra mite
  there.
- **14 of 19 missed bee boxes** are the single `61_jpg` hive-entrance scene,
  which is queued for incomplete annotation (additional visible bees) and where
  every annotated bee is missed at 0.25.
- **The two `68_jpg` mirror images** account for the remaining 4 missed bee boxes
  and 5 of the 7 mite false positives: blurred flying bees are predicted as
  mites at 0.42–0.55. This is the whole-bee-as-mite confusion already documented.
- **No tiny-mite coverage**: 13 of 15 mite boxes are 32–64 px short side
  (69.2% recalled) and 2 are ≥64 px (100% recalled). There are still **zero
  boxes below 32 px**, so tiny-mite performance remains unmeasurable.
- No empty/background-only scenes exist, so the false-alarm rate on negative
  scenes also remains unmeasurable.

## Label-review queue status

| Example | Group | Images kept | Issue |
| --- | --- | ---: | --- |
| 0 | `12_jpeg` | 2 | **Confirmed as-is**: flower object is a varroa mite; partial-bee box convention accepted |
| 37, 39 | `52_jpg` | 2 | **Resolved in v4**: partial background bees labelled; mites matched by the model |
| 41 | `61_jpg` | 1 | **Resolved in v5**: under-annotated scene moved to train (labels unchanged) |
| 44 | `65_jpg` | 1 | **Resolved in v3**: five mite labels confirmed valid; bee label added |
| 45 | `68_jpg` | 2 | **Resolved in v6**: six additional bees labelled per image; whole-bee-as-mite confusion now measured (5/16 bee boxes scored as mites) |
| 13 | `17_jpg` | — | Excluded from the export; concern resolved by removal |
| 52 | `98_jpg` | — | Excluded from the export; concern resolved by removal |

The review tool supports keep/exclude and group partitioning, **not annotation
editing**. The remaining choices are therefore: exclude the image(s), keep and
document the label noise, or correct labels outside the review workspace as a
new dataset version. Decide the partial/occluded/blurred-object policy first;
then re-export a v3, re-evaluate this same checkpoint on it, and only then
compare any newly trained model.

## Artifacts and reproduction

- Compact metrics and hashes: [`reports/bee-v14-entrance-v2-baseline-validation.json`](reports/bee-v14-entrance-v2-baseline-validation.json),
  v3 [`reports/bee-v14-entrance-v3-baseline-validation.json`](reports/bee-v14-entrance-v3-baseline-validation.json),
  v4 [`reports/bee-v14-entrance-v4-baseline-validation.json`](reports/bee-v14-entrance-v4-baseline-validation.json),
  and v5 [`reports/bee-v14-entrance-v5-baseline-validation.json`](reports/bee-v14-entrance-v5-baseline-validation.json),
  plus v6 [`reports/bee-v14-entrance-v6-baseline-validation.json`](reports/bee-v14-entrance-v6-baseline-validation.json).
- Mac artifacts (Git-ignored, ~11 MB each): `training-artifacts/bee-v14-entrance-v2-baseline-val-review-v1/`
  through `training-artifacts/bee-v14-entrance-v6-baseline-val-review-v1/`.
- WSL artifacts: `/home/tim/bee-mite-training/evaluations/bee-v14-entrance-v2-baseline-val-review-v1/`
  through `.../bee-v14-entrance-v6-baseline-val-review-v1/`.
- WSL log: `/home/tim/bee-mite-training/logs/bee-v14-entrance-v2-baseline-val-review-v1.log`.
- Examples: `examples/06.jpg` (entrance scene), `examples/07.jpg` (magnified
  close-up), `examples/08.jpg` (whole bee predicted as mite).

The generalized evaluator is `tools/evaluate_bee_baseline.py` (sha256
`de3c393f…`, supports `--dataset`/`--checkpoint`; tested by
`tests/test_training_evaluation.py`). The earlier 53-image review used the
archived frozen copy inside its own output directory.

```bash
cd /home/tim/bee-mite-training
.venv/bin/python evaluate-bee-baseline-v3.py \
  --workspace /home/tim/bee-mite-training \
  --dataset datasets/bee-v14-entrance-v2 \
  --checkpoint runs/bee-v14-baseline/weights/best.pt \
  --name bee-v14-entrance-v2-baseline-val-review-v1
```

### Image attribution

Images derive from Alice's Bee v14 dataset
(<https://universe.roboflow.com/alice-fsfw8/bee-0flyv/dataset/14>), identified
as CC BY 4.0. Overlays were added for this review. Rights/provenance have not
been independently verified; source images and checkpoints remain out of Git.

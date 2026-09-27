# Bee/varroa baseline: validation review

## Decision

**Improve label consistency and scene diversity before training longer or changing
architecture.** The baseline recognizes large, close-up mites well on this small
validation split, but this does not establish tiny-mite detection on adult bees
at a hive entrance. Bee detection is weak, and annotation problems complicate
both classes' scores. Do not deploy this checkpoint on the strength of these results.

This review evaluated the saved YOLOv8n checkpoint only. No training, relabelling,
new dataset download, test-set evaluation, or Pi deployment was performed.

## Results

53 validation images; 28 bee boxes and 118 varroa boxes. These are repeated views
and augmented variants in **11 inferred filename groups**, not 53 independent
scenes. Filename groups are conservative: some contain unrelated photos sharing
a numbered filename, so they are not verified capture identities.

| Class | AP50 | AP50–95 | Precision* | Recall* |
| --- | ---: | ---: | ---: | ---: |
| Bee | 36.63% | 21.57% | 77.36% | 28.57% |
| Varroa | 95.99% | 56.43% | 94.69% | 93.22% |
| Mean | 66.31% | 39.00% | 86.03% | 60.90% |

\* Ultralytics summary operating-point metrics, **not** precision/recall at a
fixed application confidence threshold. AP measures precision/recall across a
confidence sweep; AP50 is not “percentage of mites correctly detected.”

This explicit FP32 validation returned 66.31% mean AP50, versus the earlier
training-end report's approximately 66.6%. No model weights changed. Evaluation
settings differ; the small numerical difference has not been isolated to one cause.
Neither result is directly comparable to the paper's 89.8% on different data.

### Fixed-confidence tradeoffs

Using separately saved predictions, class-aware confidence-ordered one-to-one
matching at IoU >= 0.5:

| Confidence | Mite TP / FP / FN | Mite precision | Mite recall | Bee precision | Bee recall |
| --- | --- | ---: | ---: | ---: | ---: |
| 0.10 | 112 / 36 / 6 | 75.7% | 94.9% | 20.9% | 32.1% |
| 0.25 | 111 / 21 / 7 | 84.1% | 94.1% | 47.4% | 32.1% |
| 0.30 | 111 / 18 / 7 | 86.0% | 94.1% | 52.9% | 32.1% |
| 0.50 | 108 / 8 / 10 | 93.1% | 91.5% | 80.0% | 28.6% |
| 0.70 | 101 / 2 / 17 | 98.1% | 85.6% | 100.0% | 17.9% |

FP here means unmatched against **existing annotations**, not a confirmed biological
false alarm. Missing labels can make a sensible prediction count as an FP.
These counts use a documented diagnostic matcher, not Ultralytics' internal AP
matching algorithm. Raw predictions and all eight tested thresholds are saved.

The checkout's `detection.py` uses a counting confidence of 0.30. This table does
not reproduce its compiled HEF, NMS, camera, or tracking pipeline. Raising the
threshold reduces false detections here but does not fix the lack of representative
data or bee recall. **No deployment threshold was selected or changed.**

A separate Ultralytics diagnostic confusion matrix at confidence 0.30 and matching
IoU 0.50 records three annotated bees classified as mites. The main validator's
original confusion matrix uses the low 0.001 collection confidence and its default
matching IoU 0.45; it must not be interpreted as a deployment-threshold matrix.

## What the images reveal

All 53 validation images were viewed in labelled contact sheets; representative
label/prediction pairs and selected failure cases were inspected at full size.
This is an initial visual review, not expert verification of every mite annotation.
The numbered examples below link to local, Git-ignored artifacts; the same files
are preserved on WSL (paths below).

1. **No tiny-mite evaluation coverage.** At the actual 640×640 input scale,
   every labelled mite has a bounding-box short side of at least 32 pixels.
   Median: 58.25 px; maximum: 209.5 px. There are no annotations below 32 px on
   that dimension. Thus tiny-mite recall cannot be estimated from this split.
   This is a short-side diagnostic, not the COCO small-object area definition.

2. **A few close-up scenes dominate.** Groups `17_jpg` and `2_jpg` contain
   34/53 images and 85/118 mite annotations (72%). Contact sheets show repeated
   rotated/flipped brood close-ups, plus a separate adult-bee photo in `2_jpg`.
   The latter group illustrates why filename groups are not exact scene counts.
   The 96% mite AP50 mostly reflects this narrow distribution, not 118 independent
   encounters with mites on moving adult bees. Examples:
   [brood close-up](../training-artifacts/bee-v14-baseline-val-review-v2/examples/02.jpg),
   [large mite](../training-artifacts/bee-v14-baseline-val-review-v2/examples/20.jpg).

3. **Strong scene/scale failure for bees.** In
   [example 41](../training-artifacts/bee-v14-baseline-val-review-v2/examples/41.jpg),
   all 14 annotated bees at a hive entrance are missed at confidence 0.25.
   That single image contains half the validation bee annotations. In
   [example 46](../training-artifacts/bee-v14-baseline-val-review-v2/examples/46.jpg),
   a whole flying bee is predicted as a mite at confidence 0.76. Its mirrored
   variant shows the same kind of confusion. Blurred flying bees and close-up
   mites are not reliably distinguished by this baseline.

4. **Mites on adult bees remain difficult in some views.** In
   [example 44](../training-artifacts/bee-v14-baseline-val-review-v2/examples/44.jpg),
   only one of five mite annotations is matched at confidence 0.25. Several
   labelled regions are visually ambiguous and need expert review; do not claim
   four confirmed real mites were missed without checking those labels. The
   visible adult bee itself has no bee annotation. In contrast,
   [example 19](../training-artifacts/bee-v14-baseline-val-review-v2/examples/19.jpg)
   is a successful adult-bee/large-mite detection.

5. **Missing labels and unclear annotation policy affect scores.**
   [Example 52](../training-artifacts/bee-v14-baseline-val-review-v2/examples/52.jpg)
   labels mites but not the visible partial adult bee; bee predictions are scored
   as unmatched. Examples 45/46 label only two bees despite other visible bees.
   The policy for partial, blurred, overlapping, and immature bees is unclear.
   [Example 13](../training-artifacts/bee-v14-baseline-val-review-v2/examples/13.jpg)
   has an unmatched high-confidence mite prediction near a labelled mite that
   could be a missing annotation or confusion with another structure. It needs
   review, not automatic relabelling from model output.

6. **Even conspicuous close-ups have failure cases.**
   [Example 12](../training-artifacts/bee-v14-baseline-val-review-v2/examples/12.jpg)
   misses one labelled mite in a rotated brood image.
   [Example 37](../training-artifacts/bee-v14-baseline-val-review-v2/examples/37.jpg)
   misses a less distinct labelled region. Blur, orientation, ambiguity and
   annotation quality should be examined before attributing these solely to size.

There are no empty/background-only images in this validation split. It cannot
establish the false-alarm rate on an empty tunnel, hive entrance, debris or other
negative camera scenes. Nor has this review established performance on isolated
mites separate from bee/brood context.

## Recommended next bounded task

**Define the label policy and curate a small, representative data revision.**

1. Agree that the primary target is visible varroa on adult bees in the intended
   camera view (if that is the intended deployment); decide explicitly whether
   brood close-ups and isolated mites belong in training/evaluation scope.
2. Review the eight-item label-review queue in the linked JSON with a knowledgeable
   human. Decide how to label partial/occluded/blurred bees and uncertain mite
   candidates. Apply consistent rules to a training-side sample too. Never
   promote predictions directly to ground truth or silently edit this dataset.
3. Audit candidate samples from the paper's other datasets for adult bees,
   genuinely small mites, negative scenes, licenses, and label completeness.
   Prioritize new scenes over additional rotations of existing close-ups. Check
   cross-dataset near-duplicates against all reserved evaluation sources.
4. Capture a short IMX477 sample at the intended focus, distance, exposure and
   entrance/tunnel geometry. Check whether mites are resolvable after model-input
   resizing before committing to a large annotation effort. Include healthy bees
   and confusing backgrounds; an unlabelled object is not a verified negative.
5. Create a new versioned dataset and a more representative validation set using
   source/capture grouping. Reserve independent camera sessions for final testing.
   Keep the current test set closed. If validation labels change, re-evaluate the
   old baseline on that same revision before claiming an improvement.

Data diversity/representativeness is the largest limitation of the current
accuracy claim; label-policy repair is the immediate prerequisite for trustworthy
comparisons. Keep standard two-class YOLOv8n for the next controlled training run.
More epochs alone cannot fill this coverage gap.

This follows the paper's emphasis on annotation correction and curation
(§4.2, pages 30–37), without assuming its reported counts, splits or training
sequence are a fully reproducible recipe.

## Artifacts and reproduction

- Compact metrics, hashes and label-review queue:
  [`reports/bee-v14-baseline-validation.json`](reports/bee-v14-baseline-validation.json).
- Evaluation script: [`../tools/evaluate_bee_baseline.py`](../tools/evaluate_bee_baseline.py).
- Mac artifacts: `training-artifacts/bee-v14-baseline-val-review-v2/` (Git-ignored,
  approximately 19 MB). Includes checkpoint and metadata backup, raw predictions,
  curves, confusion matrices, 53 annotated pairs and full contact sheets.
- WSL artifacts: `/home/tim/bee-mite-training/evaluations/bee-v14-baseline-val-review-v2/`.
- WSL execution log: `/home/tim/bee-mite-training/logs/bee-v14-baseline-val-review-v2.log`.
- [PR curve](../training-artifacts/bee-v14-baseline-val-review-v2/validator/BoxPR_curve.png)
  and [confusion matrix at 0.30](../training-artifacts/bee-v14-baseline-val-review-v2/confusion-at-0.30/confusion_matrix.png).

Run the script using the **existing WSL virtual environment**, supplying a new
output name (it refuses overwrite):

```bash
cd /home/tim/bee-mite-training
.venv/bin/python evaluate-bee-baseline-v2.py \
  --workspace /home/tim/bee-mite-training \
  --name bee-v14-baseline-val-review-v3
```

The local script and archived v2 script have the same hash. The archived copy is
unchanged; the repo script has since been generalized to accept `--dataset` and
`--checkpoint` for later dataset versions. It uses a validation-only
YAML without a test path, `imgsz=640`, batch 8, CUDA device 0, FP32, prediction
collection confidence 0.001, NMS IoU 0.7, and max 300 detections/image. Original
checkpoint, manifest, training settings and results were hashed before and after;
all checked hashes were unchanged. Supplementary `contact-sheets.py` and
`fixed-confusion.py` are archived with the artifacts.

The first review attempt (`...-v1`) completed validation but stopped while accessing
the confusion-matrix API. That partial directory/log is preserved. The corrected
v2 run completed all stages; the report uses v2 only. No baseline files were replaced.

Hardware-independent diagnostic-count tests:

```bash
python3 -m unittest tests.test_training_evaluation
```

Six tests pass. The evaluation itself also asserts image/object counts and original
artifact hashes. This does not validate the full application or inherited test suite.

### Image attribution

Review images derive from Alice's Bee v14 dataset:
<https://universe.roboflow.com/alice-fsfw8/bee-0flyv/dataset/14>.
The export identifies CC BY 4.0: <https://creativecommons.org/licenses/by/4.0/>.
Overlays/contact sheets were added for this review. Original attribution files
remain in the prepared WSL dataset. Upstream image rights/provenance have not been
independently verified; source images/checkpoints are kept out of Git, and nothing
was published or pushed.

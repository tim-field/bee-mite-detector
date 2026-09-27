# Training handoff: bee/varroa detector (concise)

## End goal
Train **our own bee/varroa YOLOv8n**, following `docs/001252261-FYP_Report.pdf`
§4.2 "Dataset Acquisition and Preparation" (four Roboflow datasets, progressive
training phases), then export/compile it for the Pi's Hailo-8 and deploy it,
replacing the stock `first_15k.hef` only after accuracy and compatibility checks.

**Where we are:** end of the guide's **Phase 1** (first dataset curated, baseline
trained). Datasets 2–4, combined/progressive training, and native Hailo
compilation are ahead. Long-form history: `docs/training-handoff-archive.md`.

Work in bounded steps; confirm with the user before large downloads, training
runs, compiler installation, or Pi deployment.

## Infrastructure
| Where | Access | Notes |
| --- | --- | --- |
| Mac checkout | `/Users/tim/dev/bee-mite-detector` | Dev copy. Origin `git@github.com:tim-field/bee-mite-detector.git`. Repo edits are **not** auto-deployed. |
| WSL2 training host | `ssh -p 2222 tim@192.168.8.238` | Ubuntu 26.04, RTX 3060 Ti 8 GB, ~16 GB RAM. Workspace `/home/tim/bee-mite-training`; `.venv` = Python 3.11.16, PyTorch 2.11+cu128, Ultralytics 8.4.162. `tmux` survives SSH drops, not WSL/Windows shutdown — keep Windows awake during runs. |
| Raspberry Pi 5 | `ssh tim@192.168.8.219` | App `/home/tim/bee-mite-detector`; dashboard `http://192.168.8.219:5000` (unauthenticated, trusted LAN only); user service `bee-mite-detector` (not boot-enabled). Working Hailo-8 stack: HailoRT 4.23.0 / TAPPAS 5.1.0, IMX477 on CAM0. Details: `docs/raspberry-pi-setup.md`. |

## Guide mapping (FYP §4.2)
| Phase | Guide dataset | Status |
| --- | --- | --- |
| 1 | Bee Detection (Alice), 436 imgs | ✅ Done — actual export 537; audited, curated, baseline trained |
| 2 | Beehive Detection (Bolo), 381 imgs | ❌ Not started |
| 3 | High-res Beehive (Alice), 6,611 imgs (select 1,000) | ❌ Not started |
| 4 | Large Beehive (Bee), 17,619 imgs (select 15,000) | ❌ Not started |

Candidate URLs — verify contents, licences, class order and formats first:
- Bolo: <https://universe.roboflow.com/bolo-q0wr5/beehive-detection/dataset/2>
- Alice Beehive: <https://universe.roboflow.com/alice-fsfw8/beehive-a1iyw/dataset/7>
- Bee Beehive: <https://universe.roboflow.com/bee-9phqe/beehive-qyqml/dataset/5>

The PDF is a guide, not a reproducible recipe: its image/label counts do not
match the real exports, and its curated splits/weights were not supplied.

## Current dataset and baseline results
- Latest revision **`bee-v14-entrance-v6`** in `training-artifacts/image-review/exports/`
  (Git-ignored; v2–v5 frozen): train **278** imgs (488 bee / 783 varroa),
  valid **13** imgs / **8 unique scenes** (31 bee / 15 varroa).
- Every revision has `LABEL-EDITS.md` + `review.json` `post_export_edits`; all
  582 data-file hashes verified on Mac and WSL each move.
- Checkpoint `runs/bee-v14-baseline/weights/best.pt` on v6 val: bee AP50 **45.9%**,
  varroa AP50 **76.8%**, mean AP50 61.3%. Compare scores only within the same revision.
- Known failure modes: whole bees classified as mites (`68_jpg`: 5/16 bee boxes
  scored as mites, 0.34–0.76), blurred flying bees missed. The guide's
  magnified-mite problem was addressed by our curation.
- Coverage limits: val has **no mite box <32 px**, no empty/background scenes, and
  only 8 unique scenes; train still holds 186 mite boxes <32 px.

## What Phase 1 covered
- 537-image Alice export audited: 141 polygon annotations converted to boxes,
  splits rebuilt by source group (no leakage), duplicates checked.
- User curated out brood and magnified-close-up groups.
- Full validation label review completed — all 8 queue items resolved
  (exclusions, `65_jpg` bee label, `52_jpg` partial bees, `68_jpg` extra bees,
  one under-annotated entrance scene moved to train).
- Baseline and 5-epoch pilot trained; validation tooling and tests built.

## Repo tooling
- `tools/evaluate_bee_baseline.py` — validation-only review. Run with the WSL
  `.venv`: `--workspace /home/tim/bee-mite-training --dataset datasets/<x>
  --checkpoint runs/bee-v14-baseline/weights/best.pt --name <new-name>`
  (refuses overwrite). 7 tests in `tests/test_training_evaluation.py`.
- `tools/review_dataset.py` + `.html` — local label-review UI. Workspace
  `training-artifacts/image-review/` (decisions revision 206); serve on the Mac
  at `http://127.0.0.1:8765` when needed.
- Image auditing that works well: render labelled overlays/crops via Chrome
  DevTools screenshots (see session history) and use the evaluator's `examples/`
  GT-vs-prediction pairs. Practical for batch review of new datasets.
- Detailed reports: `docs/bee-v14-baseline-validation.md` (53-image review +
  queue), `docs/bee-v14-entrance-v2-baseline-validation.md` (v2–v6 revisions),
  `docs/reports/*.json`, `docs/dataset-review.md`.

## Next steps
1. **Audit datasets 2–4**: download, licence check, format/class-map audit,
   near-duplicate check against our val/test scenes (bounded, no training).
2. Build a combined curated dataset (~1,750-image equivalent) from phases 1–3;
   keep the original test holdout closed.
3. **Progressive training** from the current checkpoint, evaluated on the
   curated val; change one major factor at a time.
4. Final large-data phase, then ONNX export → Hailo-8 compile → deploy a new
   named HEF with rollback (`BEE_HEF`); keep the working Pi stack intact.

## Hard rules
- Never restore or use the upstream repo's published email credentials; email
  stays opt-in; SMTP debug logging stays off.
- Do not blindly follow the old README's Hailo instructions; do not downgrade Pi
  drivers, replace native Python packages, or change boot config; Pi sudo needs
  a password.
- Do not run the upstream hailo helper `setup.py`; it downloads unrelated models
  and pins NumPy <2.
- Transfer datasets without `rsync --delete`; update `data.yaml` paths after
  moving; verify hashes.
- Do not commit datasets, checkpoints, caches, or credentials (Git-ignored).
  Commit only when asked; never push unprompted.

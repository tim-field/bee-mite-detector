"""Validation-only review of a trained YOLO checkpoint; never trains or deploys.

Dataset and checkpoint are configurable; the defaults reproduce the bee-v14
baseline review. Run with the existing WSL training environment (see
docs/training-handoff.md). Outputs are exclusive/new; originals are hashed/copied,
not modified. The custom fixed-threshold counts use confidence-ordered,
class-aware greedy matching at IoU >= 0.5, not Ultralytics' internal AP matching
implementation.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil


def iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1]))
    area = lambda x: max(0, x[2] - x[0]) * max(0, x[3] - x[1])
    union = area(a) + area(b) - intersection
    return intersection / union if union else 0.0


def match_boxes(truth, predictions, confidence, min_iou=0.5):
    """Return (GT index, prediction index) pairs and unmatched GT/pred indices."""
    remaining = set(range(len(truth)))
    pairs, false_positives = [], []
    for pi in sorted(range(len(predictions)), key=lambda i: -predictions[i]['confidence']):
        pred = predictions[pi]
        if pred['confidence'] < confidence:
            continue
        candidates = [(iou(truth[gi]['xyxy'], pred['xyxy']), gi)
                      for gi in remaining if truth[gi]['class'] == pred['class']]
        overlap, gi = max(candidates, default=(-1, -1))
        if overlap >= min_iou:
            pairs.append((gi, pi))
            remaining.remove(gi)
        else:
            false_positives.append(pi)
    return pairs, sorted(remaining), false_positives


def summarize(records, confidence):
    counts = {c: Counter() for c in (0, 1)}
    sizes = {name: Counter() for name in ('<16px', '16-32px', '32-64px', '>=64px')}
    for record in records:
        truth, predictions = record['truth'], record['predictions']
        pairs, missed, extras = match_boxes(truth, predictions, confidence)
        matched = {gi for gi, _ in pairs}
        for gi, box in enumerate(truth):
            counts[box['class']]['tp' if gi in matched else 'fn'] += 1
            if box['class'] == 1:
                x1, y1, x2, y2 = box['xyxy']
                # All audited images are 640x640, so this is also model-input scale.
                side = min(x2 - x1, y2 - y1)
                bucket = '<16px' if side < 16 else '16-32px' if side < 32 else '32-64px' if side < 64 else '>=64px'
                sizes[bucket]['total'] += 1
                sizes[bucket]['detected'] += int(gi in matched)
        for pi in extras:
            counts[predictions[pi]['class']]['fp'] += 1
    def stats(c):
        tp, fp, fn = c['tp'], c['fp'], c['fn']
        return dict(tp=tp, fp=fp, fn=fn,
                    precision=tp / (tp + fp) if tp + fp else None,
                    recall=tp / (tp + fn) if tp + fn else None)
    return {'confidence': confidence, 'iou': 0.5,
            'classes': {name: stats(counts[c]) for c, name in enumerate(('bee', 'varroa'))},
            'varroa_short_side': {k: {'total': v['total'], 'detected': v['detected'],
                                    'recall': v['detected'] / v['total'] if v['total'] else None}
                                  for k, v in sizes.items()}}


def derive_group(name):
    """Filename-derived review group, used when a dataset manifest lacks group data."""
    stem = re.sub(r'\.rf\.[0-9a-f]+', '', Path(name).stem)
    return re.sub(r'_rotated_\d+_degrees', '', stem)


def sha256(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save_json(path, value):
    def convert(x):
        if hasattr(x, 'tolist'):
            return x.tolist()
        raise TypeError(type(x).__name__)
    path.write_text(json.dumps(value, indent=2, default=convert) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--dataset', default='datasets/bee-v14-grouped-v1',
                        help='dataset directory (absolute or relative to the workspace)')
    parser.add_argument('--checkpoint', default='runs/bee-v14-baseline/weights/best.pt',
                        help='model checkpoint (absolute or relative to the workspace)')
    parser.add_argument('--name', default='bee-v14-baseline-val-review-v1')
    args = parser.parse_args()
    if not args.name or Path(args.name).name != args.name or args.name in ('.', '..'):
        parser.error('--name must be a single directory name')
    root = args.workspace.resolve()
    os.environ['YOLO_CONFIG_DIR'] = str(root / '.config/ultralytics')
    os.environ['MPLCONFIGDIR'] = str(root / '.config/matplotlib')
    os.environ['OMP_NUM_THREADS'] = '4'
    os.environ['MKL_NUM_THREADS'] = '4'
    import torch
    import ultralytics
    from ultralytics import YOLO, settings
    from PIL import Image, ImageDraw
    settings.update({'sync': False})
    torch.set_num_threads(4)
    os.chdir(root)
    output = root / 'evaluations' / args.name
    output.mkdir(parents=True, exist_ok=False)
    dataset = (root / args.dataset).resolve()
    checkpoint = (root / args.checkpoint).resolve()
    val_dir = next((dataset / n for n in ('valid', 'val')
                    if (dataset / n / 'images').is_dir()), None)
    if val_dir is None:
        parser.error(f'no valid/ or val/ split with images under {dataset}')
    if not checkpoint.is_file():
        parser.error(f'checkpoint not found: {checkpoint}')
    val_name = val_dir.name
    run_dir = checkpoint.parent.parent
    candidates = [checkpoint, run_dir / 'args.yaml', run_dir / 'results.csv',
                  dataset / 'manifest.json', dataset / 'audit.json', dataset / 'data.yaml',
                  dataset / 'review.json', root / 'requirements-resolved.txt',
                  root / 'train-bee-v14-baseline.py', root / 'logs/bee-v14-baseline-status.json']
    originals = [p for p in candidates if p.is_file()]

    def rel(path):
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)

    provenance = {'originals': {rel(p): sha256(p) for p in originals},
                  'torch': torch.__version__, 'ultralytics': ultralytics.__version__,
                  'gpu': torch.cuda.get_device_name(0), 'test_split_evaluated': False,
                  'evaluation_script_sha256': sha256(Path(__file__)),
                  'settings': {'imgsz': 640, 'batch': 8, 'device': 0, 'half': False,
                               'collection_confidence': 0.001, 'nms_iou': 0.7, 'max_det': 300}}
    save_json(output / 'provenance.json', provenance)
    for path in originals:
        target = output / 'preserved' / rel(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    shutil.copy2(Path(__file__), output / 'evaluate_bee_baseline.py')
    # No test path in this evaluation config. Train points at val only to satisfy
    # the dataset schema; model.val does not train or open a training loader.
    config = output / 'validation-only.yaml'
    config.write_text(f'path: {dataset}\ntrain: {val_name}/images\nval: {val_name}/images\nnames:\n  0: bee\n  1: varroa\n')
    model = YOLO(str(checkpoint))
    metrics = model.val(data=str(config), split='val', imgsz=640, batch=8, device=0,
                        workers=2, conf=0.001, iou=0.7, max_det=300, half=False,
                        augment=False, plots=True, verbose=True,
                        project=str(output), name='validator', exist_ok=False)
    save_json(output / 'metrics.json', {'mean': metrics.results_dict,
                                      'per_class': metrics.summary(),
                                      'curves': metrics.curves_results})
    save_json(output / 'confusion-matrix.json', metrics.confusion_matrix.matrix)
    groups = {}
    manifest_path = dataset / 'manifest.json'
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        groups = {Path(r['source']).name: r['group'] for r in manifest
                  if r.get('split') == val_name and 'group' in r}
    images = sorted(p for p in (dataset / val_name / 'images').iterdir()
                    if p.suffix.lower() in ('.jpg', '.jpeg', '.png'))
    assert images, 'No validation images found'
    records = []
    for result in model.predict(source=[str(p) for p in images], stream=True,
                                imgsz=640, batch=8, device=0, conf=0.001, iou=0.7,
                                max_det=300, half=False, augment=False, verbose=False,
                                save=False):
        image = Path(result.path)
        assert result.orig_shape == (640, 640)
        labels = dataset / val_name / 'labels' / (image.stem + '.txt')
        truth = []
        for line in labels.read_text().splitlines():
            c, cx, cy, w, h = map(float, line.split())
            truth.append({'class': int(c), 'xyxy': [(cx-w/2)*640, (cy-h/2)*640,
                                                   (cx+w/2)*640, (cy+h/2)*640]})
        predictions = [{'class': int(c), 'confidence': float(conf), 'xyxy': box}
                       for c, conf, box in zip(result.boxes.cls.cpu().tolist(),
                                               result.boxes.conf.cpu().tolist(),
                                               result.boxes.xyxy.cpu().tolist())]
        records.append({'image': image.name,
                        'group': groups.get(image.name) or derive_group(image.name),
                        'image_sha256': sha256(image), 'label_sha256': sha256(labels),
                        'truth': truth, 'predictions': predictions})
    assert len(records) == len(images)
    truth_counts = Counter(b['class'] for r in records for b in r['truth'])
    empty_labels = sum(1 for r in records if not r['truth'])
    save_json(output / 'predictions.json', records)
    save_json(output / 'dataset.json', {
        'dataset': rel(dataset), 'checkpoint': rel(checkpoint),
        'images': len(records),
        'independent_filename_groups': len({r['group'] for r in records}),
        'truth_boxes': {('bee' if c == 0 else 'varroa'): n
                        for c, n in sorted(truth_counts.items())},
        'empty_label_files': empty_labels,
    })
    save_json(output / 'thresholds.json', [summarize(records, t) for t in (0.05, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.7)])
    example_dir = output / 'examples'
    example_dir.mkdir()
    index = []
    for n, record in enumerate(records):
        truth, predictions = record['truth'], record['predictions']
        pairs, missed, extras = match_boxes(truth, predictions, 0.25)
        matched = {gi for gi, _ in pairs}
        pair_image = Image.new('RGB', (1280, 680), 'white')
        original = Image.open(dataset / val_name / 'images' / record['image']).convert('RGB')
        for col in range(2):
            pair_image.paste(original, (col * 640, 40))
        draw = ImageDraw.Draw(pair_image)
        draw.text((8, 3), f'{n:02d} {record["group"]} | GT: green=matched, red=missed', fill='black')
        draw.text((648, 3), 'Predictions >=0.25: green=matched, orange=unmatched; IoU>=0.5', fill='black')
        for gi, box in enumerate(truth):
            x1, y1, x2, y2 = box['xyxy']
            color = 'lime' if gi in matched else 'red'
            draw.rectangle((x1, y1+40, x2, y2+40), outline=color, width=2)
            draw.text((x1, max(40, y1+28)), ('bee', 'mite')[box['class']], fill=color, stroke_width=1, stroke_fill='black')
        for pi, box in enumerate(predictions):
            if box['confidence'] < 0.25:
                continue
            x1, y1, x2, y2 = box['xyxy']
            color = 'orange' if pi in extras else 'lime'
            draw.rectangle((x1+640, y1+40, x2+640, y2+40), outline=color, width=2)
            draw.text((x1+640, max(40, y1+28)), f'{("bee", "mite")[box["class"]]} {box["confidence"]:.2f}', fill=color, stroke_width=1, stroke_fill='black')
        pair_image.save(example_dir / f'{n:02d}.jpg', quality=90)
        index.append({'id': n, 'image': record['image'], 'group': record['group'],
                      'matches': pairs, 'missed_truth': missed, 'unmatched_predictions': extras})
    save_json(output / 'examples-index.json', index)
    assert all(sha256(Path(p) if os.path.isabs(p) else root / p) == digest
               for p, digest in provenance['originals'].items())
    save_json(output / 'status.json', {'status': 'completed', 'test_split_evaluated': False,
                                       'original_hashes_unchanged': True})
    print(f'Completed: {output}', flush=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Loopback-only, dependency-free review/export of the prepared bee-v14 dataset.

Only train/valid assets are opened or served. Review groups start from manifest
groups and can be manually partitioned without changing source splits; test stays hidden. Run --help; see docs/dataset-review.md.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shutil
import tempfile
import threading
from urllib.parse import urlsplit

SPLITS = ('train', 'valid')
STATUSES = ('unreviewed', 'keep', 'exclude', 'unsure')
REASONS = ('close_up', 'brood', 'off_topic', 'quality', 'other')


class ReviewError(ValueError):
    pass


class Conflict(ReviewError):
    pass


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def atomic_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.review-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def safe_file(root, relative):
    path = root / relative
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise ReviewError(f'Missing or unsafe source file: {relative}')
    return path


def read_boxes(path):
    boxes = []
    for line in path.read_text().splitlines():
        values = [float(v) for v in line.split()]
        if len(values) != 5 or not all(math.isfinite(v) for v in values):
            raise ReviewError(f'Expected detection boxes, not polygons: {path.name}')
        cls, cx, cy, w, h = values
        if cls not in (0, 1) or not (0 < w <= 1 and 0 < h <= 1):
            raise ReviewError(f'Invalid box: {path.name}')
        if min(cx-w/2, cy-h/2) < -0.00001 or max(cx+w/2, cy+h/2) > 1.00001:
            raise ReviewError(f'Box outside image: {path.name}')
        boxes.append([int(cls), cx, cy, w, h])
    return boxes


class Review:
    def __init__(self, dataset, workspace):
        self.dataset = Path(dataset).resolve()
        self.workspace = Path(workspace).resolve()
        if self.workspace.is_relative_to(self.dataset):
            raise ReviewError('Review workspace must be outside the source dataset.')
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.state_path = self.workspace / 'decisions.json'
        manifest_path = safe_file(self.dataset, 'manifest.json')
        self.manifest_hash = digest(manifest_path)
        self.manifest = json.loads(manifest_path.read_text())
        self.groups = {}
        self.images = {}
        self.hashes = {'manifest.json': self.manifest_hash}
        group_splits, hash_splits, pixel_splits = {}, {}, {}
        seen_names = set()
        for row in self.manifest:
            split = row['split']
            if split not in (*SPLITS, 'test'):
                raise ReviewError(f'Unknown split: {split}')
            group = row['group']
            if not isinstance(group, str) or not group:
                raise ReviewError('Invalid manifest group')
            # Metadata-only leakage checks include test, without opening test assets.
            for mapping, key in ((group_splits, group), (hash_splits, row['sha256']),
                                 (pixel_splits, row.get('pixel_hash'))):
                if key is not None and mapping.setdefault(key, split) != split:
                    raise ReviewError('Manifest groups/hashes cross split boundaries.')
            if split == 'test':
                continue
            name = Path(row['source']).name
            if Path(name).suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
                raise ReviewError(f'Unsupported image: {name}')
            image_rel = f'{split}/images/{name}'
            label_rel = f'{split}/labels/{Path(name).stem}.txt'
            if (split, Path(name).stem) in seen_names:
                raise ReviewError(f'Duplicate image/label identity: {name}')
            seen_names.add((split, Path(name).stem))
            image = safe_file(self.dataset, image_rel)
            label = safe_file(self.dataset, label_rel)
            image_hash = digest(image)
            if image_hash != row['sha256']:
                raise ReviewError(f'Image differs from manifest: {name}')
            boxes = read_boxes(label)
            expected = row['boxes']
            if len(boxes) != len(expected) or any(
                    len(b) != 5 or any(abs(x-y) > 0.000002 for x, y in zip(a, b))
                    for a, b in zip(boxes, expected)):
                raise ReviewError(f'Labels differ from prepared manifest: {name}')
            self.hashes[image_rel] = image_hash
            self.hashes[label_rel] = digest(label)
            image_id = hashlib.sha256(image_rel.encode()).hexdigest()
            group_id = hashlib.sha256(group.encode()).hexdigest()
            item = {'id': image_id, 'name': name, 'split': split, 'boxes': boxes,
                    'group_id': group_id, 'image_rel': image_rel, 'label_rel': label_rel,
                    'manifest_row': row}
            self.images[image_id] = item
            entry = self.groups.setdefault(group_id, {'id': group_id, 'name': group,
                                                      'split': split, 'images': []})
            entry['images'].append(image_id)
        if not self.images or any(not any(g['split'] == s for g in self.groups.values()) for s in SPLITS):
            raise ReviewError('Both prepared train and valid splits are required.')
        for split in SPLITS:
            for folder in ('images', 'labels'):
                actual = {str(p.relative_to(self.dataset)) for p in (self.dataset / split / folder).iterdir() if not p.name.startswith('.')}
                expected = {key for key in self.hashes if key.startswith(f'{split}/{folder}/')}
                if actual != expected:
                    raise ReviewError(f'Unexpected or missing files in {split}/{folder}')
        for filename in ('README.dataset.txt', 'README.roboflow.txt'):
            path = safe_file(self.dataset, filename)
            self.hashes[filename] = digest(path)
        self.fingerprint = hashlib.sha256(json_bytes(self.hashes)).hexdigest()
        self.state = {'schema': 1, 'dataset_fingerprint': self.fingerprint,
                      'revision': 0, 'decisions': {}, 'partitions': []}
        if self.state_path.exists():
            state = json.loads(self.state_path.read_text())
            if state.get('schema') != 1 or state.get('dataset_fingerprint') != self.fingerprint:
                raise ReviewError('Saved review belongs to a different dataset. Use a new workspace.')
            if type(state.get('revision')) is not int or state['revision'] < 0:
                raise ReviewError('Invalid saved revision')
            for partition in state.get('partitions', []):
                self.apply_partition(partition['group'], partition['selected'])
            for gid, decision in state['decisions'].items():
                self.validate_decision(gid, decision)
            self.state = state

    def partition_plan(self, gid, selected):
        if gid not in self.groups or not isinstance(selected, list) or not all(isinstance(i, str) for i in selected):
            raise ReviewError('Invalid group selection')
        images = self.groups[gid]['images']
        if (len(set(selected)) != len(selected) or not set(selected) < set(images)
                or not selected):
            raise ReviewError('Select some, but not all, images from this group.')
        new_id = hashlib.sha256((gid + ':' + ','.join(sorted(selected))).encode()).hexdigest()
        return new_id

    def apply_partition(self, gid, selected):
        new_id = self.partition_plan(gid, selected)
        group = self.groups[gid]
        self.groups[new_id] = {**group, 'id': new_id,
                               'name': group['name'] + ' [subset ' + new_id[:6] + ']',
                               'images': [i for i in group['images'] if i in selected]}
        group['images'] = [i for i in group['images'] if i not in selected]
        for image_id in selected:
            self.images[image_id]['group_id'] = new_id
        return new_id

    def partition(self, gid, selected, revision):
        """Separate a mixed review group; NEVER change the manifest's source group/split."""
        with self.lock:
            self.check_revision(revision)
            new_id = self.partition_plan(gid, selected)
            state = json.loads(json.dumps(self.state))
            state.setdefault('partitions', []).append({'group': gid, 'selected': selected})
            state['decisions'].pop(gid, None)  # Both resulting groups require fresh review.
            state['revision'] += 1
            atomic_json(self.state_path, state)
            self.apply_partition(gid, selected)
            self.state = state
            return {'state': self.snapshot(), 'new_group': new_id}

    def validate_decision(self, gid, decision):
        if gid not in self.groups or not isinstance(decision, dict):
            raise ReviewError('Unknown group or invalid decision')
        status = decision.get('status')
        if status not in STATUSES:
            raise ReviewError('Invalid status')
        if decision.get('reason', '') not in ('', *REASONS):
            raise ReviewError('Invalid exclusion reason')
        if status == 'exclude' and decision.get('reason') not in REASONS:
            raise ReviewError('Choose an exclusion reason')
        if not isinstance(decision.get('notes', ''), str) or len(decision.get('notes', '')) > 2000:
            raise ReviewError('Notes must be at most 2000 characters')

    def check_revision(self, revision):
        if type(revision) is not int or revision != self.state['revision']:
            raise Conflict('Review changed in another tab. Reloaded; try again.')

    def decide(self, gid, status, reason, notes, revision):
        decision = {'status': status, 'reason': reason, 'notes': notes,
                    'updated_at': datetime.now(timezone.utc).isoformat()}
        with self.lock:
            self.check_revision(revision)
            self.validate_decision(gid, decision)
            state = json.loads(json.dumps(self.state))
            if status == 'unreviewed':
                state['decisions'].pop(gid, None)
            else:
                state['decisions'][gid] = decision
            state['revision'] += 1
            atomic_json(self.state_path, state)
            self.state = state
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            groups = []
            counts = {s: {'groups': 0, 'images': 0} for s in STATUSES}
            retained = {s: {'images': 0, 'bee_boxes': 0, 'varroa_boxes': 0} for s in SPLITS}
            for gid, group in self.groups.items():
                decision = self.state['decisions'].get(gid, {'status': 'unreviewed', 'reason': '', 'notes': ''})
                status = decision['status']
                counts[status]['groups'] += 1
                counts[status]['images'] += len(group['images'])
                images = [{k: self.images[i][k] for k in ('id', 'name', 'boxes')} for i in group['images']]
                groups.append({**group, 'images': images, 'decision': decision})
                if status == 'keep':
                    dest = retained[group['split']]
                    dest['images'] += len(images)
                    for image in images:
                        for cls, *_ in image['boxes']:
                            dest['bee_boxes' if cls == 0 else 'varroa_boxes'] += 1
            unresolved = counts['unreviewed']['groups'] + counts['unsure']['groups']
            problems = []
            if unresolved:
                problems.append(f'{unresolved} groups still unreviewed or unsure.')
            for split, stats in retained.items():
                if not stats['images'] or not stats['bee_boxes'] or not stats['varroa_boxes']:
                    problems.append(f'Kept {split} split needs images and labels for both bee and varroa.')
            return {'revision': self.state['revision'], 'groups': groups, 'counts': counts,
                    'retained': retained, 'export_problems': problems,
                    'dataset': str(self.dataset), 'workspace': str(self.workspace),
                    'fingerprint': self.fingerprint, 'test_hidden': True}

    def export(self, name, revision):
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', name):
            raise ReviewError('Use a version name with letters, numbers, dashes or underscores (max 80).')
        with self.lock:
            self.check_revision(revision)
            snapshot = self.snapshot()
            if snapshot['export_problems']:
                raise ReviewError(' '.join(snapshot['export_problems']))
            exports = self.workspace / 'exports'
            exports.mkdir(exist_ok=True)
            destination = exports / name
            if destination.exists():
                raise Conflict('That dataset version already exists. Choose a new name.')
            for relative, expected in self.hashes.items():
                if digest(safe_file(self.dataset, relative)) != expected:
                    raise ReviewError(f'Source changed since review opened: {relative}')
            temporary = Path(tempfile.mkdtemp(prefix='.building-', dir=exports))
            try:
                kept_rows, kept_hashes = [], {}
                for split in SPLITS:
                    for folder in ('images', 'labels'):
                        (temporary / split / folder).mkdir(parents=True)
                for image in self.images.values():
                    if self.state['decisions'][image['group_id']]['status'] != 'keep':
                        continue
                    for key in ('image_rel', 'label_rel'):
                        relative = image[key]
                        shutil.copy2(safe_file(self.dataset, relative), temporary / relative)
                        copied_hash = digest(temporary / relative)
                        if copied_hash != self.hashes[relative]:
                            raise ReviewError(f'Source changed during copy: {relative}')
                        kept_hashes[relative] = copied_hash
                    kept_rows.append(image['manifest_row'])
                for filename in ('README.dataset.txt', 'README.roboflow.txt'):
                    shutil.copy2(self.dataset / filename, temporary / filename)
                    if digest(temporary / filename) != self.hashes[filename]:
                        raise ReviewError(f'Attribution changed during copy: {filename}')
                (temporary / 'manifest.json').write_bytes(json_bytes(kept_rows))
                # Absolute path makes this work without Ultralytics dataset-root guessing.
                # On transfer to WSL, regenerate path there, leaving split membership intact.
                (temporary / 'data.yaml').write_text(
                    f'path: {json.dumps(str(destination))}\ntrain: train/images\nval: valid/images\n'
                    'names:\n  0: bee\n  1: varroa\n')
                (temporary / 'review.json').write_bytes(json_bytes({
                    'source_dataset': str(self.dataset), 'source_fingerprint': self.fingerprint,
                    'source_manifest_sha256': self.manifest_hash, 'decisions': self.state,
                    'summary': snapshot['retained'], 'files_sha256': kept_hashes,
                    'test_exported': False, 'splits_preserved': True,
                    'created_at': datetime.now(timezone.utc).isoformat()}))
                (temporary / 'REVIEW-NOTES.md').write_text(
                    '# Reviewed training/validation subset\n\n'
                    'Original source files and split membership were not changed. Image and label\n'
                    'pairs were copied together. Exclusions apply to complete review groups;\n'
                    'manual review partitions do not change original source groups or splits.\n'
                    'Test images are deliberately NOT included; use the untouched original holdout\n'
                    'only after model selection is frozen. This is not a new final test set.\n'
                    'Compare the old and new model on the same reviewed validation subset.\n'
                    'The data.yaml path is local: update it if moving this dataset to WSL.\n'
                    'Keep both attribution README files; verify upstream rights before publication.\n')
                # Reserve the name exclusively; never merge into/replace an existing version.
                destination.mkdir(exist_ok=False)
                try:
                    for child in temporary.iterdir():
                        shutil.move(str(child), destination / child.name)
                    (destination / 'COMPLETE').write_text('Export complete.\n')
                except BaseException:
                    # Leave a visibly incomplete version instead of deleting possible user work.
                    raise
                return {'path': str(destination), 'summary': snapshot['retained'], 'test_exported': False}
            finally:
                shutil.rmtree(temporary)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, review):
        self.review = review
        self.token = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(24)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, status, body, kind='application/json'):
        if not isinstance(body, bytes):
            body = json_bytes(body)
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy',
                         f"default-src 'self'; script-src 'nonce-{self.server.nonce}'; "
                         "style-src 'self' 'unsafe-inline'; img-src 'self'; object-src 'none'; "
                         "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def allowed_host(self):
        port = self.server.server_port
        return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

    def do_GET(self):
        if not self.allowed_host():
            return self.send(403, {'error': 'Localhost requests only'})
        path = urlsplit(self.path).path
        if path == '/':
            html = Path(__file__).with_name('review_dataset.html').read_text()
            html = html.replace('__TOKEN__', self.server.token).replace('__NONCE__', self.server.nonce)
            return self.send(200, html.encode(), 'text/html; charset=utf-8')
        if path == '/api/state':
            return self.send(200, self.server.review.snapshot())
        if path.startswith('/image/'):
            item = self.server.review.images.get(path.removeprefix('/image/'))
            if item:
                try:
                    image = safe_file(self.server.review.dataset, item['image_rel'])
                    return self.send(200, image.read_bytes(), mimetypes.guess_type(image.name)[0] or 'application/octet-stream')
                except (OSError, ReviewError):
                    return self.send(409, {'error': 'Source image unavailable'})
        return self.send(404, {'error': 'Not found'})

    def do_POST(self):
        port = self.server.server_port
        origin = self.headers.get('Origin')
        if (not self.allowed_host() or self.headers.get('X-Review-Token') != self.server.token
                or (origin and origin not in (f'http://127.0.0.1:{port}', f'http://localhost:{port}'))):
            return self.send(403, {'error': 'Invalid local review request'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 10000:
                raise ReviewError('Invalid request size')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ReviewError('Expected JSON object')
            if self.path == '/api/decision':
                result = self.server.review.decide(data.get('group'), data.get('status'),
                                                  data.get('reason', ''), data.get('notes', ''), data.get('revision'))
            elif self.path == '/api/partition':
                result = self.server.review.partition(data.get('group'), data.get('selected'), data.get('revision'))
            elif self.path == '/api/export':
                result = self.server.review.export(data.get('name'), data.get('revision'))
            else:
                return self.send(404, {'error': 'Not found'})
            self.send(200, result)
        except Conflict as exc:
            self.send(409, {'error': str(exc)})
        except (ReviewError, ValueError, TypeError, KeyError) as exc:
            self.send(400, {'error': str(exc)})
        except OSError as exc:
            self.send(500, {'error': f'Filesystem operation failed: {exc}'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True, help='Prepared grouped dataset; not raw Roboflow download')
    parser.add_argument('--workspace', type=Path, default=Path('training-artifacts/image-review'))
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if args.workspace.resolve().is_relative_to(args.dataset.resolve()):
        parser.exit(1, 'Review workspace must be outside the source dataset.\n')
    # One writer per workspace, including across separately launched processes.
    import fcntl
    args.workspace.mkdir(parents=True, exist_ok=True)
    with (args.workspace / '.server.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, 'This review workspace is already open in another server.\n')
        try:
            review = Review(args.dataset, args.workspace)
            server = Server(('127.0.0.1', args.port), review)
        except (ReviewError, OSError, ValueError, KeyError) as exc:
            parser.exit(1, f'Cannot open review: {exc}\n')
        print(f'Review ready: http://127.0.0.1:{server.server_port}\n'
              f'{len(review.images)} train/valid images; test hidden.\n'
              f'Decisions: {review.state_path}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == '__main__':
    main()

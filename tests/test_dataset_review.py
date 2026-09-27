"""No GPU, browser, Flask or external packages required."""
import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from tools.review_dataset import Conflict, Review, ReviewError, Server


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.work = self.root / 'work'
        self.source.mkdir()
        self.manifest = []
        # Two train groups, one with variants; one validation group. Both classes.
        for split, group, name in [('train', 'adult', 'a.jpg'), ('train', 'adult', 'a_flip.jpg'),
                                   ('train', 'brood', 'b.jpg'), ('valid', 'entrance', 'v.jpg')]:
            for folder in ('images', 'labels'):
                (self.source / split / folder).mkdir(parents=True, exist_ok=True)
            payload = ('image-' + name).encode()
            (self.source / split / 'images' / name).write_bytes(payload)
            (self.source / split / 'labels' / (Path(name).stem + '.txt')).write_text(
                '0 0.5 0.5 0.8 0.8\n1 0.5 0.5 0.1 0.1\n')
            self.manifest.append({'source': f'train/images/{name}', 'split': split, 'group': group,
                                  'sha256': hashlib.sha256(payload).hexdigest(),
                                  'boxes': [[0, .5, .5, .8, .8], [1, .5, .5, .1, .1]]})
        # Only test metadata exists. Opening a test asset would fail.
        self.manifest.append({'source': 'test/images/SECRET.jpg', 'split': 'test', 'group': 'SECRET',
                              'sha256': 'reserved-test-hash', 'boxes': []})
        self.write_manifest()
        for name in ('README.dataset.txt', 'README.roboflow.txt'):
            (self.source / name).write_text('Attribution retained\n')
        self.review = Review(self.source, self.work)

    def write_manifest(self):
        (self.source / 'manifest.json').write_text(json.dumps(self.manifest))

    def gid(self, name):
        return next(gid for gid, g in self.review.groups.items() if g['name'] == name)

    def decide(self, name, status, reason=''):
        return self.review.decide(self.gid(name), status, reason, '', self.review.state['revision'])

    def ready(self):
        self.decide('adult', 'keep')
        self.decide('brood', 'exclude', 'brood')
        self.decide('entrance', 'keep')

    def test_only_train_validation_visible(self):
        snapshot = self.review.snapshot()
        self.assertEqual(len(snapshot['groups']), 3)
        self.assertEqual(len(self.review.images), 4)
        self.assertNotIn('SECRET', json.dumps(snapshot))
        self.assertTrue(snapshot['test_hidden'])
        self.assertFalse((self.source / 'test').exists())

    def test_decisions_apply_to_variants_and_persist(self):
        s = self.decide('adult', 'exclude', 'close_up')
        self.assertEqual(s['counts']['exclude'], {'groups': 1, 'images': 2})
        loaded = Review(self.source, self.work)
        self.assertEqual(loaded.state, self.review.state)
        self.decide('adult', 'unreviewed')
        self.assertNotIn(self.gid('adult'), self.review.state['decisions'])

    def test_revision_conflict_does_not_overwrite(self):
        self.decide('adult', 'keep')
        before = self.review.state_path.read_bytes()
        with self.assertRaises(Conflict):
            self.review.decide(self.gid('adult'), 'exclude', 'brood', '', 0)
        self.assertEqual(before, self.review.state_path.read_bytes())

    def test_save_failure_does_not_change_memory(self):
        with patch('tools.review_dataset.atomic_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.decide('adult', 'keep')
        self.assertEqual(self.review.state['revision'], 0)
        self.assertEqual(self.review.state['decisions'], {})

    def test_invalid_decisions(self):
        for status, reason in [('bad', ''), ('exclude', ''), ('exclude', 'unknown')]:
            with self.assertRaises(ReviewError):
                self.decide('adult', status, reason)
        with self.assertRaises(ReviewError):
            self.review.decide('SECRET', 'keep', '', '', 0)
        self.assertEqual(self.review.state['revision'], 0)

    def test_export_unreviewed_unsure_and_empty_blocked(self):
        with self.assertRaises(ReviewError):
            self.review.export('new', 0)
        self.ready()
        self.decide('adult', 'unsure')
        with self.assertRaises(ReviewError):
            self.review.export('new', self.review.state['revision'])
        self.decide('adult', 'exclude', 'off_topic')
        with self.assertRaises(ReviewError):
            self.review.export('new', self.review.state['revision'])

    def test_export_pairs_splits_attribution_and_no_test(self):
        before = {str(p): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        self.ready()
        result = self.review.export('entrance-v2', self.review.state['revision'])
        exported = Path(result['path'])
        self.assertTrue((exported / 'COMPLETE').exists())
        self.assertEqual({p.name for p in (exported / 'train/images').iterdir()}, {'a.jpg', 'a_flip.jpg'})
        self.assertEqual({p.name for p in (exported / 'train/labels').iterdir()}, {'a.txt', 'a_flip.txt'})
        self.assertTrue((exported / 'valid/images/v.jpg').exists())
        self.assertFalse((exported / 'test').exists())
        self.assertNotIn('test:', (exported / 'data.yaml').read_text())
        self.assertIn(str(exported), (exported / 'data.yaml').read_text())
        for name in ('README.dataset.txt', 'README.roboflow.txt'):
            self.assertEqual((exported / name).read_bytes(), (self.source / name).read_bytes())
        for row in json.loads((exported / 'manifest.json').read_text()):
            self.assertIn(row['split'], ('train', 'valid'))
            self.assertNotEqual(row['group'], 'brood')
        after = {str(p): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        with self.assertRaises(Conflict):
            self.review.export('entrance-v2', self.review.state['revision'])

    def test_changed_source_blocks_export(self):
        self.ready()
        (self.source / 'train/labels/a.txt').write_text('')
        with self.assertRaises(ReviewError):
            self.review.export('new', self.review.state['revision'])
        self.assertFalse((self.work / 'exports/new').exists())

    def test_export_path_traversal_and_stale_revision(self):
        self.ready()
        for name in ('../escape', '/tmp/escape', '.', 'a/b', ''):
            with self.assertRaises(ReviewError):
                self.review.export(name, self.review.state['revision'])
        with self.assertRaises(Conflict):
            self.review.export('new', 0)

    def test_manifest_changes_reject_old_decisions(self):
        self.decide('adult', 'keep')
        self.manifest[0]['provenance_note'] = 'changed'
        self.write_manifest()
        with self.assertRaisesRegex(ReviewError, 'different dataset'):
            Review(self.source, self.work)

    def test_cross_split_groups_hashes_and_pixels_rejected(self):
        for key in ('group', 'sha256', 'pixel_hash'):
            original = self.manifest[-1].copy()
            if key == 'pixel_hash':
                self.manifest[0][key] = 'same-pixels'
            self.manifest[-1][key] = self.manifest[0][key]
            self.write_manifest()
            with self.assertRaisesRegex(ReviewError, 'cross split'):
                Review(self.source, self.root / ('bad-' + key))
            self.manifest[-1] = original

    def test_missing_or_mismatched_labels_rejected(self):
        label = self.source / 'train/labels/a.txt'
        label.write_text('1 0.5 0.5 0.1 0.1\n')
        with self.assertRaisesRegex(ReviewError, 'Labels differ'):
            Review(self.source, self.root / 'bad')
        label.unlink()
        with self.assertRaisesRegex(ReviewError, 'Missing'):
            Review(self.source, self.root / 'bad2')

    def test_symlink_escape_rejected(self):
        image = self.source / 'train/images/a.jpg'
        outside = self.root / 'outside.jpg'
        outside.write_bytes(image.read_bytes())
        image.unlink()
        image.symlink_to(outside)
        with self.assertRaisesRegex(ReviewError, 'unsafe'):
            Review(self.source, self.root / 'bad')

    def test_partition_persists_and_preserves_original_split_and_group(self):
        self.ready()
        adult = self.gid('adult')
        selected = [self.review.groups[adult]['images'][0]]
        result = self.review.partition(adult, selected, self.review.state['revision'])
        new_id = result['new_group']
        self.assertEqual(result['state']['counts']['unreviewed']['groups'], 2)
        loaded = Review(self.source, self.work)
        self.assertEqual(loaded.groups, self.review.groups)
        self.assertEqual(loaded.images[selected[0]]['group_id'], new_id)
        self.decide('adult', 'keep')
        self.review.decide(new_id, 'exclude', 'close_up', '', self.review.state['revision'])
        result = self.review.export('partitioned', self.review.state['revision'])
        exported = Path(result['path'])
        self.assertEqual({p.name for p in (exported / 'train/images').iterdir()}, {'a_flip.jpg'})
        rows = json.loads((exported / 'manifest.json').read_text())
        adult_row = next(r for r in rows if r['group'] == 'adult')
        self.assertEqual(adult_row['split'], 'train')
        self.assertEqual(adult_row['source'], 'train/images/a_flip.jpg')

    def test_partition_invalid_selection_and_disk_failure(self):
        adult = self.gid('adult')
        images = self.review.groups[adult]['images'][:]
        for selection in ([], images, ['SECRET'], [images[0], images[0]]):
            with self.assertRaises(ReviewError):
                self.review.partition(adult, selection, 0)
        with patch('tools.review_dataset.atomic_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.review.partition(adult, [images[0]], 0)
        self.assertEqual(len(self.review.groups), 3)
        self.assertEqual(self.review.state['revision'], 0)

    def test_http_security_and_state(self):
        server = Server(('127.0.0.1', 0), self.review)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
        self.addCleanup(connection.close)

        def request(method, path, body=None, headers=None):
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read()

        code, payload = request('GET', '/api/state')
        self.assertEqual(code, 200)
        self.assertNotIn(b'SECRET', payload)
        self.assertEqual(request('GET', '/image/SECRET')[0], 404)
        self.assertEqual(request('GET', '/image/../../manifest.json')[0], 404)
        self.assertEqual(request('GET', '/', headers={'Host': 'evil.test'})[0], 403)
        body = json.dumps({'group': self.gid('adult'), 'status': 'keep', 'revision': 0})
        self.assertEqual(request('POST', '/api/decision', body)[0], 403)
        headers = {'X-Review-Token': server.token, 'Origin': 'http://evil.test'}
        self.assertEqual(request('POST', '/api/decision', body, headers)[0], 403)
        headers['Origin'] = f'http://127.0.0.1:{server.server_port}'
        self.assertEqual(request('POST', '/api/decision', body, headers)[0], 200)
        self.assertEqual(request('POST', '/api/decision', body, headers)[0], 409)
        self.assertEqual(request('POST', '/api/decision', '[]', headers)[0], 400)
        image_id = next(iter(self.review.images))
        self.assertEqual(request('GET', '/image/' + image_id)[0], 200)
        self.assertEqual(request('GET', '/')[0], 200)


if __name__ == '__main__':
    unittest.main()

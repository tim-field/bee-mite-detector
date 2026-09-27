"""Hardware/package-independent tests for validation review counting."""
import unittest

from tools.evaluate_bee_baseline import derive_group, iou, match_boxes, summarize


def box(c=1, coords=(0, 0, 10, 10), confidence=None):
    result = {'class': c, 'xyxy': list(coords)}
    if confidence is not None:
        result['confidence'] = confidence
    return result


class EvaluationTests(unittest.TestCase):
    def test_iou(self):
        self.assertEqual(iou((0, 0, 10, 10), (0, 0, 10, 10)), 1)
        self.assertEqual(iou((0, 0, 10, 10), (10, 10, 20, 20)), 0)
        self.assertEqual(iou((0, 0, 0, 0), (0, 0, 0, 0)), 0)
        self.assertAlmostEqual(iou((0, 0, 10, 10), (0, 0, 5, 10)), 0.5)

    def test_unique_matching_confidence_order(self):
        predictions = [box(confidence=0.3), box(confidence=0.9)]
        self.assertEqual(match_boxes([box()], predictions, 0.25), ([(0, 1)], [], [0]))

    def test_wrong_class_and_low_confidence(self):
        predictions = [box(c=0, confidence=0.9), box(confidence=0.1)]
        self.assertEqual(match_boxes([box()], predictions, 0.25), ([], [0], [0]))

    def test_threshold_and_iou_inclusive(self):
        predictions = [box(coords=(0, 0, 5, 10), confidence=0.25)]
        self.assertEqual(match_boxes([box()], predictions, 0.25), ([(0, 0)], [], []))

    def test_empty(self):
        self.assertEqual(match_boxes([], [], 0.25), ([], [], []))
        self.assertEqual(match_boxes([], [box(confidence=0.9)], 0.25), ([], [], [0]))

    def test_derive_group(self):
        self.assertEqual(derive_group('12_jpeg.rf.905d5a47bf2cd1e06fb9117c9caa90bb.jpg'), '12_jpeg')
        self.assertEqual(derive_group('11_rotated_108_degrees_jpg.rf.abc123.jpg'), '11_jpg')
        self.assertEqual(derive_group('plain_name.jpg'), 'plain_name')

    def test_summary_size_and_class_counts(self):
        records = [{'truth': [box(), box(coords=(20, 20, 36, 40)), box(c=0)],
                    'predictions': [box(confidence=0.9), box(c=0, confidence=0.8),
                                    box(coords=(50, 50, 60, 60), confidence=0.3)]}]
        result = summarize(records, 0.25)
        self.assertEqual(result['classes']['varroa'],
                         dict(tp=1, fp=1, fn=1, precision=0.5, recall=0.5))
        self.assertEqual(result['classes']['bee']['recall'], 1)
        self.assertEqual(result['varroa_short_side']['<16px']['recall'], 1)
        self.assertEqual(result['varroa_short_side']['16-32px']['recall'], 0)
        self.assertIsNone(result['varroa_short_side']['>=64px']['recall'])


if __name__ == '__main__':
    unittest.main()

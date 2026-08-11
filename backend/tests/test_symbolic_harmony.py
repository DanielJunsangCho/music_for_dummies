"""
Harmony validation against public symbolic corpora.

These tests feed *known pitches* into the harmony engine and compare against
expert Roman analyses (When-in-Rome) or annotated TheoryTab chord symbols
(Hooktheory). They do not exercise scan CV or PDF glyph reading.
"""

import unittest

from tests.symbolic_eval import FIXTURES, evaluate_theorytab, evaluate_when_in_rome


# Floors are calibrated to current engine quality. Key accuracy is only gated
# on pieces that stay in one key; modulating Lieder often disagree on tonic
# spelling even when roots are right.
WHEN_IN_ROME_CASES = [
    # slug, min_root_recall, min_root_precision, min_key_accuracy|None, expected_key|None
    ('das_wandern', 0.55, 0.90, 0.70, 'Bb major'),
    ('die_sterne', 0.50, 0.65, 0.75, 'Eb major'),
    ('wohin', 0.65, 0.85, None, None),
    ('schwanenlied', 0.55, 0.85, 0.80, 'G minor'),
    ('le_colibri', 0.55, 0.70, None, None),
    ('berceuse', 0.50, 0.65, None, None),
]

HOOKTHEORY_CASES = [
    'unsteady_intro.xml',
    'orlando_intro.xml',
    'revenge_intro.xml',
    'freedom_dive_intro.xml',
]


class WhenInRomeTests(unittest.TestCase):
    def test_corpus_root_and_key_floors(self):
        for slug, recall, precision, key_acc, expected_key in WHEN_IN_ROME_CASES:
            with self.subTest(piece=slug):
                piece = FIXTURES / 'when_in_rome' / slug
                if not (piece / 'score.mxl').is_file():
                    self.skipTest(f'fixture missing: {slug}')
                result = evaluate_when_in_rome(piece)
                if expected_key:
                    self.assertEqual(result.predicted_key, expected_key)
                self.assertGreaterEqual(result.root_recall, recall, result.name)
                self.assertGreaterEqual(result.root_precision, precision, result.name)
                if key_acc is not None:
                    self.assertGreaterEqual(result.key_accuracy, key_acc, result.name)


class HooktheoryTests(unittest.TestCase):
    def test_theorytab_root_recovery(self):
        for filename in HOOKTHEORY_CASES:
            with self.subTest(fixture=filename):
                path = FIXTURES / 'hooktheory' / filename
                if not path.is_file():
                    self.skipTest(f'fixture missing: {filename}')
                result = evaluate_theorytab(path)
                self.assertGreaterEqual(result.root_recall, 0.85, result.name)
                self.assertGreaterEqual(result.root_precision, 0.85, result.name)


if __name__ == '__main__':
    unittest.main()

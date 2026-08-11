import unittest

from app.services.harmony import (
    Key,
    harmonic_function,
    meter_divisions,
    secondary_dominant_target,
)


class MeterTests(unittest.TestCase):
    def test_simple_triple_meter_only_splits_on_beats(self):
        self.assertEqual(meter_divisions((3, 4)), ((1, 3), 3.0))

    def test_compound_meter_uses_dotted_beats(self):
        self.assertEqual(meter_divisions((6, 8)), ((1, 2), 2.0))

    def test_common_time_allows_half_and_quarter_bar_changes(self):
        self.assertEqual(meter_divisions((4, 4)), ((1, 2, 4), 4.0))


class FunctionTests(unittest.TestCase):
    def setUp(self):
        self.key = Key(tonic=4, mode='major')

    def test_secondary_dominant_targets_a_relative_scale_degree(self):
        self.assertEqual(secondary_dominant_target(6, 'dominant seventh', self.key), 'V')
        self.assertEqual(secondary_dominant_target(3, 'dominant seventh', self.key), 'iii')

    def test_primary_dominant_is_not_secondary(self):
        self.assertIsNone(secondary_dominant_target(11, 'dominant seventh', self.key))

    def test_borrowed_quality_is_chromatic_even_on_tonic_root(self):
        self.assertEqual(harmonic_function(4, 'half-diminished', self.key), 'chromatic')

    def test_diatonic_minor_supertonic_is_subdominant(self):
        self.assertEqual(harmonic_function(6, 'minor sixth', self.key), 'subdominant')


class KeyCompatibilityTests(unittest.TestCase):
    def test_relative_major_and_minor_stay_compatible(self):
        from app.services.harmony import _keys_compatible

        self.assertTrue(_keys_compatible(Key(0, 'major'), Key(9, 'minor')))
        self.assertTrue(_keys_compatible(Key(2, 'minor'), Key(5, 'major')))
        self.assertFalse(_keys_compatible(Key(0, 'major'), Key(7, 'major')))


if __name__ == '__main__':
    unittest.main()

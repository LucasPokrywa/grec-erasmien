import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from natural_voice import french_approx

class NeuralApproximationTests(unittest.TestCase):
    def test_text_greek_is_not_used_in_neural_approx(self):
        self.assertEqual(french_approx('ˈan.θrɔː.pos'), 'annetroposse')
        self.assertEqual(french_approx('ˈgɛ.fy.ra'), 'guèfura')

    def test_diphthongs(self):
        self.assertEqual(french_approx('ˈoi̯.kos'), 'oïkosse')

    def test_unrecognized_phoneme_rejected(self):
        with self.assertRaises(ValueError):
            french_approx('a🤖')

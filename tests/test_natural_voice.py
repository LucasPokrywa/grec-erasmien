import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from natural_voice import french_approx

class NeuralApproximationTests(unittest.TestCase):
    def test_text_greek_is_not_used_in_neural_approx(self):
        self.assertEqual(french_approx('ˈan.θrɔː.pos'), 'anne tro posse')
        self.assertEqual(french_approx('ˈgɛ.fy.ra'), 'guè fu ra')

    def test_hard_gamma_in_sentence(self):
        # Μεγάλη : the /ga/ syllable must not be read as the letters « gé a ».
        self.assertEqual(french_approx('mɛ.ˈga.leː'), 'mèga lé')
        self.assertEqual(french_approx('ˈga.la'), 'gala')
        self.assertEqual(french_approx('mɛ.ˈga.leː mɛ.ˈga.leː'), 'mèga lé mèga lé')

    def test_word_boundaries(self):
        self.assertEqual(french_approx('ˈan.θrɔː.pos ˈan.θrɔː.pos'), 'anne tro posse anne tro posse')

    def test_diphthongs(self):
        self.assertEqual(french_approx('ˈoi̯.kos'), 'oï kosse')

    def test_unrecognized_phoneme_rejected(self):
        with self.assertRaises(ValueError):
            french_approx('a🤖')

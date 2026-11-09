import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phonology import analyze, analyze_word
from server import synthesize, concatenate_wav, ESPEAK


class PronunciationTests(unittest.TestCase):
    def word(self, w):
        return analyze_word(w)

    def test_basic_syllables(self):
        w = self.word('ἄνθρωπος')
        self.assertEqual([s['greek'] for s in w['syllables']], ['ἄν', 'θρω', 'πος'])
        self.assertEqual(w['ipa'], 'ˈan.θrɔː.pos')

    def test_bridges(self):
        w = self.word('γέφυρα')
        self.assertEqual([s['greek'] for s in w['syllables']], ['γέ', 'φυ', 'ρα'])
        self.assertEqual(w['ipa'], 'ˈgɛ.fy.ra')

    def test_geminate(self):
        self.assertEqual([s['greek'] for s in self.word('θάλαττα')['syllables']],
                         ['θά', 'λατ', 'τα'])

    def test_diphthong(self):
        self.assertEqual(self.word('οἶκος')['ipa'], 'ˈoi̯.kos')
        self.assertEqual(len(self.word('οἶκος')['syllables']), 2)

    def test_diaeresis(self):
        self.assertEqual(len(self.word('ἀϋπνία')['syllables']), 4)

    def test_long_vowel(self):
        self.assertIn('ɔː', self.word('δῶρον')['ipa'])

    def test_iota_subscript(self):
        self.assertEqual(self.word('τῇ')['ipa'], 'ˈteː')

    def test_gamma_nasal(self):
        self.assertEqual(self.word('ἄγγελος')['ipa'], 'ˈaŋ.gɛ.los')

    def test_rough_breathing(self):
        self.assertEqual(self.word('ὕδωρ')['ipa'], 'ˈhy.dɔːr')

    def test_punctuation_and_sentence(self):
        data = analyze('ὁ λόγος, ἀγαθός.')
        self.assertEqual(data['word_count'], 3)
        self.assertIn('ˈlo.gos', data['ipa'])

    def test_non_greek_rejected(self):
        with self.assertRaises(ValueError):
            analyze('hello')

    @unittest.skipUnless(ESPEAK, 'eSpeak non installé')
    def test_wav_generated(self):
        wav = synthesize(self.word('γέφυρα')['phonemes'])
        self.assertTrue(wav.startswith(b'RIFF'))
        wav2 = concatenate_wav([wav, wav])
        self.assertGreater(len(wav2), len(wav))


if __name__ == '__main__':
    unittest.main()

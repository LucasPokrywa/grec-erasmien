"""Transcription et syllabation du grec ancien : convention érasmienne scolaire.

Ce module est déterministe et ne dépend d'aucun moteur TTS. Les mnémoniques
phonétiques pour eSpeak sont distincts de la transcription IPA affichée.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata as ud


VOWELS = set('αεηιουω')
GREEK_LETTERS = set('αβγδεζηθικλμνξοπρσςτυφχψω')
COMBINING_ROUGH = '\u0314'
COMBINING_ACUTE = '\u0301'
COMBINING_GRAVE = '\u0300'
COMBINING_CIRCUMFLEX = '\u0342'
COMBINING_MACRON = '\u0304'
COMBINING_SUBSCRIPT = '\u0345'
COMBINING_DIAERESIS = '\u0308'
ACCENTS = {COMBINING_ACUTE, COMBINING_GRAVE, COMBINING_CIRCUMFLEX}

# Prononciation érasmienne usuelle en contexte pédagogique : θ et x fricatives,
# φ rendu par f. Accents rendus par une proéminence tonique, non par une
# reconstruction complète de l'accent musical du grec classique.
CONSONANTS = {
    'β': ('b', 'b'), 'γ': ('g', 'g'), 'δ': ('d', 'd'),
    'ζ': ('z', 'z'), 'θ': ('θ', 'T'), 'κ': ('k', 'k'),
    'λ': ('l', 'l'), 'μ': ('m', 'm'), 'ν': ('n', 'n'),
    'ξ': ('ks', 'ks'), 'π': ('p', 'p'), 'ρ': ('r', 'r'),
    'σ': ('s', 's'), 'τ': ('t', 't'), 'φ': ('f', 'f'),
    'χ': ('x', 'x'), 'ψ': ('ps', 'ps'),
}
VOWEL_SOUNDS = {
    'α': ('a', 'a'), 'ε': ('ɛ', 'E'), 'η': ('eː', 'e:'),
    'ι': ('i', 'i'), 'ο': ('o', 'o'), 'υ': ('y', 'y'),
    'ω': ('ɔː', 'O:'),
}
DIPHTHONGS = {
    'αι': ('ai̯', 'aI'), 'ει': ('ei̯', 'eI'), 'οι': ('oi̯', 'oI'),
    'υι': ('yi̯', 'y|i'), 'αυ': ('au̯', 'aU'), 'ευ': ('eu̯', 'eU'),
    'ου': ('uː', 'u:'), 'ηυ': ('eːu̯', 'e:U'),
}
# Groupes grecs possibles à l'initiale et groupes occlusive + μ/ν.
INITIAL_CLUSTERS = set(('βλ βρ γλ γν γρ δρ θλ θν θρ κλ κν κρ κτ κμ '
                        'μν πλ πν πρ πτ σβ σγ σδ σθ σκ σλ σμ σν σπ στ '
                        'σφ σχ σρ τλ τμ τν τρ φθ φλ φρ χθ χλ χρ γδ γμ').split())
MAX_CHARS = 240
MAX_WORDS = 35


@dataclass(frozen=True)
class Letter:
    text: str
    base: str
    marks: frozenset[str]

    @property
    def vowel(self) -> bool:
        return self.base in VOWELS


@dataclass(frozen=True)
class Sound:
    text: str
    letters: str
    ipa: str
    espeak: str
    nucleus: bool
    accent: bool


def _letter_groups(word: str) -> list[Letter]:
    letters: list[list[str]] = []
    for ch in ud.normalize('NFD', word):
        if ud.combining(ch):
            if not letters:
                raise ValueError('Signe diacritique sans lettre grecque.')
            letters[-1].append(ch)
        else:
            b = ch.lower()
            if b not in GREEK_LETTERS:
                raise ValueError(f'Caractère grec non pris en charge : {ch}')
            letters.append([ch])
    return [Letter(ud.normalize('NFC', ''.join(p)), p[0].lower().replace('ς', 'σ'),
                   frozenset(p[1:])) for p in letters]


def tokenize(text: str) -> list[str]:
    if not text.strip():
        raise ValueError('Saisis au moins un mot en grec ancien.')
    if len(text) > MAX_CHARS:
        raise ValueError(f'Le texte ne doit pas dépasser {MAX_CHARS} caractères.')
    result: list[str] = []
    current = ''
    for ch in text:
        normalized = ud.normalize('NFD', ch)
        base = normalized[0].lower()
        if base in GREEK_LETTERS:
            current += ch
        elif ud.combining(ch) and current:
            current += ch
        else:
            if current:
                result.append(current)
                current = ''
            if ch.isalpha() or (ud.combining(ch) and not ch.isspace()):
                raise ValueError('Le champ accepte uniquement des mots grecs et de la ponctuation.')
    if current:
        result.append(current)
    if not result:
        raise ValueError('Aucun mot grec reconnu.')
    if len(result) > MAX_WORDS:
        raise ValueError(f'Limite : {MAX_WORDS} mots par lecture.')
    return result


def _sounds(letters: list[Letter]) -> list[Sound]:
    out: list[Sound] = []
    i = 0
    while i < len(letters):
        c = letters[i]
        d = letters[i + 1] if i + 1 < len(letters) else None
        pair = c.base + d.base if d else ''
        # Le tréma distingue un hiatus d'une diphtongue (ἀϋπνία).
        if c.vowel and d and d.vowel and pair in DIPHTHONGS and COMBINING_DIAERESIS not in d.marks and COMBINING_SUBSCRIPT not in c.marks:
            ipa, esp = DIPHTHONGS[pair]
            rough = COMBINING_ROUGH in c.marks or COMBINING_ROUGH in d.marks
            accent = bool((c.marks | d.marks) & ACCENTS)
            out.append(Sound(c.text + d.text, pair,
                             ('h' if rough else '') + ipa,
                             ('h' if rough else '') + esp, True, accent))
            i += 2
            continue
        if c.vowel:
            ipa, esp = VOWEL_SOUNDS[c.base]
            # Les ᾳ/ῃ/ῳ sont traditionnellement lus sans iota prononcé.
            long = (COMBINING_MACRON in c.marks or COMBINING_CIRCUMFLEX in c.marks
                    or COMBINING_SUBSCRIPT in c.marks)
            if long and 'ː' not in ipa:
                ipa += 'ː'
                esp += ':'
            rough = COMBINING_ROUGH in c.marks
            out.append(Sound(c.text, c.base,
                             ('h' if rough else '') + ipa,
                             ('h' if rough else '') + esp,
                             True, bool(c.marks & ACCENTS)))
        else:
            ipa, esp = CONSONANTS[c.base]
            # Nasalisation de γ devant les vélaires, y compris γγ et γξ.
            if c.base == 'γ' and d and d.base in 'γκχξ':
                ipa, esp = 'ŋ', 'N'
            # Le rho initial à esprit rude est une vibrante sourde /r̥/.
            if c.base == 'ρ' and COMBINING_ROUGH in c.marks:
                ipa, esp = 'r̥', 'hr'
            out.append(Sound(c.text, c.base, ipa, esp, False, False))
        i += 1
    return out


def _is_valid_onset(cluster: list[Sound]) -> bool:
    if len(cluster) <= 1:
        return True
    spelling = ''.join(s.letters for s in cluster)
    return spelling in INITIAL_CLUSTERS


def _syllable_ranges(sounds: list[Sound]) -> list[tuple[int, int]]:
    nuclei = [i for i, s in enumerate(sounds) if s.nucleus]
    if not nuclei:
        return []
    cuts = [0]
    for left, right in zip(nuclei, nuclei[1:]):
        between = sounds[left + 1:right]
        if not between:
            cut = right
        elif len(between) == 1:
            cut = left + 1
        else:
            # La plus longue attaque admise rejoint la syllabe suivante.
            cut = right - 1
            for size in range(len(between), 1, -1):
                if _is_valid_onset(between[-size:]):
                    cut = right - size
                    break
        cuts.append(cut)
    cuts.append(len(sounds))
    return list(zip(cuts, cuts[1:]))


def analyze_word(word: str) -> dict:
    sounds = _sounds(_letter_groups(word))
    ranges = _syllable_ranges(sounds)
    syllables: list[dict] = []
    for start, end in ranges:
        part = sounds[start:end]
        accent = any(s.accent for s in part)
        ipa = ''.join(s.ipa for s in part)
        esp = ''.join(s.espeak for s in part)
        # L'accent est noté avant la syllabe et placé avant la voyelle pour eSpeak.
        if accent:
            n = next((j for j, s in enumerate(part) if s.nucleus), 0)
            esp = ''.join(s.espeak for s in part[:n]) + "'" + ''.join(s.espeak for s in part[n:])
        syllables.append({
            'greek': ''.join(s.text for s in part),
            'ipa': ('ˈ' if accent else '') + ipa,
            'phonemes': esp,
            'accented': accent,
        })
    return {
        'greek': word,
        'ipa': '.'.join(s['ipa'] for s in syllables),
        'phonemes': ''.join(s['phonemes'] for s in syllables),
        'syllables': syllables,
    }


def analyze(text: str) -> dict:
    words = [analyze_word(w) for w in tokenize(text)]
    syllables = [syllable for w in words for syllable in w['syllables']]
    return {
        'words': words,
        'syllables': syllables,
        'ipa': ' '.join(w['ipa'] for w in words),
        'syllable_count': len(syllables),
        'word_count': len(words),
        'warning': ('Les longueurs de α, ι et υ non marquées ne peuvent pas toujours être '
                    'déduites de l’orthographe. L’accent est rendu comme un accent tonique.'),
    }

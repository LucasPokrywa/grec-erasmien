"""Synthèse neuronale optionnelle pour Φωνή.

Deux moteurs peuvent fournir une voix naturelle :
- Azure Speech : balisage IPA explicite (clé privée en variable d'environnement).
- edge-tts : rendu neural de graphies françaises approximatives. Ce moteur ne
  sait PAS respecter l'API du grec ancien, contrairement à la transcription
  affichée. C'est un compromis de naturel, pas une restitution savante.
"""
from __future__ import annotations

import asyncio
import os
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from xml.sax.saxutils import escape, quoteattr

try:
    import edge_tts
except ImportError:
    edge_tts = None

# Pas de nom libre fourni par le client pour écarter toute injection de commande
# et éviter d'utiliser des voix non choisies par le projet.
EDGE_VOICES = {
    'femme': 'fr-FR-DeniseNeural',
    'homme': 'fr-FR-HenriNeural',
}
AZURE_REGION = os.getenv('AZURE_SPEECH_REGION', '').lower().strip()
AZURE_KEY = os.getenv('AZURE_SPEECH_KEY', '').strip()
AZURE_VOICE = os.getenv('AZURE_SPEECH_VOICE', 'fr-FR-DeniseNeural').strip()
AZURE_READY = bool(AZURE_REGION and AZURE_KEY and re.fullmatch(r'[a-z0-9-]{2,32}', AZURE_REGION) and re.fullmatch(r'[A-Za-z]{2,5}-[A-Za-z]{2,5}-[A-Za-z0-9]+Neural', AZURE_VOICE))

# Ordre important : séquences longues d'abord. Les approximations ci-dessous
# visent les voix françaises. θ, χ, η/ω longs et l'accent ne sont PAS reproduits
# fidèlement en mode neural sans phonèmes explicites.
FRENCH_SOUNDS = [
    ('eːu̯', 'éou'), ('ai̯', 'aï'), ('ei̯', 'éï'), ('oi̯', 'oï'),
    ('yi̯', 'uï'), ('au̯', 'aou'), ('eu̯', 'éou'),
    ('ɔː', 'o'), ('eː', 'é'), ('uː', 'ou'),
    ('r̥', 'r'), ('ŋ', 'ng'), ('θ', 't'), ('x', 'r'),
    ('ɛ', 'è'), ('y', 'u'),
    ('a', 'a'), ('b', 'b'), ('g', 'g'), ('d', 'd'), ('z', 'z'),
    ('k', 'k'), ('l', 'l'), ('m', 'm'), ('n', 'n'), ('p', 'p'),
    ('r', 'r'), ('s', 's'), ('t', 't'), ('f', 'f'), ('h', ''),
    ('i', 'i'), ('o', 'o'), ('u', 'ou'), ('e', 'é'),
]


def french_approx(ipa: str) -> str:
    """Graphie ciblée fr-FR. Pas une translittération exacte ni une API."""
    src = ipa.replace('ˈ', '').replace('ˌ', '')
    out = []
    i = 0
    while i < len(src):
        if src[i] == '.':
            out.append('-')
            i += 1
            continue
        for sound, orth in FRENCH_SOUNDS:
            if src.startswith(sound, i):
                # En français, g devant e/i devient /ʒ/ ; gu restaure /g/.
                if sound == 'g' and src[i+1:i+2] in {'e', 'i', 'ɛ', 'y'}:
                    orth = 'gu'
                out.append(orth)
                i += len(sound)
                break
        else:
            # Un phonème inconnu ne doit pas être envoyé tel quel à la voix.
            raise ValueError('Son non compatible avec la voix neuronale approximative.')
    result = ''.join(out)
    # Le -s final muet est rendu prononçable par -sse (ex. pos > posse).
    result = re.sub(r's(?=$|-|\s)', 'sse', result)
    # Éviter les voyelles nasales françaises non souhaitées avant -n final.
    result = re.sub(r'([aioèéu])n(?=$|-|\s)', r'\1nne', result)
    return result.replace('-', '')


async def _edge_bytes(text: str, voice: str, rate: str) -> bytes:
    tts = edge_tts.Communicate(text, voice, rate=rate)
    chunks = []
    async for item in tts.stream():
        if item['type'] == 'audio':
            chunks.append(item['data'])
    result = b''.join(chunks)
    if not result:
        raise RuntimeError('La voix neuronale n’a retourné aucun son.')
    return result


def synthesize_edge(ipa: str, speed: int, voice: str = 'femme') -> tuple[bytes, str]:
    if edge_tts is None:
        raise RuntimeError('Voix neuronale absente : installe les dépendances avec pip install -r requirements.txt.')
    if voice not in EDGE_VOICES:
        raise ValueError('Voix non reconnue.')
    text = french_approx(ipa)
    rate = f'{max(-50, min(50, round((speed - 140) / 140 * 100))):+d}%'
    try:
        data = asyncio.run(asyncio.wait_for(_edge_bytes(text, EDGE_VOICES[voice], rate), timeout=20))
    except (TimeoutError, OSError, RuntimeError) as exc:
        raise RuntimeError('La voix neuronale en ligne est indisponible. Essaie la voix phonétique.') from exc
    return data, 'audio/mpeg'


def synthesize_azure(ipa: str, greek: str, speed: int) -> tuple[bytes, str]:
    if not AZURE_READY:
        raise RuntimeError('Azure Speech n’est pas configuré sur le serveur.')
    # ph doit être issu UNIQUEMENT de la transcription serveur, jamais d'une
    # chaîne IPA fournie par le client. L'attribut XML est échappé explicitement.
    rate = max(65, min(145, round(speed / 140 * 100)))
    ssml = ("<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='fr-FR'>"
            f'<voice name={quoteattr(AZURE_VOICE)}><prosody rate="{rate}%">'
            f'<phoneme alphabet="ipa" ph={quoteattr(ipa)}>{escape(greek)}</phoneme>'
            '</prosody></voice></speak>')
    endpoint = f'https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1'
    request = Request(endpoint, data=ssml.encode('utf-8'), method='POST', headers={
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Content-Type': 'application/ssml+xml',
        'X-Microsoft-OutputFormat': 'riff-24khz-16bit-mono-pcm',
        'User-Agent': 'PhoneAncientGreek/2.0',
    })
    try:
        with urlopen(request, timeout=18) as response:
            data = response.read(4_000_000)
        if not data.startswith(b'RIFF'):
            raise RuntimeError('Azure Speech n’a pas renvoyé un fichier WAV.')
        return data, 'audio/wav'
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError('Azure a refusé cette lecture : la prise en charge des phonèmes dépend de la voix. Essaie eSpeak ou la voix neuronale approximative.') from exc

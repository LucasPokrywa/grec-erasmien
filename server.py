#!/usr/bin/env python3
"""Serveur local sans dépendance pip pour l'application Φωνή."""

from __future__ import annotations

import argparse
import os
import time
from collections import defaultdict, deque
from threading import Lock
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import wave
import webbrowser
import threading

from phonology import analyze
from natural_voice import AZURE_READY, edge_tts, synthesize_edge, synthesize_azure

ROOT = Path(__file__).resolve().parent
ESPEAK = shutil.which('espeak-ng') or shutil.which('espeak')
MIMES = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8'}
RATE_LOCK = Lock()
RATE_EVENTS = defaultdict(deque)

def allowed_audio_request(ip: str) -> bool:
    now = time.monotonic()
    with RATE_LOCK:
        events = RATE_EVENTS[ip]
        while events and now - events[0] > 60:
            events.popleft()
        if len(events) >= 40:
            return False
        events.append(now)
        return True


def synthesize(phonemes: str, speed: int = 140) -> bytes:
    if not ESPEAK:
        raise RuntimeError('eSpeak NG est absent. Installe-le (sur Arch : sudo pacman -S espeak-ng).')
    # Données externes toujours filtrées par le transcripteur grec (aucun shell).
    proc = subprocess.run(
        [ESPEAK, '-v', 'el', '-s', str(speed), '-p', '50', '--stdout', f'[[{phonemes}]]'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False,
    )
    if proc.returncode != 0 or not proc.stdout.startswith(b'RIFF'):
        raise RuntimeError('Impossible de générer le son avec eSpeak.')
    return proc.stdout


def concatenate_wav(clips: list[bytes], gap_ms: int = 240) -> bytes:
    if not clips:
        raise ValueError('Aucune syllabe à prononcer.')
    out = io.BytesIO()
    with wave.open(out, 'wb') as writer:
        sample_params = None
        for i, data in enumerate(clips):
            with wave.open(io.BytesIO(data), 'rb') as reader:
                params = (reader.getnchannels(), reader.getsampwidth(), reader.getframerate())
                if sample_params is None:
                    sample_params = params
                    writer.setnchannels(params[0])
                    writer.setsampwidth(params[1])
                    writer.setframerate(params[2])
                elif params != sample_params:
                    raise RuntimeError('Formats audio différents.')
                writer.writeframes(reader.readframes(reader.getnframes()))
            if i != len(clips) - 1:
                writer.writeframes(b'\x00' * (sample_params[2] * gap_ms // 1000 * sample_params[0] * sample_params[1]))
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print('[Φωνή]', fmt % args)

    def reply(self, code: int, data: bytes, content_type: str):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def reply_json(self, code: int, payload: dict):
        self.reply(code, json.dumps(payload, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

    def do_GET(self):
        if self.path == '/api/health':
            return self.reply_json(200, {'ready': bool(ESPEAK) or edge_tts is not None or AZURE_READY, 'engine': Path(ESPEAK).name if ESPEAK else None, 'edge': edge_tts is not None, 'azure': AZURE_READY})
        name = 'index.html' if self.path == '/' else self.path.lstrip('/')
        if name not in {'index.html', 'styles.css', 'app.js'}:
            return self.reply_json(404, {'error': 'Page introuvable.'})
        path = ROOT / name
        self.reply(200, path.read_bytes(), MIMES[path.suffix])

    def do_POST(self):
        if self.path not in {'/api/analyze', '/api/audio'}:
            return self.reply_json(404, {'error': 'Route introuvable.'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 8192:
                return self.reply_json(413, {'error': 'Données trop volumineuses.'})
            params = json.loads(self.rfile.read(length))
            if not isinstance(params, dict) or not isinstance(params.get('text'), str):
                raise ValueError('Texte grec manquant.')
            analysis = analyze(params['text'])
            if self.path == '/api/analyze':
                return self.reply_json(200, analysis)
            if not allowed_audio_request(self.client_address[0]):
                return self.reply_json(429, {'error': 'Trop de lectures audio : réessaie dans une minute.'})
            speed = int(params.get('speed', 140))
            if not 80 <= speed <= 220:
                raise ValueError('Vitesse invalide (80–220).')
            mode = params.get('mode', 'normal')
            if mode not in {'normal', 'syllable', 'segmented'}:
                raise ValueError('Mode de lecture invalide.')
            index = params.get('index')
            if mode == 'syllable' and (not isinstance(index, int) or not 0 <= index < len(analysis['syllables'])):
                raise ValueError('Numéro de syllabe invalide.')

            engine = params.get('engine', 'phonetic')
            voice = params.get('voice', 'femme')
            if engine in {'edge', 'azure'}:
                if mode == 'segmented':
                    return self.reply_json(400, {'error': 'Le mode syllabique enchaîné est assuré par le navigateur.'})
                if mode == 'normal':
                    ipa = ' '.join(w['ipa'] for w in analysis['words'])
                    greek = ' '.join(w['greek'] for w in analysis['words'])
                else:
                    ipa = analysis['syllables'][index]['ipa']
                    greek = analysis['syllables'][index]['greek']
                if engine == 'edge':
                    audio, mime = synthesize_edge(ipa, speed, voice)
                else:
                    audio, mime = synthesize_azure(ipa, greek, speed)
            elif engine == 'phonetic':
                if mode == 'normal':
                    phonemes = ' '.join(w['phonemes'] for w in analysis['words'])
                    audio = synthesize(phonemes, speed)
                elif mode == 'syllable':
                    audio = synthesize(analysis['syllables'][index]['phonemes'], speed)
                else:
                    clips = [synthesize(s['phonemes'], speed) for s in analysis['syllables']]
                    audio = concatenate_wav(clips)
                mime = 'audio/wav'
            else:
                raise ValueError('Moteur vocal inconnu.')
            self.reply(200, audio, mime)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.reply_json(400, {'error': str(exc)})
        except subprocess.TimeoutExpired:
            self.reply_json(503, {'error': 'La synthèse audio a expiré.'})
        except (OSError, RuntimeError) as exc:
            self.reply_json(503, {'error': str(exc)})


def main():
    parser = argparse.ArgumentParser(description='Application web locale de prononciation érasmienne.')
    parser.add_argument('--port', type=int, default=int(os.getenv('PORT', '8765')))
    parser.add_argument('--host', default='127.0.0.1', help='0.0.0.0 pour Docker / hébergement')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    address = f'http://127.0.0.1:{args.port}'
    print(f'\nΦωνή — application disponible sur {address}')
    print('eSpeak :', ESPEAK or 'non installé')
    print('Neurale Edge :', 'disponible (en ligne, approximation)' if edge_tts else 'non installée')
    print('Neurale Azure/IPA :', 'configurée' if AZURE_READY else 'clé non configurée')
    print('Ctrl+C pour arrêter le serveur.\n')
    if not args.no_browser:
        threading.Timer(0.75, lambda: webbrowser.open(address)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nArrêt du serveur.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

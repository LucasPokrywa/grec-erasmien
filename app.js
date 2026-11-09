'use strict';

const $ = (id) => document.getElementById(id);
const elements = {
  input: $('greekInput'), count: $('charCount'), error: $('errorBox'),
  greek: $('resultGreek'), ipa: $('resultIpa'), countSyllables: $('syllableCount'),
  container: $('syllableContainer'), state: $('playState'), stop: $('stopBtn'),
  speed: $('speedRange'), speedValue: $('speedValue'),
  dot: $('engineDot'), engine: $('engineStatus'), normal: $('normalBtn'), slow: $('slowBtn'),
  engineChoice: $('voiceEngine'), voiceChoice: $('voiceGender'), voiceInfo: $('voiceInfo'), voiceRow: $('edgeVoiceRow')
};
let analysis = null;
let analyzedText = null;
let playing = false;
let aborter = null;
let activeAudio = null;
let currentAudioUrl = null;
let playSerial = 0;
let syllableButtons = [];

function setError(text = '') {
  elements.error.textContent = text;
  elements.error.hidden = !text;
}
function setPlayStatus(message, running = false) {
  elements.state.textContent = message;
  playing = running;
  elements.stop.disabled = !running;
  elements.normal.disabled = running;
  elements.slow.disabled = running;
}
function resetHighlights() {
  syllableButtons.forEach(b => {
    b.classList.remove('active');
    b.removeAttribute('aria-current');
  });
}
function stopPlayback() {
  playSerial += 1;
  aborter?.abort();
  if (activeAudio) { activeAudio.pause(); activeAudio.dispatchEvent(new Event('ended')); activeAudio.currentTime = 0; activeAudio = null; }
  if (currentAudioUrl) { URL.revokeObjectURL(currentAudioUrl); currentAudioUrl = null; }
  resetHighlights();
  setPlayStatus('Prêt à écouter', false);
}
async function requestJson(url, payload) {
  const res = await fetch(url, {method:'POST', headers: {'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Erreur inconnue.');
  return data;
}
async function requestAudio(payload, signal) {
  const response = await fetch('/api/audio', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({...payload,engine:elements.engineChoice.value,voice:elements.voiceChoice.value}), signal
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || 'Échec de la synthèse audio.');
  }
  return response.blob();
}
function newElement(tag, cls, value) {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (value !== undefined) el.textContent = value;
  return el;
}
function renderResult(data) {
  elements.greek.textContent = data.words.map(w => w.greek).join(' ');
  elements.ipa.textContent = `/${data.ipa}/`;
  elements.countSyllables.textContent = `${data.syllable_count} syllabe${data.syllable_count > 1 ? 's' : ''}`;
  elements.container.replaceChildren();
  syllableButtons = [];
  let idx = 0;
  data.words.forEach((word) => {
    const group = newElement('div', 'word-group');
    const heading = newElement('div', 'word-head', word.greek);
    group.append(heading);
    const parts = newElement('div', 'syllables-list');
    word.syllables.forEach((syl, i) => {
      if (i) parts.append(newElement('span', 'hyphen', '·'));
      const b = newElement('button', `syllable${syl.accented ? ' is-accented' : ''}`);
      b.type = 'button';
      b.title = `Écouter « ${syl.greek} »`;
      b.setAttribute('aria-label', `Écouter la syllabe ${syl.greek}, ${syl.ipa}`);
      b.append(newElement('span', 'syllable-greek', syl.greek));
      b.append(newElement('span', 'syllable-ipa', `/${syl.ipa}/`));
      const index = idx;
      b.addEventListener('click', () => play('syllable', index));
      syllableButtons.push(b);
      parts.append(b);
      idx += 1;
    });
    group.append(parts);
    elements.container.append(group);
  });
}
async function analyzeCurrent() {
  stopPlayback();
  setError();
  const text = elements.input.value.trim();
  if (!text) {setError('Écris d’abord un mot grec.'); return false;}
  try {
    analysis = await requestJson('/api/analyze', {text});
    analyzedText = text;
    renderResult(analysis);
    return true;
  } catch (err) {
    setError(err.message);
    return false;
  }
}
async function ensureAnalysis() {
  if (!analysis || elements.input.value.trim() !== analyzedText) return analyzeCurrent();
  return true;
}
async function playBlob(blob, serial) {
  if (serial !== playSerial) return;
  const url = URL.createObjectURL(blob);
  currentAudioUrl = url;
  const audio = new Audio(url);
  activeAudio = audio;
  try {
    await new Promise((resolve, reject) => {
      audio.onended = resolve;
      audio.onerror = () => reject(new Error('Le navigateur ne peut pas lire le son.'));
      audio.play().catch(reject);
    });
  } finally {
    if (activeAudio === audio) activeAudio = null;
    URL.revokeObjectURL(url);
    if (currentAudioUrl === url) currentAudioUrl = null;
  }
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function play(mode, singleIndex = null) {
  stopPlayback();
  if (!(await ensureAnalysis())) return;
  setError();
  setPlayStatus(mode === 'normal' ? 'Lecture continue…' : 'Lecture syllabique…', true);
  const serial = ++playSerial;
  const speed = Number(elements.speed.value);
  aborter = new AbortController();
  try {
    if (mode === 'normal') {
      const blob = await requestAudio({text: analyzedText, mode: 'normal', speed}, aborter.signal);
      if (serial === playSerial) await playBlob(blob, serial);
    } else {
      const indices = singleIndex === null ? analysis.syllables.map((_, i) => i) : [singleIndex];
      for (const index of indices) {
        if (serial !== playSerial) break;
        resetHighlights();
        const b = syllableButtons[index];
        if (b) {b.classList.add('active'); b.setAttribute('aria-current', 'true');}
        elements.state.textContent = `Syllabe ${index + 1} / ${analysis.syllable_count}`;
        const blob = await requestAudio({text: analyzedText, mode:'syllable', index, speed}, aborter.signal);
        if (serial !== playSerial) break;
        await playBlob(blob, serial);
        if (indices.length > 1 && index !== indices.at(-1) && serial === playSerial) await pause(190);
      }
    }
  } catch (err) {
    if (err.name !== 'AbortError' && serial === playSerial) setError(err.message);
  } finally {
    if (serial === playSerial) stopPlayback();
  }
}

$('analyzeBtn').addEventListener('click', analyzeCurrent);
elements.normal.addEventListener('click', () => play('normal'));
elements.slow.addEventListener('click', () => play('slow'));
elements.stop.addEventListener('click', stopPlayback);
$('clearBtn').addEventListener('click', () => {
  stopPlayback();
  elements.input.value = '';
  analysis = null; analyzedText = null; syllableButtons = [];
  elements.greek.textContent = '—'; elements.ipa.textContent = '—';
  elements.countSyllables.textContent = '— syllabes';
  elements.container.replaceChildren(newElement('div', 'syllable-placeholder', 'Votre analyse s’affichera ici.'));
  elements.input.dispatchEvent(new Event('input'));
  elements.input.focus();
});
elements.input.addEventListener('input', () => {
  elements.count.textContent = `${elements.input.value.length} / 240 caractères`;
  if (!elements.error.hidden) setError();
});
elements.input.addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') analyzeCurrent();
});
document.querySelectorAll('.example').forEach(btn => {
  btn.addEventListener('click', () => {
    elements.input.value = btn.dataset.text;
    elements.input.dispatchEvent(new Event('input'));
    analyzeCurrent();
  });
});
elements.speed.addEventListener('input', () => {elements.speedValue.textContent = `${elements.speed.value} mots/min`;});
$('copyBtn').addEventListener('click', async () => {
  if (!(await ensureAnalysis())) return;
  try {
    await navigator.clipboard.writeText(`/${analysis.ipa}/`);
    $('copyBtn').querySelector('span').textContent = 'Copié !';
    setTimeout(() => { $('copyBtn').querySelector('span').textContent = 'Copier'; }, 1400);
  } catch { setError('Copie impossible : vérifie les autorisations du navigateur.'); }
});
$('downloadBtn').addEventListener('click', async () => {
  if (!(await ensureAnalysis())) return;
  setError();
  const btn = $('downloadBtn');
  btn.disabled = true;
  btn.textContent = 'Préparation de l’audio…';
  try {
    const blob = await requestAudio({text:analyzedText, mode:'normal', speed:Number(elements.speed.value)});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `prononciation-erasmienne.${blob.type.includes('mpeg') ? 'mp3' : 'wav'}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 15000);
  } catch (err) {setError(err.message);}
  finally {btn.disabled = false; btn.textContent = '↓ Télécharger l’audio';}
});

function refreshVoiceInfo() {
  const choice = elements.engineChoice.value;
  elements.voiceRow.hidden = choice !== 'edge';
  elements.voiceInfo.textContent = choice === 'azure'
    ? 'Azure utilise l’API pour guider une voix neuronale ; les phonèmes possibles dépendent de la voix configurée.'
    : choice === 'edge'
    ? 'Voix plus naturelle, en ligne : graphie phonétique française approximative, sans garantie de fidélité érasmienne.'
    : 'Lecture locale eSpeak : phonèmes explicitement pilotés, mais rendu mécanique.';
}
elements.engineChoice.addEventListener('change', () => { stopPlayback(); refreshVoiceInfo(); });
elements.voiceChoice.addEventListener('change', stopPlayback);

async function init() {
  try {
    const result = await fetch('/api/health');
    const data = await result.json();
    const choices = elements.engineChoice;
    choices.querySelector('[value="edge"]').disabled = !data.edge;
    choices.querySelector('[value="phonetic"]').disabled = !data.engine;
    const azure = choices.querySelector('[value="azure"]');
    azure.disabled = !data.azure;
    azure.hidden = !data.azure;
    choices.value = data.azure ? 'azure' : data.edge ? 'edge' : 'phonetic';
    refreshVoiceInfo();
    elements.dot.classList.add(data.ready ? 'ready' : 'missing');
    elements.engine.textContent = data.azure ? 'Voix neuronale API disponible'
      : data.edge ? 'Voix neuronale en ligne disponible'
      : data.engine ? 'Voix phonétique disponible' : 'Transcription seule';
  } catch {
    elements.dot.classList.add('missing');
    elements.engine.textContent = 'Serveur indisponible';
  }
  elements.input.value = 'ἄνθρωπος';
  elements.input.dispatchEvent(new Event('input'));
  await analyzeCurrent();
}
init();

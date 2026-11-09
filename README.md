# Φωνή — Grec ancien, prononciation érasmienne (v2)

Application web (Python + HTML/JavaScript) : saisie de grec polytonique,
transcription API, affichage des syllabes et lecture continue ou syllabe par
syllabe. Chaque syllabe est cliquable.

## Les trois modes de synthèse

| Mode | Qualité de la voix | Fidélité phonétique |
|---|---|---|
| **Neurale** (Edge, sélection par défaut si disponible) | Plus naturelle | **Approximation** en français de l'API, notamment θ, χ, h, les longues et l'accent. Ne convient PAS comme référence phonétique stricte. |
| **Phonétique** (eSpeak NG) | Mécanique | Pilote les phonèmes d'après la convention érasmienne implémentée. |
| **Neurale avec API** (Azure Speech, optionnelle) | Neurale | Transmet la transcription IPA via SSML `<phoneme>`. **La compatibilité varie selon la voix et les phonèmes**. À valider à l'oreille ; l'option n'est disponible que si la clé est configurée. |

Les voix neuronales utilisent une connexion réseau. L'option Edge utilise le
projet tiers `edge-tts`, interface **non officielle** avec le service de lecture
Microsoft Edge : ce service peut devenir indisponible ou imposer des limites
sans préavis. Les textes destinés à la synthèse en ligne sont envoyés au
fournisseur distant (graphie approximative pour Edge, grec et API pour Azure).
Le mode eSpeak fonctionne sans Internet.

## Installation locale Arch Linux

```bash
sudo pacman -S python espeak-ng
cd phone_erasmienne
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Le navigateur s'ouvre à `http://127.0.0.1:8765`.

**Sans connexion ni pip**, la transcription et la lecture phonétique restent
utilisables : `python server.py`, avec eSpeak NG préinstallé. Si `edge-tts`
n'est pas installé, l'option neuronale est désactivée automatiquement.

Sous Debian/Ubuntu : `sudo apt install python3 python3-venv espeak-ng`.

## Déployer sur Render (HTTPS public)

Le dépôt est prêt pour un service Render **Docker** : `Dockerfile` et
`render.yaml` sont inclus.

1. Placer les fichiers de ce dossier à la racine d'un dépôt GitHub.
2. Dans Render, créer un **Web Service** depuis ce dépôt (ou créer un Blueprint
   à partir de `render.yaml`). Choisir le plan gratuit si disponible.
3. Render lance le Dockerfile et fournit une adresse publique `onrender.com`.
4. Ajouter un domaine personnalisé si besoin. Le service écoute sur `0.0.0.0`
   et la variable d'environnement `PORT` (défaut Docker 10000).

Le plan gratuit peut se mettre en veille après une période d'inactivité.
L'option Edge a besoin de connexions sortantes HTTPS/WebSocket pour la voix
neuronale ; sa disponibilité depuis Render n'est pas garantie.

**Aucun hébergement public n'est créé automatiquement par cette archive.**

## Déployer sur un VPS Debian + Caddy

### Option A — Caddy tourne lui-même dans Docker (réseau partagé)

Dans le dossier projet sur le VPS :

```bash
docker build -t phone-grec-ancien .
docker run -d --name phone-grec-ancien --restart unless-stopped \
  --network projet-bibliotheque_proxy \
  phone-grec-ancien
```

`projet-bibliotheque_proxy` est un **exemple de réseau Docker existant** ;
vérifier avec `docker network ls` et utiliser le réseau sur lequel se trouve
votre conteneur Caddy. Les deux conteneurs doivent partager ce réseau.

Dans le `Caddyfile` du conteneur Caddy :

```caddyfile
grec.exemple.fr {
    encode zstd gzip
    reverse_proxy phone-grec-ancien:10000
}
```

Configurer le DNS du sous-domaine sur l'IP publique du VPS, puis recharger
Caddy avec les commandes adaptées à votre stack Docker.

### Option B — Caddy installé directement sur le VPS

```bash
docker build -t phone-grec-ancien .
docker run -d --name phone-grec-ancien --restart unless-stopped \
  -p 127.0.0.1:8765:10000 phone-grec-ancien
```

Dans le `Caddyfile` du système :

```caddyfile
grec.exemple.fr {
    reverse_proxy 127.0.0.1:8765
}
```

Dans les deux cas, HTTPS est géré par Caddy. Ne pas exposer directement le
serveur Python au public sur un port non chiffré.

## Voix Azure configurée côté serveur (optionnelle)

```bash
AZURE_SPEECH_REGION=francecentral \
AZURE_SPEECH_KEY=VOTRE_CLE_PRIVEE \
AZURE_SPEECH_VOICE=fr-FR-DeniseNeural \
python server.py
```

Pour Docker, utiliser les variables `-e AZURE_SPEECH_REGION=...`, etc., ou
les *secrets* de la plateforme d'hébergement. **Ne jamais placer la clé dans
le navigateur ni dans le code Git.** Azure est un service externe pouvant
occasionner des frais ; le serveur contient un plafonnement basique des
requêtes audio, mais ce n'est pas une protection budgétaire complète.

Le moteur utilise les phonèmes IPA définis dans `phonology.py` via SSML. Une
voix et une locale ne prennent pas forcément en charge tous les sons du grec
ancien, notamment /y/, /θ/, /x/ : tester les cas représentatifs.

## Exemples de règles pédagogiques

| Grec | API | Observations |
|---|---|---|
| β γ δ | b g d | Occlusives, pas fricatives grecques modernes |
| θ φ χ | θ f x | Tradition érasmienne scolaire retenue |
| η ω | eː ɔː | Voyelles longues |
| υ | y | « u » français |
| αι ει οι | ai̯ ei̯ oi̯ | Diphtongues |
| αυ ευ ου | au̯ eu̯ uː | Diphthongues et ou long |
| ῾ | h | Esprit rude |

Les accents sont restitués par un accent tonique, non une hauteur musicale.
Pour α/ι/υ, la longueur non marquée ne peut pas toujours être déduite de la
graphie. La syllabation de certains composés exige une analyse morphologique.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Références

- [Smyth, *Greek Grammar*, §§ 138–141](https://grammars.alpheios.net/smyth/xhtml/body.1_div1.1_div2.6.html)
- [Prononciation érasmienne (comparaison)](https://greekpronunciations.com/pronunciation/erasmian)
- [edge-tts (interface non officielle)](https://github.com/rany2/edge-tts)
- [Azure Speech, phonèmes SSML](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-synthesis-markup-pronunciation)
- [Render Web Services](https://render.com/docs/web-services)

# Voice Library Design — Bibliotheque locale + Navigateur HuggingFace

**Date** : 2026-02-22
**Statut** : Approuve

## Objectif

Remplacer le simple champ texte + file picker pour la voix de reference Chatterbox par une bibliotheque de voix complete avec :
1. Gestion locale des voix (import, preview, selection, suppression)
2. Telechargement depuis HuggingFace (dataset Kyutai TTS Voices)

## Specs audio Chatterbox

- Format : WAV 24kHz+ mono
- Duree optimale : 10-30 secondes (le modele ne traite que les ~10 premieres secondes)
- Qualite : enregistrement propre, pas de bruit de fond

## Structure fichiers

```
E:\TTS\voices\
+-- meta.json                    <- Index global (auto-genere au scan)
+-- fr_donation_0a67/
|   +-- voice.wav                <- Fichier audio (enhanced WAV)
|   +-- meta.json                <- {"name": "Donation 0A67", "lang": "fr", "gender": "unknown", "source": "kyutai", "duration_s": 8.2}
+-- custom_ma_voix/
    +-- voice.wav                <- Importe par l'utilisateur
    +-- meta.json                <- {"name": "Ma voix", "lang": "fr", "gender": "male", "source": "local"}
```

Chaque voix = un sous-dossier avec `voice.wav` + `meta.json`.

## UI — Onglet Persona (remplace le champ texte actuel)

### Bibliotheque locale

Integree dans la section "Clonage de voix" du PersonaTab :

- **Voix active** : carte surelevee (BG_ELEVATED + BORDER_FOCUS glow) montrant nom, tags, duree
- **Liste scrollable** : QScrollArea max-height 200px avec items custom
  - Chaque item : nom (bold), tags (langue/genre/duree/source), bouton play, bouton delete (hover only, voix custom)
  - Item actif : border-left 3px ACCENT (#4f8fff)
  - Hover : BG_RAISED -> BG_ELEVATED, transition 150ms
- **Bouton "Importer un WAV"** : ghost style (transparent, border)
- **Bouton "Telecharger depuis HF"** : ACCENT background, bold

### Dialog HuggingFace Browser

Modal avec :
- **Onglets categorie** : Donations (228) | Francais (32) | VCTK (110)
- **Liste voix** : checkbox + ID + duree + bouton preview + bouton telecharger
- **Batch download** : selection multiple + bouton GREEN "Telecharger la selection (N)"
- **Barre de progression** : ACCENT fill, BG_RAISED track, 6px height
- **Indicateur "Installe"** : GREEN badge pour les voix deja presentes

### Dialog d'import

Petit modal apres selection fichier :
- Champs : Nom, Langue (combo), Genre (radio)
- Affiche info fichier (duree, sample rate)
- Copie (pas deplace) le fichier dans voices/

## Backend — VoiceLibrary

```python
# jarvis/voices/library.py
class VoiceMeta:
    id: str          # Identifiant unique (nom du dossier)
    name: str        # Nom affiche
    lang: str        # "fr", "en", etc.
    gender: str      # "male", "female", "unknown"
    source: str      # "local", "kyutai"
    duration_s: float
    path: str        # Chemin absolu vers voice.wav

class VoiceLibrary:
    def __init__(self, voices_dir: str)
    def scan_local() -> list[VoiceMeta]          # Scan voices/*/meta.json
    def import_wav(path, name, lang, gender)      # Copie + cree meta.json
    def delete_voice(voice_id)                    # Supprime le dossier
    def get_voice_path(voice_id) -> str           # Retourne le path WAV

    # HuggingFace
    def list_hf_voices(category) -> list[HFVoice] # Liste via HF API
    def preview_hf_voice(hf_id) -> np.ndarray      # Download temp
    def download_hf_voice(hf_id, name) -> VoiceMeta
```

## Fichiers a creer/modifier

| Fichier | Action | Lignes estimees |
|---------|--------|-----------------|
| `jarvis/voices/__init__.py` | Nouveau — package | 5 |
| `jarvis/voices/library.py` | Nouveau — VoiceLibrary + VoiceMeta | ~200 |
| `jarvis/gui/widgets/voice_browser.py` | Nouveau — dialog HF browser | ~250 |
| `jarvis/gui/widgets/persona_tab.py` | Modifier — liste locale + boutons | ~150 modifies |
| `jarvis/config.py` | Mineur — ajouter voices_dir si besoin | ~5 |

## Dataset HuggingFace

**Kyutai TTS Voices** (`kyutai/tts-voices`, ~999 MB total) :
- `voice-donations/` : 228 voix, IDs hex (0a67, 1410...), WAV + enhanced WAV
- `cml-tts/fr/` : ~32 voix francaises, IDs numeriques
- `vctk/` : 110 speakers anglais avec accents varies

On telecharge uniquement les `*_enhanced.wav` (nettoyes par Demucs).

## Theme Obsidian

Tous les nouveaux widgets utilisent la palette existante :
- Fonds : BG_VOID < BG_BASE < BG_SURFACE < BG_RAISED < BG_ELEVATED
- Accent : ACCENT (#4f8fff), GREEN (#34d399) pour les actions positives
- Texte : TEXT (#e2e8f0), TEXT_SECONDARY (#7e8ca2)
- Borders : BORDER_DEFAULT (#1e2436), BORDER_FOCUS (#4f8fff)
- Border-radius : 8px partout (coherent avec GroupBox)

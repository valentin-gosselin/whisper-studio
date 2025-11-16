# Guide du Mode Document

Le mode **Document** de Whisper Studio transforme vos enregistrements audio/vidéo en documents Word professionnels structurés grâce à l'intelligence artificielle.

## Fonctionnalités

### Transcription + Analyse IA
- Transcription audio avec Whisper (large-v3)
- Analyse et structuration automatique avec Ollama (qwen2.5:7b ou llama3.1:8b)
- Enrichissement intelligent avec points clés, définitions et exemples
- Génération de résumé exécutif

### Types de contenu supportés
- **Cours magistral** : Notes structurées avec concepts clés et questions de révision
- **Réunion** : Compte-rendu formel avec décisions et actions
- **Conférence** : Synthèse avec arguments principaux et implications
- **Interview** : Format Q&A avec insights clés
- **Autre** : Structuration générique adaptative

### Formats de sortie
- **Document DOCX** : Document Word formaté professionnellement
  - Page de couverture avec métadonnées
  - Table des matières
  - Résumé exécutif
  - Sections enrichies avec points clés
  - Définitions et exemples en encadrés

- **Transcription TXT** : Backup de la transcription brute

## Utilisation

### 1. Sélectionner le mode Document
Cliquez sur l'onglet "Document" en haut de la page.

### 2. Choisir le type de contenu
Sélectionnez le type qui correspond le mieux à votre enregistrement :
- Cours magistral (par défaut)
- Réunion
- Conférence
- Interview
- Autre

### 3. Fournir l'audio

#### Option A : Enregistrement direct
1. Cliquez sur le bouton "Enregistrer"
2. Autorisez l'accès au microphone
3. Parlez (le timer s'affiche)
4. Cliquez sur "Arrêter" quand vous avez terminé
5. Le fichier est ajouté automatiquement

#### Option B : Upload de fichier
1. Glissez-déposez votre fichier ou cliquez sur "Parcourir"
2. Formats audio supportés : MP3, WAV, M4A, OGG, FLAC, AAC, WMA, OPUS
3. Formats vidéo supportés : MP4, MKV, AVI, MOV, WEBM

### 4. Sélectionner la langue
Choisissez la langue du contenu (auto-détection par défaut).

### 5. Lancer le traitement
Cliquez sur "Démarrer tout" et patientez.

## Pipeline de traitement

Le mode Document exécute un pipeline en 4 étapes :

```
1. Transcription Whisper (20-50%)
   Audio → Texte brut avec timestamps

2. Segmentation IA (55%)
   Ollama détecte les sections logiques

3. Enrichissement (60-80%)
   Chaque section est analysée et enrichie
   - Nettoyage du texte
   - Extraction de points clés
   - Identification de définitions
   - Repérage d'exemples

4. Finalisation (85-100%)
   - Génération du résumé exécutif
   - Création du document DOCX
   - Sauvegarde de la transcription TXT
```

## Temps de traitement estimés

| Durée audio | Temps total | Détails |
|-------------|-------------|---------|
| 15 min | 2-3 min | Rapide |
| 1h | 8-10 min | Moyen |
| 2h | 15-20 min | Long |
| 4h | 30-35 min | Très long |

*Les temps varient selon la charge GPU/CPU*

## Configuration Ollama

### Modèles utilisés
- **Primaire** : `qwen2.5:7b` (meilleur pour le français)
- **Fallback** : `llama3.1:8b` (si le primaire échoue)

### Vérifier les modèles disponibles
```bash
docker exec whisper-ollama ollama list
```

### Télécharger un modèle manquant
```bash
docker exec whisper-ollama ollama pull qwen2.5:7b
docker exec whisper-ollama ollama pull llama3.1:8b
```

## Résolution de problèmes

### Le mode Document n'apparaît pas
Vérifiez que le service Ollama est démarré :
```bash
docker ps | grep ollama
```

Si absent, démarrez-le :
```bash
docker compose -f /docker/whisper/docker-compose-webui.yml up -d ollama
```

### Erreur "Ollama service unavailable"
1. Vérifiez les logs du service :
```bash
docker logs whisper-ollama
```

2. Redémarrez le service :
```bash
docker restart whisper-ollama
```

3. Attendez 10-15s que le modèle charge en mémoire

### Le document généré est de mauvaise qualité
- **Problème** : Sections mal découpées
  - **Solution** : Essayez un autre type de contenu (ex: "Autre" au lieu de "Cours")

- **Problème** : Texte incomplet ou tronqué
  - **Solution** : Vérifiez que le modèle Ollama a assez de RAM (min 8GB recommandé)

- **Problème** : Résumé générique
  - **Solution** : L'audio doit être clair et structuré. Évitez les enregistrements avec beaucoup de bruit de fond.

### L'enregistrement vocal ne fonctionne pas
1. Vérifiez les permissions du navigateur (microphone)
2. Utilisez Chrome ou Firefox (Safari peut avoir des limitations)
3. Si en HTTPS, vérifiez le certificat SSL

### Le téléchargement du DOCX échoue
Vérifiez l'espace disque disponible :
```bash
df -h /docker/whisper/webui-outputs
```

## Astuces pour de meilleurs résultats

### Pour des cours magistraux
- Enregistrez dans un environnement calme
- Structurez votre discours avec des transitions claires ("Passons maintenant à...", "Chapitre suivant...")
- Parlez clairement et à un rythme modéré

### Pour des réunions
- Annoncez les points de l'ordre du jour en début de réunion
- Récapitulez les décisions et actions à la fin de chaque point
- Utilisez des formulations claires ("Il est décidé que...", "Action pour...")

### Pour des conférences
- Structurez votre présentation avec intro/développement/conclusion
- Annoncez vos arguments principaux
- Citez vos sources si pertinent

## Limitations connues

- **Durée maximale** : Pas de limite technique, mais au-delà de 4h le temps de traitement devient important
- **Langues** : Fonctionne mieux en français et anglais (modèles optimisés pour ces langues)
- **Qualité audio** : Un audio de mauvaise qualité donnera une transcription imparfaite
- **Formats spécifiques** : Les diapositives PowerPoint ou tableaux ne sont pas extraits

## Architecture technique

```
┌─────────────────────────────────────────────────────────────┐
│                      Whisper Studio                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  [Frontend] index.html                                       │
│       ↓                                                       │
│  [Backend] app.py (Flask)                                    │
│       ↓                                                       │
│  ┌──────────────────────────────────────────────┐           │
│  │ Mode Document Pipeline                        │           │
│  ├──────────────────────────────────────────────┤           │
│  │ 1. Whisper (faster-whisper-server)           │           │
│  │    - Transcription audio → texte              │           │
│  │                                               │           │
│  │ 2. Ollama (qwen2.5:7b / llama3.1:8b)         │           │
│  │    - ollama_client.py: API client             │           │
│  │    - prompts.py: Prompt templates             │           │
│  │    - Segmentation intelligente                │           │
│  │    - Enrichissement par section               │           │
│  │    - Génération résumé                        │           │
│  │                                               │           │
│  │ 3. DOCX Generator (python-docx)               │           │
│  │    - docx_generator.py: Création document     │           │
│  │    - Styles professionnels                    │           │
│  │    - Formatage automatique                    │           │
│  └──────────────────────────────────────────────┘           │
│       ↓                                                       │
│  [Output] Document.docx + transcript.txt                     │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Prochaines améliorations possibles

- Export PDF en plus de DOCX
- Génération de flashcards Anki pour révision
- Mindmaps visuelles des concepts
- Support multilingue amélioré
- Templates DOCX personnalisables
- Détection automatique du type de contenu

## Support

Pour tout problème ou suggestion :
1. Vérifiez les logs : `docker logs whisper-webui` et `docker logs whisper-ollama`
2. Consultez le README principal
3. Ouvrez une issue sur GitHub

# Configuration de la Diarization (Détection de locuteurs)

## 🎯 Qu'est-ce que la diarization ?

La **diarization** permet de détecter automatiquement les changements de locuteurs dans un audio/vidéo. Cela créera un nouveau sous-titre à chaque fois qu'une personne différente parle, rendant les dialogues beaucoup plus lisibles.

**Exemple :**

Sans diarization :
```srt
1
00:00:01,000 --> 00:00:10,000
Bonjour, comment vas-tu? Très bien merci, et toi?
```

Avec diarization :
```srt
1
00:00:01,000 --> 00:00:03,000
Bonjour, comment vas-tu?

2
00:00:03,500 --> 00:00:10,000
Très bien merci, et toi?
```

## 📋 Prérequis

La diarization utilise le modèle **Pyannote 3.1** de Hugging Face, qui nécessite :

1. **Compte Hugging Face** (gratuit)
2. **Token d'accès** (gratuit)
3. **Acceptation des termes du modèle** (une seule fois)

## 🔧 Installation pas à pas

### Étape 1 : Créer un compte Hugging Face

1. Allez sur https://huggingface.co
2. Cliquez sur "Sign Up" (Inscription)
3. Créez votre compte (gratuit)

### Étape 2 : Générer un token d'accès

1. Connectez-vous à votre compte Hugging Face
2. Allez sur https://huggingface.co/settings/tokens
3. Cliquez sur "New token" (Nouveau token)
4. Donnez-lui un nom (ex: "whisper-diarization")
5. Sélectionnez le type "Read" (Lecture)
6. Cliquez sur "Generate token"
7. **COPIEZ LE TOKEN** (vous ne pourrez plus le voir après !)

### Étape 3 : Accepter les termes du modèle

1. Allez sur https://huggingface.co/pyannote/speaker-diarization-3.1
2. Cliquez sur "Agree and access repository"
3. Acceptez les conditions d'utilisation

### Étape 4 : Configurer le token dans votre projet

1. Copiez le fichier `.env.example` vers `.env` :
   ```bash
   cd /docker/whisper
   cp .env.example .env
   ```

2. Éditez le fichier `.env` :
   ```bash
   nano .env
   ```

3. Remplacez `your_huggingface_token_here` par votre token :
   ```env
   HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

4. Sauvegardez et quittez (Ctrl+O, Entrée, Ctrl+X)

### Étape 5 : Démarrer les services

```bash
cd /docker/whisper
docker compose -f docker-compose-webui.yml up -d --build
```

## ✅ Vérification

Pour vérifier que la diarization fonctionne :

1. Vérifiez les logs du service :
   ```bash
   docker logs pyannote-diarization
   ```

2. Vous devriez voir :
   ```
   [DIARIZATION] Loading pyannote speaker-diarization-3.1 model...
   [DIARIZATION] Using GPU for diarization
   [DIARIZATION] Model loaded successfully!
   ```

3. Testez le health check :
   ```bash
   curl http://localhost:8001/health
   ```

   Réponse attendue :
   ```json
   {
     "status": "ok",
     "model_loaded": true,
     "gpu_available": true
   }
   ```

## 🎬 Utilisation

1. Ouvrez l'interface web : http://localhost:7860
2. Cliquez sur "Sous-titres (SRT)" (mode SRT)
3. **Cochez la case** "Détecter les changements de locuteurs (dialogues)"
4. Uploadez votre vidéo/audio avec dialogue
5. Attendez la fin du traitement

Le fichier SRT généré aura un nouveau segment à chaque changement de locuteur !

## 🐛 Dépannage

### Le service ne démarre pas

**Erreur** : `HF_TOKEN not set - diarization may not work!`

**Solution** : Vérifiez que vous avez bien créé le fichier `.env` avec votre token.

### Modèle non chargé

**Erreur** : `Failed to load diarization model`

**Solutions** :
1. Vérifiez que vous avez accepté les termes sur https://huggingface.co/pyannote/speaker-diarization-3.1
2. Vérifiez que votre token est valide
3. Redémarrez le conteneur :
   ```bash
   docker restart pyannote-diarization
   ```

### La checkbox n'apparaît pas

**Cause** : La checkbox n'apparaît qu'en mode SRT

**Solution** : Cliquez d'abord sur "Sous-titres (SRT)" en haut de la page

### Diarization ignorée

Si la diarization ne fonctionne pas mais qu'il n'y a pas d'erreur :
1. Le service Pyannote n'est peut-être pas disponible (il continuera sans diarization)
2. Vérifiez les logs :
   ```bash
   docker logs whisper-webui
   ```

   Vous devriez voir :
   ```
   [DIARIZATION] Detected 2 speakers in 45 segments
   [SPEAKER] Applying speaker segmentation to 23 segments
   ```

## 📊 Performance

La diarization ajoute environ **2-3 secondes de traitement par minute d'audio**.

Pour une vidéo de 10 minutes :
- Transcription seule : ~30 secondes
- Transcription + diarization : ~50 secondes

C'est un bon compromis pour avoir des sous-titres beaucoup plus lisibles !

## ❓ FAQ

**Q : Est-ce que ça fonctionne avec plusieurs langues ?**
A : Oui, Pyannote fonctionne indépendamment de la langue.

**Q : Combien de locuteurs maximum ?**
A : Pyannote détecte automatiquement le nombre de locuteurs (pas de limite fixe).

**Q : Est-ce que ça affiche le nom des personnes ?**
A : Non, volontairement. Le système détecte juste les changements de voix et crée de nouveaux segments. Pas d'affichage "SPEAKER_00:" dans les sous-titres.

**Q : Ça marche si les gens se coupent la parole ?**
A : Oui ! C'est justement pour ça qu'on utilise Pyannote au lieu de détecter juste les pauses.

**Q : C'est gratuit ?**
A : Oui, complètement gratuit (modèle open-source + self-hosted).

## 🔗 Ressources

- Documentation Pyannote : https://github.com/pyannote/pyannote-audio
- Modèle utilisé : https://huggingface.co/pyannote/speaker-diarization-3.1
- Hugging Face tokens : https://huggingface.co/settings/tokens

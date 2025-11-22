"""
RGPD-compliant legal text templates with placeholders
These templates are used to seed the database with default legal texts
"""

PRIVACY_POLICY_TEMPLATE = """# Politique de Confidentialité

**Dernière mise à jour : {{LAST_UPDATED}}**

## 1. Responsable du traitement

**Organisation** : {{DATA_CONTROLLER_NAME}}
**Email** : {{DATA_CONTROLLER_EMAIL}}
{{#if DPO_EMAIL}}**DPO (Délégué à la Protection des Données)** : {{DPO_EMAIL}}{{/if}}

## 2. Données collectées

Dans le cadre de la fourniture de notre service de transcription audio automatique, nous collectons les données suivantes :

### Données de compte
- **Email** : Pour l'authentification et la communication
- **Nom d'utilisateur** : Optionnel, pour personnaliser votre expérience
- **Mot de passe** : Stocké de manière chiffrée (hash)

### Données de service
- **Fichiers audio** : Les fichiers que vous uploadez pour transcription (supprimés automatiquement après traitement)
- **Transcriptions générées** : Documents DOCX, SRT, TXT produits par le service
- **Métadonnées** : Titres, tags, favoris, types de documents

### Données techniques
- **Logs de traitement** : Historique des jobs (dates, durées, statuts)
- **Préférences** : Thème d'interface (light/dark), paramètres de notification

## 3. Finalité du traitement

Ces données sont collectées et traitées pour les finalités suivantes :

- **Fourniture du service** : Transcription automatique de vos fichiers audio
- **Gestion de compte** : Authentification, sécurité, communication
- **Amélioration du service** : Optimisation des performances et de l'expérience utilisateur

**Base légale** : Exécution du contrat (fourniture du service demandé) - RGPD Art. 6.1.b

## 4. Durée de conservation

- **Fichiers audio uploadés** : Supprimés immédiatement après traitement (transcription terminée)
- **Documents générés** : Conservés tant que votre compte est actif
{{#if AUTO_DELETE_ENABLED}}- **Suppression automatique** : Les documents de plus de {{RETENTION_DAYS}} jours peuvent être supprimés automatiquement (notification {{DELETION_NOTIFICATION_DAYS}} jours avant suppression){{/if}}
- **Compte utilisateur** : Tant que le compte est actif. En cas d'inactivité de plus d'un an, un email de notification vous sera envoyé 30 jours avant la suppression automatique de votre compte et de toutes vos données
- **Logs techniques** : 90 jours maximum

Vous pouvez à tout moment télécharger vos documents depuis votre bibliothèque ou supprimer votre compte pour effacer toutes vos données.

## 5. Vos droits (RGPD)

Conformément au Règlement Général sur la Protection des Données (RGPD), vous disposez des droits suivants :

### Droit d'accès (Art. 15)
Vous pouvez consulter toutes vos données depuis votre profil et votre bibliothèque.

### Droit de rectification (Art. 16)
Vous pouvez modifier vos informations personnelles (email, nom d'utilisateur, mot de passe) depuis votre profil.

### Droit à l'effacement / Droit à l'oubli (Art. 17)
Vous pouvez supprimer votre compte et toutes vos données associées de manière définitive depuis votre profil → "Supprimer mon compte".

Cette action supprime :
- Votre compte utilisateur
- Tous les fichiers uploadés
- Tous les documents générés
- Tout l'historique de traitement

### Droit à la portabilité (Art. 20)
Vous pouvez télécharger toutes vos données au format ZIP depuis votre profil → "Télécharger mes données" (fonctionnalité à venir).

L'export contiendra :
- Vos informations de compte (JSON)
- Tous vos documents (DOCX, SRT, TXT)
- Votre historique de traitement (JSON)

### Droit d'opposition (Art. 21)
Vous pouvez vous opposer au traitement de vos données en supprimant votre compte ou en nous contactant à {{DATA_CONTROLLER_EMAIL}}.

### Droit de limitation (Art. 18)
Vous pouvez demander la limitation du traitement en nous contactant.

**Pour exercer vos droits** : Utilisez les fonctionnalités de votre profil ou contactez-nous à {{DATA_CONTROLLER_EMAIL}}.

## 6. Sécurité des données

Nous mettons en œuvre toutes les mesures techniques et organisationnelles appropriées pour protéger vos données contre tout accès non autorisé, modification, divulgation ou destruction.

Ces mesures incluent notamment :
- Le chiffrement des communications et des mots de passe
- L'isolation des données entre utilisateurs
- L'authentification sécurisée
- Des sauvegardes régulières
- La suppression sécurisée des données

## 7. Cookies

Nous utilisons des cookies pour le fonctionnement du site. Voici les types de cookies utilisés :

### Cookies strictement nécessaires (pas de consentement requis)
Ces cookies sont indispensables au fonctionnement du site :

- **Cookie de session** : Authentification (supprimé à la déconnexion)
- **Cookie de préférences** : Thème light/dark (localStorage)

Ces cookies ne nécessitent pas de consentement selon le RGPD (Art. 6.1.f - intérêt légitime).

{{#if COOKIES_ANALYTICS_ENABLED}}
### Cookies analytiques (consentement requis)
Si vous acceptez, nous utilisons des cookies pour analyser l'utilisation du site :

- **Statistiques de pages vues**
- **Durée de session**
- **Données anonymisées**

Vous pouvez retirer votre consentement à tout moment via le lien "Gérer mes cookies" en bas de page.
{{/if}}

{{#if COOKIES_PREFERENCES_ENABLED}}
### Cookies de préférences (consentement requis)
Si vous acceptez, nous mémorisons vos préférences :

- **Langue préférée**
- **Paramètres d'affichage personnalisés**
{{/if}}

### Gestion de vos cookies
- Modifier vos choix : Lien "Gérer mes cookies" en bas de page
- Supprimer les cookies : Paramètres de votre navigateur
- Refuser les cookies : Fonctionnalités essentielles peuvent être affectées

## 8. Partage des données

Nous ne vendons ni ne louons vos données personnelles à des tiers.

Vos données peuvent être partagées uniquement dans les cas suivants :

- **Hébergement** : Nos serveurs sont hébergés chez {{#if HOSTING_INFO}}{{HOSTING_INFO}}{{else}}[À compléter par l'administrateur]{{/if}}
- **Obligation légale** : Si requis par la loi ou une autorité compétente

Aucun transfert de données hors de l'Union Européenne n'est effectué.

## 9. Modification de la politique

Nous nous réservons le droit de modifier cette politique de confidentialité.

En cas de modification substantielle, vous serez informé par email et/ou via une notification sur le site.

**Date de dernière modification** : {{LAST_UPDATED}}

## 10. Contact

Pour toute question concernant vos données personnelles ou cette politique :

**Email** : {{DATA_CONTROLLER_EMAIL}}
{{#if DPO_EMAIL}}**DPO** : {{DPO_EMAIL}}{{/if}}

Vous avez également le droit d'introduire une réclamation auprès de la CNIL (Commission Nationale de l'Informatique et des Libertés) : [www.cnil.fr](https://www.cnil.fr)
"""


TERMS_TEMPLATE = """# Conditions Générales d'Utilisation (CGU)

**Dernière mise à jour : {{LAST_UPDATED}}**

## 1. Objet

Les présentes Conditions Générales d'Utilisation (ci-après « CGU ») régissent l'utilisation du service de transcription audio automatique fourni par {{DATA_CONTROLLER_NAME}} (ci-après « le Service »).

## 2. Acceptation des CGU

L'utilisation du Service implique l'acceptation pleine et entière des présentes CGU.

En cochant la case « J'accepte les CGU » lors de l'inscription, vous reconnaissez avoir pris connaissance et accepté ces conditions.

## 3. Description du Service

Le Service propose les fonctionnalités suivantes :

- **Transcription automatique** : Conversion de fichiers audio en texte via technologie Whisper AI
- **Formats supportés** : MP3, WAV, M4A, OGG, FLAC, AAC, WMA, OPUS, vidéos (MP4, AVI, MOV, etc.)
- **Génération de documents** : Formats DOCX (traitement de texte) et SRT (sous-titres)
- **Stockage temporaire** : Conservation des documents générés pendant {{RETENTION_DAYS}} jours
- **Limite de stockage** : {{STORAGE_LIMIT}} Go par utilisateur

## 4. Inscription et compte utilisateur

### 4.1 Création de compte
- Fournir une adresse email valide
- Créer un mot de passe sécurisé (minimum 8 caractères)
- Accepter les présentes CGU et la Politique de confidentialité

### 4.2 Responsabilité du compte
Vous êtes responsable de :
- La confidentialité de vos identifiants
- Toutes les activités effectuées depuis votre compte
- Nous informer rapidement en cas d'accès non autorisé à votre compte

### 4.3 Exactitude des informations
Vous vous engagez à fournir des informations exactes et à les maintenir à jour.

## 5. Utilisation du Service

### 5.1 Utilisation autorisée
Le Service est destiné à un usage personnel ou professionnel :
- Transcription de réunions, conférences, interviews
- Génération de sous-titres pour vidéos
- Création de comptes-rendus et documents

### 5.2 Utilisation interdite
Il est strictement interdit de :
- Transcrire des contenus illégaux, diffamatoires, ou violant des droits de propriété intellectuelle
- Utiliser le Service pour du spam, phishing, ou activités malveillantes
- Tenter de contourner les limitations techniques ou de sécurité
- Revendre ou redistribuer le Service sans autorisation

### 5.3 Droits de propriété intellectuelle
Vous conservez tous les droits sur vos fichiers audio et les transcriptions générées.

Vous devez détenir les droits nécessaires sur les fichiers uploadés (ou avoir l'autorisation des ayants droit).

{{DATA_CONTROLLER_NAME}} ne revendique aucun droit sur vos contenus.

## 6. Limitation de responsabilité

### 6.1 Service fourni "en l'état"
Le Service utilise une technologie de reconnaissance vocale automatique (Whisper AI).

Nous ne garantissons pas :
- L'exactitude à 100% des transcriptions
- La reconnaissance parfaite de tous les accents ou langues
- La disponibilité continue du Service (maintenance, pannes techniques)

### 6.2 Limitation de responsabilité
{{DATA_CONTROLLER_NAME}} ne saurait être tenu responsable :
- Des erreurs de transcription ou d'interprétation
- Des pertes de données dues à des pannes techniques
- Des dommages indirects (perte de temps, de revenus, etc.)
- De l'utilisation que vous faites des transcriptions générées

### 6.3 Vérification des transcriptions
Il vous appartient de vérifier et corriger les transcriptions générées avant toute utilisation critique.

## 7. Propriété intellectuelle du Service

### 7.1 Projet open-source
Le Service est un projet **open-source** publié sous **licence MIT** :
- **Code source** : [github.com/valentin-gosselin/whisper-studio](https://github.com/valentin-gosselin/whisper-studio)
- **Licence** : MIT License

### 7.2 Libertés accordées par la licence MIT
**Vous êtes libre de** :
- Utiliser ce logiciel à des fins personnelles ou commerciales
- Modifier le code source selon vos besoins
- Distribuer et redistribuer le logiciel
- Créer des œuvres dérivées
- Déployer votre propre instance
- Contribuer au projet open-source

La seule obligation : conserver la notice de copyright et la licence MIT dans les copies.

### 7.3 Hébergement et exploitation
Cette instance est hébergée et exploitée par {{DATA_CONTROLLER_NAME}}.

**Important** : Bien que le code soit libre et open-source, cette instance spécifique est gérée par {{DATA_CONTROLLER_NAME}} qui en assure la maintenance, la sécurité et l'hébergement.

**Contributions bienvenues** : N'hésitez pas à contribuer au projet sur GitHub !

## 8. Protection des données personnelles

Le traitement de vos données personnelles est décrit dans notre [Politique de confidentialité](/privacy-policy).

En résumé :
- **Fichiers audio** : Supprimés immédiatement après traitement
- **Documents générés** : Conservés tant que votre compte est actif
- **Compte inactif** : Suppression automatique après 1 an d'inactivité (notification 30 jours avant)
- **Vos droits RGPD** : Accès, rectification, suppression, portabilité de vos données
- **Suppression de compte** : Disponible à tout moment depuis votre profil

## 9. Conservation et suppression des données

### 9.1 Durée de conservation
- **Fichiers audio uploadés** : Supprimés immédiatement après le traitement (transcription terminée)
- **Documents générés** (DOCX, SRT, TXT) : Conservés tant que votre compte est actif
- **Compte inactif** : Après 1 an d'inactivité, notification par email 30 jours avant suppression automatique

### 9.2 Téléchargement de vos données
Vous pouvez télécharger vos documents à tout moment depuis votre bibliothèque.

### 9.3 Suppression de compte
Vous pouvez supprimer votre compte depuis votre profil. Cette action est irréversible et supprime toutes vos données (compte, documents, historique).

## 10. Modification des CGU

Nous nous réservons le droit de modifier les présentes CGU à tout moment.

En cas de modification substantielle :
- Vous serez informé par email
- Les nouvelles CGU entreront en vigueur 30 jours après notification
- Continuer à utiliser le Service après cette période vaut acceptation des nouvelles CGU

## 11. Résiliation

### 11.1 Résiliation par l'utilisateur
Vous pouvez résilier votre compte à tout moment en le supprimant depuis votre profil.

### 11.2 Résiliation par le Service
Nous nous réservons le droit de suspendre ou supprimer votre compte en cas de :
- Violation des présentes CGU
- Utilisation frauduleuse ou abusive
- Non-paiement (si applicable dans une version payante future)
- Inactivité prolongée (plus de 12 mois)

En cas de suspension, vous serez informé par email avec possibilité de récupérer vos données pendant 30 jours.

## 12. Droit applicable et juridiction

Les présentes CGU sont régies par le droit français.

En cas de litige, les parties s'efforceront de trouver une solution amiable.

À défaut, les tribunaux français seront seuls compétents.

## 13. Contact

Pour toute question concernant ces CGU :

**Email** : {{DATA_CONTROLLER_EMAIL}}

## 14. Dispositions finales

Si une clause des présentes CGU est déclarée nulle ou inapplicable, les autres clauses restent en vigueur.

L'absence d'exercice d'un droit ne constitue pas une renonciation à ce droit.

**Date d'acceptation** : Enregistrée lors de votre inscription ({{TERMS_ACCEPTED_AT}})
"""


LEGAL_MENTIONS_TEMPLATE = """# Mentions Légales

**Dernière mise à jour : {{LAST_UPDATED}}**

Conformément aux dispositions de la loi n° 2004-575 du 21 juin 2004 pour la confiance dans l'économie numérique, il est précisé aux utilisateurs du site les présentes mentions légales.

## 1. Éditeur du site

**Organisation** : {{DATA_CONTROLLER_NAME}}
**Email** : {{DATA_CONTROLLER_EMAIL}}

{{#if EDITOR_INFO}}
{{EDITOR_INFO}}
{{else}}
**Note** : Informations complémentaires à configurer par l'administrateur (adresse, SIRET, téléphone, etc.)
{{/if}}

## 2. Responsable de la publication

**Responsable** : {{DATA_CONTROLLER_NAME}}
**Email** : {{DATA_CONTROLLER_EMAIL}}

## 3. Hébergement

{{#if HOSTING_INFO}}
{{HOSTING_INFO}}
{{else}}
**À compléter par l'administrateur**

Nom de l'hébergeur :
Adresse :
Téléphone :
{{/if}}

## 4. Protection des données personnelles

### 4.1 Responsable du traitement
**Responsable du traitement** : {{DATA_CONTROLLER_NAME}}
**Email** : {{DATA_CONTROLLER_EMAIL}}

{{#if DPO_EMAIL}}
### 4.2 Délégué à la Protection des Données (DPO)
**Email du DPO** : {{DPO_EMAIL}}
{{/if}}

### 4.3 Finalité du traitement
Le traitement de vos données personnelles est effectué dans le cadre de la fourniture du service de transcription audio.

**Base légale** : Exécution du contrat (RGPD Art. 6.1.b)

### 4.4 Vos droits
Vous disposez des droits suivants :
- Droit d'accès (Art. 15)
- Droit de rectification (Art. 16)
- Droit à l'effacement / Droit à l'oubli (Art. 17)
- Droit à la portabilité (Art. 20)
- Droit d'opposition (Art. 21)

Pour exercer vos droits : {{DATA_CONTROLLER_EMAIL}}

### 4.5 Réclamation
Vous avez le droit d'introduire une réclamation auprès de la CNIL :
- Site web : [www.cnil.fr](https://www.cnil.fr)
- Adresse : 3 Place de Fontenoy - TSA 80715 - 75334 PARIS CEDEX 07
- Téléphone : 01 53 73 22 22

## 5. Propriété intellectuelle

### 5.1 Projet open-source
Ce service est un **projet open-source** publié sous **licence MIT** :
- **Code source** : [github.com/valentin-gosselin/whisper-studio](https://github.com/valentin-gosselin/whisper-studio)
- **Licence** : MIT License

### 5.2 Libertés accordées
La licence MIT vous permet de :
- Utiliser le logiciel à des fins personnelles ou commerciales
- Modifier, distribuer et créer des œuvres dérivées
- Déployer votre propre instance
- Contribuer au projet

### 5.3 Hébergement
Cette instance est hébergée et exploitée par {{DATA_CONTROLLER_NAME}}.

Le code source reste libre et ouvert sous licence MIT, mais chaque instance déployée est gérée indépendamment par son opérateur.

## 6. Cookies

Le site utilise des cookies strictement nécessaires au fonctionnement :
- Cookie de session (authentification)
- Cookie de préférences (thème d'interface)

Pour plus d'informations : [Politique de confidentialité](/privacy-policy#cookies)

## 7. Limitation de responsabilité

{{DATA_CONTROLLER_NAME}} ne saurait être tenu responsable :
- Des erreurs de transcription générées par l'IA
- Des interruptions de service dues à des cas de force majeure
- Des dommages indirects résultant de l'utilisation du service

## 8. Loi applicable

Les présentes mentions légales sont soumises au droit français.

## 9. Contact

Pour toute question concernant ces mentions légales :

**Email** : {{DATA_CONTROLLER_EMAIL}}
"""

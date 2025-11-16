"""
Ollama prompts library for document generation
Optimized prompts for different document types and analysis stages
"""


def get_segmentation_prompt(transcript: str, doc_type: str, language: str) -> str:
    """
    Generate prompt for analyzing and structuring transcript content
    Uses a simpler approach: ask for outline, then we'll handle segmentation

    Args:
        transcript: Full transcript text
        doc_type: Type of document (course, meeting, conference, interview, other)
        language: Language code (fr, en, etc.)

    Returns:
        Formatted prompt string
    """

    type_instructions = {
        'course': "Identifie les chapitres/sujets principaux du cours, les concepts clés abordés, et structure l'information de manière pédagogique.",
        'meeting': "Identifie les points à l'ordre du jour, les décisions prises, et les actions à mener.",
        'conference': "Identifie les arguments principaux, les points clés, et la structure de la présentation.",
        'interview': "Identifie les questions principales et les réponses, organisées par thème.",
        'other': "Identifie les sujets principaux et structure l'information de manière logique."
    }

    instruction = type_instructions.get(doc_type, type_instructions['other'])

    # Simplified prompt: just extract structure, we'll handle segmentation ourselves
    prompt = f"""Tu es un assistant qui analyse des transcriptions audio pour créer des notes structurées.

TÂCHE: Analyse cette transcription de {doc_type} et identifie sa structure principale.

{instruction}

IMPORTANT:
- Réponds UNIQUEMENT en JSON valide, sans texte additionnel
- Utilise le français pour tous les textes
- Extrais les points clés EXACTS du transcript (ne pas inventer)
- Reste fidèle au contenu réel

FORMAT DE SORTIE (JSON):
{{
  "titre_document": "Titre clair et descriptif du {doc_type} (max 10 mots)",
  "sujet_principal": "Description du sujet global en une phrase",
  "sections": [
    {{
      "titre": "Titre de la section",
      "points_cles": ["Point 1", "Point 2", "..."],
      "mots_cles": ["mot1", "mot2", "..."]
    }}
  ]
}}

TRANSCRIPTION:
{transcript[:8000]}

JSON:"""

    return prompt


def get_enrichment_prompt(section_text: str, section_title: str, doc_type: str, language: str) -> str:
    """
    Generate prompt for enriching a section with structure and key points

    Args:
        section_text: Raw section text
        section_title: Section title
        doc_type: Type of document
        language: Language code

    Returns:
        Formatted prompt string
    """

    type_instructions = {
        'course': """Pour un cours, rédige un texte structuré qui:
- Présente les concepts de façon pédagogique et progressive
- Intègre naturellement les définitions dans le texte (en gras si important)
- Illustre avec les exemples mentionnés
- Organise logiquement les idées""",
        'meeting': """Pour une réunion, rédige un texte structuré qui:
- Résume les discussions par point à l'ordre du jour
- Mentionne clairement les décisions prises
- Liste les actions à mener avec les responsables
- Note les échéances importantes""",
        'conference': """Pour une conférence, rédige un texte structuré qui:
- Développe les arguments principaux
- Présente les preuves et données mentionnées
- Explique les conclusions et implications
- Suit la logique de la présentation""",
        'interview': """Pour une interview, rédige un texte structuré qui:
- Organise par thématiques ou questions principales
- Rapporte les insights et points de vue partagés
- Cite les éléments marquants
- Maintient le fil conducteur""",
        'other': """Rédige un texte structuré qui:
- Organise les idées de manière logique
- Présente clairement les informations importantes
- Utilise des paragraphes cohérents"""
    }

    instruction = type_instructions.get(doc_type, type_instructions['other'])

    prompt = f"""Tu es un rédacteur professionnel qui transforme des transcriptions audio brutes en notes structurées et lisibles.

TÂCHE: Reformule cette section de {doc_type} en un texte rédigé professionnel.

Section: "{section_title}"

{instruction}

RÈGLES IMPORTANTES:
- Transforme le flux de parole brut en texte bien rédigé avec ponctuation correcte
- IMPORTANT: Utilise la ponctuation typographique correcte de la langue ({language})
  * Pour le français: guillemets « ... », apostrophes ', etc.
  * Pour l'anglais: guillemets "...", apostrophes ', etc.
- Organise en 3-6 paragraphes cohérents (saute des lignes entre les paragraphes avec \\n\\n)
- Élimine les hésitations ("euh", "donc euh", répétitions inutiles)
- Garde TOUT le contenu informatif important - ne rien omettre
- Améliore la clarté sans changer le sens
- Utilise un style clair, professionnel et agréable à lire
- Structure naturellement selon le type de contenu (pas de format imposé)
- Réponds UNIQUEMENT en JSON valide, sans texte additionnel

FORMAT DE SORTIE (JSON):
{{
  "title": "Titre descriptif et précis de la section",
  "content": "Premier paragraphe qui introduit le sujet principal et pose le contexte de manière claire.\\n\\nDeuxième paragraphe qui développe les concepts clés avec des explications détaillées. Les définitions importantes sont intégrées naturellement dans le texte.\\n\\nTroisième paragraphe qui présente les exemples concrets mentionnés, en gardant le contexte pour qu'ils soient bien compréhensibles.\\n\\nQuatrième paragraphe (optionnel) qui conclut ou fait la synthèse des points importants."
}}

TRANSCRIPTION AUDIO BRUTE:
{section_text}

JSON:"""

    return prompt


def get_summary_prompt(sections, doc_type: str, language: str) -> str:
    """
    Generate prompt for creating executive summary

    Args:
        sections: List of enriched sections
        doc_type: Type of document
        language: Language code

    Returns:
        Formatted prompt string
    """

    # Combine all key points from sections
    all_key_points = []
    for section in sections:
        title = section.get('title', '')
        points = section.get('key_points', [])
        if points:
            all_key_points.append(f"\n{title}:")
            all_key_points.extend([f"- {point}" for point in points])

    key_points_text = '\n'.join(all_key_points)

    type_instructions = {
        'course': "Rédige un résumé mettant en avant les objectifs pédagogiques, les concepts clés enseignés, et les points pratiques à retenir.",
        'meeting': "Rédige un résumé mettant en avant les décisions prises, les actions assignées, et les prochaines étapes.",
        'conference': "Rédige un résumé mettant en avant la thèse principale, les découvertes clés, et les implications.",
        'interview': "Rédige un résumé mettant en avant les insights partagés, les citations importantes, et les thèmes discutés.",
        'other': "Rédige un résumé concis mettant en avant les points principaux et conclusions."
    }

    instruction = type_instructions.get(doc_type, type_instructions['other'])

    prompt = f"""Tu es un assistant qui rédige des résumés exécutifs pour des transcriptions de {doc_type}.

TÂCHE: Crée un résumé exécutif basé sur les points clés extraits.

{instruction}

RÈGLES:
- Maximum 250 mots
- Utilise le français
- Sois concis mais complet
- Mets en avant l'information la plus importante
- Structure en paragraphes clairs
- Base-toi UNIQUEMENT sur les points clés fournis (ne pas inventer)

POINTS CLÉS DE TOUTES LES SECTIONS:
{key_points_text}

RÉSUMÉ EXÉCUTIF:"""

    return prompt


# Utility function to estimate token count (rough approximation)
def estimate_tokens(text: str) -> int:
    """
    Estimate number of tokens in text

    Args:
        text: Input text

    Returns:
        Estimated token count (rough: 1 token ≈ 4 characters)
    """
    return len(text) // 4

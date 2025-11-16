"""
Ollama Client for AI-powered document generation
Handles communication with Ollama LLM service for transcript analysis
"""
import os
import requests
import json
import time
from typing import Dict, List, Optional, Tuple


class OllamaClient:
    """Client for interacting with Ollama LLM service"""

    def __init__(self, base_url: str = None, primary_model: str = None, fallback_model: str = None):
        self.base_url = base_url or os.environ.get('OLLAMA_URL', 'http://ollama:11434')
        self.primary_model = primary_model or os.environ.get('OLLAMA_MODEL_PRIMARY', 'qwen2.5:7b')
        self.fallback_model = fallback_model or os.environ.get('OLLAMA_MODEL_FALLBACK', 'llama3.1:8b')
        self.current_model = self.primary_model
        self.timeout = 300  # 5 minutes timeout for long contexts

    def health_check(self) -> bool:
        """Check if Ollama service is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"[OLLAMA] Health check failed: {e}")
            return False

    def list_models(self) -> List[str]:
        """List available models"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except Exception as e:
            print(f"[OLLAMA] Failed to list models: {e}")
            return []

    def chat(self, prompt: str, system_prompt: str = None, model: str = None,
             temperature: float = 0.7, max_retries: int = 2) -> Optional[str]:
        """
        Send a chat request to Ollama

        Args:
            prompt: User prompt
            system_prompt: System prompt for context
            model: Model to use (defaults to primary_model)
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
            max_retries: Number of retries on failure

        Returns:
            Model response as string or None on failure
        """
        model = model or self.current_model

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 4096  # Max tokens to generate
            }
        }

        for attempt in range(max_retries + 1):
            try:
                print(f"[OLLAMA] Sending request to {model} (attempt {attempt + 1}/{max_retries + 1})")
                start_time = time.time()

                response = requests.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=self.timeout
                )

                elapsed = time.time() - start_time
                print(f"[OLLAMA] Response received in {elapsed:.1f}s")

                if response.status_code == 200:
                    data = response.json()
                    content = data.get('message', {}).get('content', '')

                    if content:
                        print(f"[OLLAMA] Success: {len(content)} characters generated")
                        return content
                    else:
                        print(f"[OLLAMA] Warning: Empty response")
                        if attempt < max_retries:
                            continue
                else:
                    print(f"[OLLAMA] HTTP error {response.status_code}: {response.text}")

                    # Try fallback model on error
                    if model == self.primary_model and attempt == 0:
                        print(f"[OLLAMA] Switching to fallback model: {self.fallback_model}")
                        model = self.fallback_model
                        payload['model'] = model
                        continue

            except requests.exceptions.Timeout:
                print(f"[OLLAMA] Timeout after {self.timeout}s")
                if attempt < max_retries:
                    time.sleep(2)
                    continue
            except Exception as e:
                print(f"[OLLAMA] Error: {e}")
                if attempt < max_retries:
                    time.sleep(2)
                    continue

        return None

    def segment_transcript(self, transcript: str, doc_type: str, language: str = 'fr') -> Optional[List[Dict]]:
        """
        Segment transcript into logical sections

        Args:
            transcript: Full transcript text
            doc_type: Type of document (course, meeting, conference, etc.)
            language: Language code

        Returns:
            List of sections with titles and text, or None on failure
        """
        from prompts import get_segmentation_prompt

        system_prompt = f"You are an expert at analyzing and structuring {doc_type} transcripts in {language}."
        user_prompt = get_segmentation_prompt(transcript, doc_type, language)

        print(f"[OLLAMA SEGMENT] Analyzing {len(transcript)} characters ({doc_type})")

        response = self.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3  # Low temperature for structured output
        )

        if not response:
            return None

        try:
            # Clean response (remove markdown code blocks if present)
            cleaned = response.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]  # Remove ```json
            elif cleaned.startswith('```'):
                cleaned = cleaned[3:]  # Remove ```
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]  # Remove trailing ```
            cleaned = cleaned.strip()

            # Parse JSON response
            sections = json.loads(cleaned)
            print(f"[OLLAMA SEGMENT] Extracted {len(sections)} sections")
            return sections
        except json.JSONDecodeError as e:
            print(f"[OLLAMA SEGMENT] Failed to parse JSON: {e}")
            print(f"[OLLAMA SEGMENT] Raw response: {response[:500]}...")
            return None

    def enrich_section(self, section_text: str, section_title: str,
                      doc_type: str, language: str = 'fr') -> Optional[Dict]:
        """
        Enrich a single section with structure and key points

        Args:
            section_text: Raw section text
            section_title: Section title
            doc_type: Type of document
            language: Language code

        Returns:
            Enriched section dict or None on failure
        """
        from prompts import get_enrichment_prompt

        system_prompt = f"You are an expert at creating professional {doc_type} notes in {language}."
        user_prompt = get_enrichment_prompt(section_text, section_title, doc_type, language)

        print(f"[OLLAMA ENRICH] Processing section: {section_title} ({len(section_text)} chars)")

        response = self.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.5  # Moderate temperature for natural language
        )

        if not response:
            return None

        try:
            # Clean response (remove markdown code blocks and extra text)
            cleaned = response.strip()

            # Remove markdown code blocks
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            elif cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # Try to extract JSON if there's text before/after
            # Look for { ... } pattern
            if not cleaned.startswith('{'):
                start = cleaned.find('{')
                if start != -1:
                    cleaned = cleaned[start:]
            if not cleaned.endswith('}'):
                end = cleaned.rfind('}')
                if end != -1:
                    cleaned = cleaned[:end+1]

            enriched = json.loads(cleaned)
            print(f"[OLLAMA ENRICH] Section enriched successfully")
            return enriched
        except json.JSONDecodeError as e:
            print(f"[OLLAMA ENRICH] Failed to parse JSON: {e}")
            print(f"[OLLAMA ENRICH] Response preview: {response[:200]}...")

            # Fallback: Try to extract content from malformed JSON manually
            # The JSON is malformed but often contains the full content
            import re

            # Strategy 1: Try to find "content": "..." with proper handling of escaped quotes
            # Look for the content field and extract until the closing quote/brace
            content_start = response.find('"content"')
            if content_start != -1:
                # Find the start of the actual content (after "content": ")
                value_start = response.find('"', content_start + len('"content"'))
                if value_start != -1:
                    value_start += 1  # Skip the opening quote

                    # Find the end - look for "}  that signals end of JSON
                    # We can't rely on finding closing quote because content may have unescaped quotes
                    # Instead, find the last sensible content before the JSON structure ends
                    value_end = response.rfind('}')
                    if value_end != -1:
                        # Work backwards to find where content likely ends
                        # Content ends before the closing quote + closing brace
                        content_section = response[value_start:value_end]

                        # Find the last quote before the closing brace
                        last_quote = content_section.rfind('"')
                        if last_quote != -1:
                            content = content_section[:last_quote]
                        else:
                            content = content_section.strip()

                        # Unescape JSON strings
                        content = content.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                        print(f"[OLLAMA ENRICH] Extracted content from malformed JSON ({len(content)} chars)")
                        return {
                            "title": section_title,
                            "content": content
                        }

            # Last resort: use entire response cleaned
            print(f"[OLLAMA ENRICH] Using full response as fallback")
            cleaned_content = response.replace('```json', '').replace('```', '').strip()
            # Remove JSON structure markers
            cleaned_content = re.sub(r'^\s*\{.*?"content"\s*:\s*"', '', cleaned_content, flags=re.DOTALL)
            cleaned_content = re.sub(r'"\s*\}\s*$', '', cleaned_content, flags=re.DOTALL)
            return {
                "title": section_title,
                "content": cleaned_content
            }

    def generate_summary(self, sections: List[Dict], doc_type: str, language: str = 'fr') -> Optional[str]:
        """
        Generate executive summary from all sections

        Args:
            sections: List of enriched sections
            doc_type: Type of document
            language: Language code

        Returns:
            Summary text or None on failure
        """
        from prompts import get_summary_prompt

        system_prompt = f"You are an expert at writing concise summaries of {doc_type} in {language}."
        user_prompt = get_summary_prompt(sections, doc_type, language)

        print(f"[OLLAMA SUMMARY] Generating summary from {len(sections)} sections")

        response = self.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.6  # Slightly higher for natural summary
        )

        if response:
            print(f"[OLLAMA SUMMARY] Generated summary: {len(response)} characters")

        return response

    def chunk_long_transcript(self, transcript: str, max_chars: int = 15000) -> List[str]:
        """
        Split very long transcripts into manageable chunks

        Args:
            transcript: Full transcript
            max_chars: Maximum characters per chunk

        Returns:
            List of transcript chunks
        """
        if len(transcript) <= max_chars:
            return [transcript]

        chunks = []
        current_chunk = ""

        # Split by paragraphs (double newline) or sentences
        paragraphs = transcript.split('\n\n')

        for para in paragraphs:
            if len(current_chunk) + len(para) > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += '\n\n' + para if current_chunk else para

        if current_chunk:
            chunks.append(current_chunk.strip())

        print(f"[OLLAMA CHUNK] Split transcript into {len(chunks)} chunks")
        return chunks


# Singleton instance
_ollama_client = None

def get_ollama_client() -> OllamaClient:
    """Get or create Ollama client singleton"""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client

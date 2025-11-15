"""
SRT (SubRip) utilities for subtitle processing
Ported from video_to_srt Node.js implementation to Python
"""
import re
from typing import List, Dict, Optional, Tuple


class SRTSegment:
    """Represents a single SRT subtitle segment"""
    def __init__(self, index: int, start_time: float, end_time: float, text: str):
        self.index = index
        self.start_time = start_time
        self.end_time = end_time
        self.text = text


def parse_srt(srt_content: str) -> List[SRTSegment]:
    """
    Parse SRT content into segments

    Args:
        srt_content: SRT file content as string

    Returns:
        List of SRTSegment objects
    """
    segments = []
    blocks = srt_content.strip().split('\n\n')

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        try:
            index = int(lines[0])
        except ValueError:
            continue

        time_line = lines[1]
        text = '\n'.join(lines[2:])

        # Parse timestamps: 00:00:10,500 --> 00:00:13,000
        match = re.match(
            r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})',
            time_line
        )
        if not match:
            continue

        start_time = parse_timestamp(match[1], match[2], match[3], match[4])
        end_time = parse_timestamp(match[5], match[6], match[7], match[8])

        segments.append(SRTSegment(index, start_time, end_time, text))

    return segments


def parse_timestamp(hours: str, minutes: str, seconds: str, milliseconds: str) -> float:
    """Convert SRT timestamp components to seconds (float)"""
    return (
        int(hours) * 3600 +
        int(minutes) * 60 +
        int(seconds) +
        int(milliseconds) / 1000
    )


def format_srt_timestamp(seconds: float) -> str:
    """
    Format seconds to SRT timestamp (HH:MM:SS,mmm)

    Args:
        seconds: Time in seconds (float)

    Returns:
        SRT formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def group_words_into_subtitles(words: List[Dict], max_chars_per_line: int = 42, max_lines: int = 2, max_duration: float = 7.0) -> List[SRTSegment]:
    """
    Group word-level timestamps into well-formatted subtitle segments

    Following Netflix subtitle guidelines:
    - Max 42 characters per line
    - Max 2 lines per subtitle
    - Max ~7 seconds duration per subtitle
    - Break at natural pauses (punctuation, pauses in speech)

    Args:
        words: List of word dicts with 'word', 'start', 'end' keys
        max_chars_per_line: Maximum characters per line (default 42)
        max_lines: Maximum lines per subtitle (default 2)
        max_duration: Maximum duration in seconds (default 7.0)

    Returns:
        List of SRTSegment objects
    """
    if not words:
        return []

    # FIX: Merge words starting with apostrophes with previous word
    # This fixes a known Whisper API bug where French contractions like "l'entrée"
    # are split into "l " and "'entrée" (see faster-whisper issue #899)
    merged_words = []
    for i, word_dict in enumerate(words):
        word = word_dict.get('word', '').strip()
        if not word:
            continue

        # If word starts with apostrophe or dash, merge with previous word
        if i > 0 and word and word[0] in ["'", "-", "–"] and merged_words:
            prev = merged_words[-1]
            # Merge the text (removing space between them)
            prev['word'] = prev['word'].rstrip() + word
            # Extend the end time to include this word
            prev['end'] = word_dict['end']
        else:
            merged_words.append(word_dict.copy())

    words = merged_words

    segments = []
    current_words = []
    current_start = None

    def create_segment_from_words(words_buffer):
        """
        Create one or more segments from a buffer of words
        Splits into multiple segments if needed to respect max 2 lines per segment
        """
        if not words_buffer:
            return

        # Build lines from words, detecting natural line breaks
        all_lines = []  # List of dicts: {'words': [word_dicts], 'text': str}
        current_line_words = []
        current_length = 0

        for i, word_dict in enumerate(words_buffer):
            word = word_dict['word'].strip()
            if not word:
                continue

            # Check for natural line breaks (comma, pause)
            prev_has_comma = False
            if i > 0 and current_line_words:
                prev_word_text = words_buffer[i-1]['word'].strip()
                prev_has_comma = prev_word_text and prev_word_text[-1] in ',;'

            pause_threshold = 0.8
            has_pause = False
            if i > 0 and current_line_words:
                prev_word = words_buffer[i-1]
                gap = word_dict['start'] - prev_word['end']
                has_pause = gap >= pause_threshold

            word_len = len(word) + 1

            # Start new line if natural break or exceeds length
            if (prev_has_comma or has_pause) and current_line_words:
                all_lines.append({
                    'words': current_line_words.copy(),
                    'text': ' '.join(w['word'].strip() for w in current_line_words)
                })
                current_line_words = [word_dict]
                current_length = word_len
            elif current_length + word_len > max_chars_per_line and current_line_words:
                all_lines.append({
                    'words': current_line_words.copy(),
                    'text': ' '.join(w['word'].strip() for w in current_line_words)
                })
                current_line_words = [word_dict]
                current_length = word_len
            else:
                current_line_words.append(word_dict)
                current_length += word_len

        # Add last line
        if current_line_words:
            all_lines.append({
                'words': current_line_words.copy(),
                'text': ' '.join(w['word'].strip() for w in current_line_words)
            })

        # Now split lines into segments (max 2 lines per segment)
        for line_idx in range(0, len(all_lines), max_lines):
            segment_lines = all_lines[line_idx:line_idx + max_lines]

            # Get all words for this segment
            segment_words = []
            for line in segment_lines:
                segment_words.extend(line['words'])

            if not segment_words:
                continue

            # Create segment
            text = '\n'.join(line['text'] for line in segment_lines)
            start_time = segment_words[0]['start']
            end_time = segment_words[-1]['end']

            segments.append(SRTSegment(
                index=len(segments) + 1,
                start_time=start_time,
                end_time=end_time,
                text=text
            ))

    for i, word_dict in enumerate(words):
        word = word_dict.get('word', '').strip()
        if not word:
            continue

        # NEVER break before a word starting with apostrophe or dash
        # (e.g., don't separate "qu'est-ce" and "'une" into different segments)
        force_continue = word[0] in ["'", "-", "–"]

        # Detect long pause between words (indicates change of thought/scene)
        long_pause_threshold = 1.5  # seconds - creates new segment
        has_long_pause = False
        if i > 0 and current_words:
            prev_word = words[i-1]
            gap = word_dict['start'] - prev_word['end']
            has_long_pause = gap >= long_pause_threshold

        # Initialize start time
        if current_start is None:
            current_start = word_dict['start']

        # Calculate current duration
        current_duration = word_dict['end'] - current_start

        # Calculate current character count (including this word)
        # Use a more conservative estimate: count actual text length
        current_text_length = sum(len(w['word'].strip()) + 1 for w in current_words) + len(word)

        # Check if we should break:
        # 1. Long pause detected (change of thought in natural speech)
        # 2. Duration exceeds max_duration
        # 3. Character count would exceed comfortable limit (80% of max to avoid cutting mid-sentence)
        # 4. Natural break (punctuation at end of word)
        should_break = False

        # Don't use character limit - it causes text loss
        # Instead, rely ONLY on natural breaks (punctuation, pauses, duration)
        # This ensures ALL words are included in the output

        if has_long_pause and current_words and not force_continue:
            should_break = True
        elif current_duration > max_duration and current_words and not force_continue:
            # Only break on duration if we have accumulated some words
            # AND the current word ends with punctuation (natural break point)
            if word[-1] in '.!?,:;':
                current_words.append(word_dict)
                should_break = True
            else:
                # No punctuation - continue accumulating to avoid cutting mid-sentence
                should_break = False
        elif word[-1] in '.!?:' and current_words and not force_continue:  # Strong punctuation = natural break
            current_words.append(word_dict)
            should_break = True

        if should_break and current_words:
            create_segment_from_words(current_words)
            current_words = []
            current_start = None
        else:
            if not should_break:  # Only add if we didn't already add it above
                current_words.append(word_dict)

    # Create final segment
    if current_words:
        create_segment_from_words(current_words)

    return segments


def remove_overlapping_segments(segments: List[SRTSegment]) -> List[SRTSegment]:
    """
    Intelligently merge overlapping segments to avoid cutting words

    When chunking audio with overlap (e.g., 30s chunks with 5s overlap),
    segments may overlap in time. Instead of removing them (which loses text),
    we detect text similarity and merge or extend segments intelligently.

    Args:
        segments: List of SRTSegment objects (must be sorted by start_time)

    Returns:
        List of non-overlapping SRTSegment objects
    """
    if not segments:
        return segments

    # STEP 1: Remove segments with invalid timestamps (start >= end)
    valid_segments = []
    invalid_count = 0
    for seg in segments:
        if seg.start_time >= seg.end_time:
            invalid_count += 1
            print(f"[SRT INVALID] Removed segment {seg.index} with invalid timestamps: {seg.start_time:.3f} >= {seg.end_time:.3f} (text: '{seg.text[:50]}...')")
        else:
            valid_segments.append(seg)

    if invalid_count > 0:
        print(f"[SRT INVALID] Removed {invalid_count} segments with invalid timestamps")

    if not valid_segments:
        return []

    # STEP 2: Merge overlapping segments
    cleaned = [valid_segments[0]]
    merged_count = 0

    for current in valid_segments[1:]:
        previous = cleaned[-1]

        # If current starts before previous ends -> overlap detected!
        if current.start_time < previous.end_time:
            # Check if texts are similar (same content in overlap zone)
            similarity = calculate_jaccard_trigram(previous.text, current.text)

            # Also check if current text starts with end of previous text (overlap repetition)
            # Normalize for comparison (lowercase, strip whitespace, remove punctuation)
            import string
            prev_text = previous.text.lower().replace('\n', ' ')
            curr_text = current.text.lower().replace('\n', ' ')
            # Remove punctuation for word matching
            prev_text = prev_text.translate(str.maketrans('', '', string.punctuation))
            curr_text = curr_text.translate(str.maketrans('', '', string.punctuation))
            prev_words = prev_text.split()
            curr_words = curr_text.split()

            # Check if there's significant word overlap at boundaries
            # Take last N words of previous and first N words of current
            overlap_check_len = min(5, len(prev_words), len(curr_words))
            has_boundary_overlap = False

            if overlap_check_len >= 2:
                prev_end = prev_words[-overlap_check_len:]
                curr_start = curr_words[:overlap_check_len]
                # Check if at least 2 words match
                matching_words = sum(1 for w in curr_start if w in prev_end)
                has_boundary_overlap = matching_words >= 2

            if similarity > 0.5 or has_boundary_overlap:  # Similar or has text repetition at boundary
                # MERGE: Extend the previous segment, taking the longer/newer text
                if len(current.text) > len(previous.text):
                    previous.text = current.text
                previous.end_time = max(previous.end_time, current.end_time)
                merged_count += 1
                reason = f"similarity: {similarity:.2f}" if similarity > 0.5 else "boundary overlap"
                print(f"[SRT OVERLAP] Merged overlapping segment at {current.start_time:.2f}s ({reason})")
            else:
                # ADJUST TIMING: Different content - start current right after previous
                gap = 0.1  # 100ms gap
                if current.start_time < previous.end_time:
                    current.start_time = previous.end_time + gap
                    print(f"[SRT OVERLAP] Adjusted segment start time to {current.start_time:.2f}s to avoid overlap")
                cleaned.append(current)
        else:
            # No overlap - add as is
            cleaned.append(current)

    if merged_count > 0:
        print(f"[SRT OVERLAP] Merged {merged_count} overlapping segments")

    return cleaned


def merge_srt_segments(srt_chunks: List[Dict]) -> str:
    """
    Merge multiple SRT contents with time offsets

    Args:
        srt_chunks: List of dicts with keys:
            - 'srt_content': SRT string
            - 'time_offset': Time offset in seconds (float)

    Returns:
        Merged SRT content as string
    """
    all_segments = []

    for chunk in srt_chunks:
        srt_content = chunk['srt_content']
        time_offset = chunk['time_offset']

        segments = parse_srt(srt_content)

        # Adjust timestamps with offset
        for segment in segments:
            all_segments.append(SRTSegment(
                index=0,  # Will be re-indexed later
                start_time=segment.start_time + time_offset,
                end_time=segment.end_time + time_offset,
                text=segment.text
            ))

    # Sort by start time
    all_segments.sort(key=lambda s: s.start_time)

    # Remove overlapping segments
    all_segments = remove_overlapping_segments(all_segments)

    # Re-index and format
    result_lines = []
    for i, segment in enumerate(all_segments, start=1):
        start_str = format_srt_timestamp(segment.start_time)
        end_str = format_srt_timestamp(segment.end_time)

        result_lines.append(f"{i}")
        result_lines.append(f"{start_str} --> {end_str}")
        result_lines.append(segment.text)
        result_lines.append("")  # Empty line between segments

    return '\n'.join(result_lines)


def calculate_jaccard_trigram(text1: str, text2: str) -> float:
    """
    Calculate Jaccard similarity using character trigrams
    Used to detect similar/duplicate segments

    Args:
        text1, text2: Texts to compare

    Returns:
        Similarity score between 0.0 and 1.0
    """
    def get_trigrams(text: str) -> set:
        text = text.lower().strip()
        if len(text) < 3:
            return set([text])
        return set(text[i:i+3] for i in range(len(text) - 2))

    trigrams1 = get_trigrams(text1)
    trigrams2 = get_trigrams(text2)

    if not trigrams1 and not trigrams2:
        return 1.0
    if not trigrams1 or not trigrams2:
        return 0.0

    intersection = trigrams1.intersection(trigrams2)
    union = trigrams1.union(trigrams2)

    return len(intersection) / len(union) if union else 0.0


def detect_tv_credits(text: str) -> bool:
    """
    Detect Quebec TV credit hallucinations
    Common patterns from Whisper training data

    Args:
        text: Subtitle text to check

    Returns:
        True if text looks like TV credits
    """
    normalized = text.lower().strip()

    # Common hallucination patterns
    credit_patterns = [
        r'sous[\s-]?titrage',
        r'soci[eé]t[eé]\s+radio[\s-]?canada',
        r'production',
        r'r[eé]alisation',
        r'^merci\s*[.!]?\s*$',
        r'^très\s+bien\s*[.!]?\s*$',
        r'^ok\s*[.!]?\s*$',
        r'^ah\s*[.!]?\s*$',
        r'^\[.*\]$',  # Just sound effects
        r'^♪.*♪$'     # Just music notes
    ]

    for pattern in credit_patterns:
        if re.search(pattern, normalized, re.IGNORECASE):
            return True

    return False


def clean_hallucinations(srt_content: str, time_merge_sec: float = 3.0, similarity_threshold: float = 0.9) -> str:
    """
    Clean hallucinations using non-destructive approach
    - Blocks TV credit hallucinations
    - Fuses similar adjacent segments
    - Handles temporal overlaps

    Args:
        srt_content: SRT content to clean
        time_merge_sec: Time window for merging similar segments (seconds)
        similarity_threshold: Jaccard similarity threshold (0.0 to 1.0)

    Returns:
        Cleaned SRT content
    """
    segments = parse_srt(srt_content)

    if not segments:
        return srt_content

    output = []

    for segment in segments:
        text = segment.text.strip()

        # Keep empty segments
        if not text:
            output.append(segment)
            continue

        # BLOCK TV credit hallucinations (Quebec TV training data artifact)
        if detect_tv_credits(text) and len(text) < 100:
            word_count = len(text.split())
            if word_count <= 6:
                print(f"[SRT] Blocked TV credit hallucination: \"{text[:50]}\"")
                continue

        # Check against last segment
        if output:
            last = output[-1]

            # 1A) TEMPORAL OVERLAP: segments that overlap in time with similar content
            has_temporal_overlap = segment.start_time < last.end_time

            if has_temporal_overlap:
                # Calculate similarity with lower threshold for overlaps (0.6 instead of 0.9)
                overlap_similarity = calculate_jaccard_trigram(text, last.text)

                if overlap_similarity >= 0.6:
                    # Keep the LONGER segment (more content)
                    if len(text) > len(last.text):
                        # New segment is longer → replace previous
                        last.text = text
                        last.end_time = max(last.end_time, segment.end_time)
                        print(f"[SRT] Overlap: kept longer version \"{text[:40]}...\"")
                    else:
                        # Old segment is longer → just extend time
                        last.end_time = max(last.end_time, segment.end_time)
                        print(f"[SRT] Overlap: extended time for \"{last.text[:40]}...\"")
                    continue

            # 1B) Temporal fusion: near-identical within time window
            is_near_in_time = (segment.start_time - last.end_time) <= time_merge_sec
            is_very_similar = calculate_jaccard_trigram(text, last.text) >= similarity_threshold

            if is_near_in_time and is_very_similar:
                # FUSE instead of delete → non-destructive
                last.end_time = max(last.end_time, segment.end_time)
                print(f"[SRT] Fused similar segment: \"{text[:40]}...\"")
                continue

        # Keep segment
        output.append(segment)

    print(f"[SRT] Cleaning: {len(segments)} → {len(output)} subtitles ({len(segments) - len(output)} fused/removed)")

    # Re-index and format
    result_lines = []
    for i, segment in enumerate(output, start=1):
        start_str = format_srt_timestamp(segment.start_time)
        end_str = format_srt_timestamp(segment.end_time)

        result_lines.append(f"{i}")
        result_lines.append(f"{start_str} --> {end_str}")
        result_lines.append(segment.text)
        result_lines.append("")

    return '\n'.join(result_lines)


def validate_srt_format(srt_content: str) -> bool:
    """
    Validate if string is valid SRT format

    Args:
        srt_content: Content to validate

    Returns:
        True if valid SRT format
    """
    if not srt_content or not srt_content.strip():
        return False

    # Check for SRT timestamp pattern
    pattern = r'\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}'
    return bool(re.search(pattern, srt_content))


def apply_speaker_segmentation(segments: List[SRTSegment], speaker_segments: List[Dict]) -> List[SRTSegment]:
    """
    Split SRT segments based on speaker changes (diarization)

    When a speaker changes in the middle of an SRT segment, split it into two segments.
    This ensures each subtitle corresponds to a single speaker for better readability.

    Args:
        segments: List of SRTSegment objects from Whisper
        speaker_segments: List of dicts from Pyannote with 'start', 'end', 'speaker' keys
            Example: [{"start": 0.5, "end": 3.2, "speaker": "SPEAKER_00"}, ...]

    Returns:
        List of SRTSegment objects with speaker-based segmentation applied
    """
    if not speaker_segments:
        print("[SPEAKER] No speaker segments provided, returning original segments")
        return segments

    print(f"[SPEAKER] Applying speaker segmentation to {len(segments)} segments")
    print(f"[SPEAKER] Using {len(speaker_segments)} speaker segments from diarization")

    # Helper function to find which speaker is active at a given time
    def get_speaker_at_time(time: float) -> Optional[str]:
        """Find the speaker active at the given timestamp"""
        for seg in speaker_segments:
            if seg['start'] <= time <= seg['end']:
                return seg['speaker']
        return None

    # Helper function to find speaker changes within a time range
    def find_speaker_changes(start_time: float, end_time: float) -> List[Tuple[float, str]]:
        """
        Find all speaker changes within a time range
        Returns list of (timestamp, speaker) tuples
        """
        changes = []
        current_speaker = None

        for seg in speaker_segments:
            # Skip if segment is completely outside our range
            if seg['end'] < start_time or seg['start'] > end_time:
                continue

            # Find the effective start time within our range
            effective_start = max(seg['start'], start_time)

            # If speaker changes, record it
            if seg['speaker'] != current_speaker:
                changes.append((effective_start, seg['speaker']))
                current_speaker = seg['speaker']

        return changes

    new_segments = []

    for segment in segments:
        # Find speaker changes within this segment
        speaker_changes = find_speaker_changes(segment.start_time, segment.end_time)

        if len(speaker_changes) <= 1:
            # No speaker change in this segment - keep as is
            new_segments.append(segment)
        else:
            # Multiple speakers in this segment - need to split!
            print(f"[SPEAKER] Splitting segment at {segment.start_time:.2f}s ({len(speaker_changes)} speakers)")

            # Parse the text into words to redistribute them
            words = segment.text.replace('\n', ' ').split()
            if not words:
                new_segments.append(segment)
                continue

            # Calculate approximate duration per word
            total_duration = segment.end_time - segment.start_time
            duration_per_word = total_duration / len(words)

            # Split text based on speaker changes
            current_start = segment.start_time
            word_index = 0

            for i, (change_time, speaker) in enumerate(speaker_changes):
                # Calculate how many words belong to this speaker
                if i < len(speaker_changes) - 1:
                    next_change_time = speaker_changes[i + 1][0]
                else:
                    next_change_time = segment.end_time

                segment_duration = next_change_time - change_time
                num_words = max(1, int(segment_duration / duration_per_word))

                # Get words for this sub-segment
                segment_words = words[word_index:word_index + num_words]
                if not segment_words:
                    continue

                # Create new segment
                new_segment = SRTSegment(
                    index=0,  # Will be re-indexed later
                    start_time=change_time,
                    end_time=min(next_change_time, segment.end_time),
                    text=' '.join(segment_words)
                )
                new_segments.append(new_segment)

                word_index += num_words

            # Add any remaining words to the last segment
            if word_index < len(words):
                if new_segments:
                    new_segments[-1].text += ' ' + ' '.join(words[word_index:])

    # Re-index segments
    for i, seg in enumerate(new_segments, start=1):
        seg.index = i

    print(f"[SPEAKER] Segmentation complete: {len(segments)} → {len(new_segments)} segments")
    return new_segments

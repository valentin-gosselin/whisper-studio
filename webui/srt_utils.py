"""
SRT (SubRip) utilities for subtitle processing
Ported from video_to_srt Node.js implementation to Python
"""
import re
from typing import List, Dict, Optional


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

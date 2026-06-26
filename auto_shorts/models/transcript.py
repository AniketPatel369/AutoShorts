"""
Auto Shorts — Data Models: Transcript

Represents the speech-to-text transcript output.
"""
from dataclasses import dataclass, field
from typing import List

@dataclass
class TranscriptWord:
    word: str
    start: float
    end: float

@dataclass
class TranscriptSegment:
    id: int
    start: float
    end: float
    text: str
    words: List[TranscriptWord] = field(default_factory=list)

@dataclass
class Transcript:
    text: str
    segments: List[TranscriptSegment] = field(default_factory=list)
    language: str = "en"

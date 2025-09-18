import re
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Trigger:
    key: str
    pattern: re.Pattern
    flag: str
    fail_fast: bool

# --- Regex patterns (expand conservatively over time) ---

# Off-label red flags: Trodelvy before chemo, early-stage, adjuvant/neoadjuvant, etc.
OFF_LABEL_PATTERNS = [
    r"\b(use|start|switch|move)\s+Trodelvy\s+(?:before|prior to)\s+(?:chemotherapy|chemo)\b",
    r"\bTrodelvy\b.*\b(adjuvant|neoadjuvant|early[- ]?stage)\b",
    r"\bcombine\b.*\bTrodelvy\b.*\b(off[- ]?label|not (?:in|on)[ -]?label)\b",
]

# Promotional hype red flags
PROMO_PATTERNS = [
    r"\bmiracle\b",
    r"\bgame[- ]changer\b",
    r"\bzero side effects\b",
]

# --- Compile triggers ---
TRIGGERS: List[Trigger] = [
    *[Trigger("off_label", re.compile(p, re.I), "OFF_LABEL_SUGGESTION", True) for p in OFF_LABEL_PATTERNS],
    *[Trigger("promo",     re.compile(p, re.I), "PROMOTIONAL_TONE",   False) for p in PROMO_PATTERNS],
]

def scan_fail_fast(text: str) -> Tuple[bool, List[str]]:
    """
    Scan text for deterministic rule violations.
    Returns (fail_fast: bool, flags: List[str]).
    """
    flags: List[str] = []
    ff = False
    for t in TRIGGERS:
        if t.pattern.search(text):
            flags.append(t.flag)
            if t.fail_fast:
                ff = True
    return ff, flags

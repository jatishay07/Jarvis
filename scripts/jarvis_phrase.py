#!/usr/bin/env python3
"""Stand-down phrase normalization and matching (no audio deps)."""
from __future__ import annotations

import difflib
import re


def normalize_phrase_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


def _apply_whisper_fixes(s: str) -> str:
    """Common tiny.en / faster-whisper glitches for stand-down phrases."""
    fixes = [
        (r"\bstandown\b", "stand down"),
        (r"\bstanding\s*down\b", "stand down"),
        (r"\bstan\s+down\b", "stand down"),
        (r"\bstand\s+own\b", "stand down"),
        (r"\bjarvus\b", "jarvis"),
        (r"\bjervis\b", "jarvis"),
        (r"\bgarvis\b", "jarvis"),
        (r"\bjarvice\b", "jarvis"),
    ]
    for pat, rep in fixes:
        s = re.sub(pat, rep, s, flags=re.I)
    return " ".join(s.split())


def _word_hit(word: str, tokens: list[str], ratio: float) -> bool:
    """Each config phrase word must appear as a token, substring, or close fuzzy hit."""
    if len(word) <= 2:
        return word in tokens
    blob = " ".join(tokens)
    if word in blob:
        return True
    for tok in tokens:
        if not tok:
            continue
        if tok == word:
            return True
        if len(word) >= 4 and word in tok:
            return True
        if len(tok) >= 4 and tok in word:
            return True
        if len(word) >= 3 and len(tok) >= 3:
            if difflib.SequenceMatcher(None, word, tok).ratio() >= ratio:
                return True
    return False


def phrase_matches(text: str, phrases: list[str], fuzzy_ratio: float = 0.72) -> bool:
    t = _apply_whisper_fixes(normalize_phrase_text(text))
    if not t:
        return False
    word_ratio = max(0.82, float(fuzzy_ratio))
    tokens = t.split()
    for p in phrases:
        pn = _apply_whisper_fixes(normalize_phrase_text(p))
        if not pn:
            continue
        if pn in t or t in pn:
            return True
        pw = pn.split()
        if len(pw) >= 2 and all(w in t for w in pw):
            return True
        if len(pw) >= 2 and all(_word_hit(w, tokens, word_ratio) for w in pw):
            return True
        if len(pn) >= 6 and len(t) >= 6:
            if difflib.SequenceMatcher(None, t, pn).ratio() >= fuzzy_ratio:
                return True
            if difflib.SequenceMatcher(None, pn, t).ratio() >= fuzzy_ratio:
                return True
    return False

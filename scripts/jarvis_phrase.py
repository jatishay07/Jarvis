#!/usr/bin/env python3
"""Stand-down phrase normalization and matching (no audio deps)."""
from __future__ import annotations

import re


def normalize_phrase_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


def phrase_matches(text: str, phrases: list[str]) -> bool:
    t = normalize_phrase_text(text)
    if not t:
        return False
    for p in phrases:
        pn = normalize_phrase_text(p)
        if not pn:
            continue
        if pn in t or t in pn:
            return True
        pw = pn.split()
        if len(pw) >= 2 and all(w in t for w in pw):
            return True
    return False

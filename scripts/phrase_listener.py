#!/usr/bin/env python3
"""
Stand-down phrase matching (no microphone).

Live mic + Whisper run in double_clap_listener.py. This module exists for
tests and imports: `from jarvis_phrase import phrase_matches`.
"""

from jarvis_phrase import phrase_matches

__all__ = ["phrase_matches"]

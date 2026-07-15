from rapidfuzz import fuzz

# Loose on purpose: this stage exists to catch obviously wrong/garbled/missing
# dialogue, not to penalize paraphrasing or Veo's arbitrary line-splitting.
SIMILARITY_THRESHOLD = 75


def match_dialogue(dialogue: list, segments: list) -> dict:
    """Compare a clip's expected dialogue against its Whisper transcript,
    both concatenated into one block (Veo doesn't respect line boundaries,
    so per-line comparison against per-segment transcript is brittle).

    dialogue: [{"character_id": str, "line": str}, ...] from scenario.json
    segments: [{"start": float, "end": float, "text": str}, ...] from transcribe_clip

    Returns {"expected_text", "transcribed_text", "similarity", "passed"}.
    """
    expected_text = " ".join(d["line"].strip() for d in dialogue).strip()
    transcribed_text = " ".join(s["text"].strip() for s in segments).strip()

    similarity = fuzz.token_sort_ratio(expected_text, transcribed_text)

    return {
        "expected_text": expected_text,
        "transcribed_text": transcribed_text,
        "similarity": round(similarity, 1),
        "passed": similarity >= SIMILARITY_THRESHOLD,
    }

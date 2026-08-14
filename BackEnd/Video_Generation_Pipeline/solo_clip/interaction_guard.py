# Dialogue whose *words* describe a physical gesture or interaction (nodding,
# pointing, "show me", referencing the other person's posture) empirically
# bleeds the other, off-frame character into solo clips at a much higher rate
# than purely verbal lines — the semantic content itself seems to pull Veo
# toward two-shot framing even when camera/backdrop instructions say
# otherwise. Detected via keyword match so the extra guard only fires on the
# lines that actually carry that risk, not on every line.
INTERACTION_KEYWORDS = [
    "nod",
    "shake your head",
    "shake his head",
    "shake her head",
    "shook",
    "show me",
    "show him",
    "show her",
    "point",
    "pointing",
    "pointed",
    "crossed your arms",
    "crossed his arms",
    "crossed her arms",
    "crossed arms",
    "your arms",
    "gesture",
    "wave",
    "look at me",
    "looking at",
    "touch",
    "thumbs up",
    "thumbs-up",
    "raise your hand",
    "raised his hand",
    "raised her hand",
]


def references_interaction(line_text: str) -> bool:
    lower = line_text.lower()
    return any(kw in lower for kw in INTERACTION_KEYWORDS)


def interaction_isolation_instruction(speaker_name: str, other_name: str) -> str:
    return (
        f"This line's words describe a physical action or gesture (e.g. "
        f"nodding, shaking the head, pointing, showing something) - but that "
        f"description is about something {other_name} might do, NOT something "
        f"to depict in this shot. This clip shows ONLY {speaker_name} speaking "
        f"these words. Do not attempt to illustrate, depict, or hint at the "
        f"described gesture actually happening - not by {speaker_name}, and "
        f"absolutely not by cutting to or including {other_name}. Keep the "
        f"frame exactly as specified above: {speaker_name} alone, in their "
        f"fixed pose, talking."
    )


def close_up_camera(speaker_name: str, backdrop_text: str) -> dict:
    """A physically tighter framing than the usual medium/waist-up shot, for
    interaction-flagged lines. The isolation *instruction* alone hasn't
    reliably stopped the other character from bleeding into frame on lines
    whose words describe a gesture/interaction - this is a geometric
    mitigation instead: crop tight enough that there is no room in frame for
    a second person regardless of what the model wants to depict."""
    return {
        "angle": (
            f"Extreme close-up on {speaker_name}'s face and shoulders only - "
            "tightly framed, filling most of the frame. Cropped tight enough "
            "that there is no physical room in frame for anyone else to "
            f"appear, even partially, even at the frame edge. {backdrop_text}"
        ),
        "movement": "Static.",
        "lens_effect": "Shallow depth of field, background softly blurred, neutral warm tone.",
    }

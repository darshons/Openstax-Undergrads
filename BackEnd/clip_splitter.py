"""
Split flat scene dialogue from the script generation pipeline into
per-clip chunks sized for the Veo extension pipeline (~8 s first clip,
~7 s extensions).

Usage
-----
    python clip_splitter.py input_script.json -o output_scenario.json
    python clip_splitter.py input_script.json --wps 2.0   # slower speaking rate
    python clip_splitter.py input_script.json --preview    # print clip breakdown only
"""

import argparse
import json
import re
from pathlib import Path

FIRST_CLIP_SECONDS = 8
EXTENSION_CLIP_SECONDS = 7
DEFAULT_WORDS_PER_SECOND = 2.5
ACTION_EFFECTIVE_WORDS = 2
OVERFLOW_FACTOR = 1.2


def count_spoken_words(text: str) -> int:
    """Count words that are actually spoken, ignoring [bracketed] stage directions."""
    cleaned = re.sub(r"\[.*?\]", "", text)
    cleaned = cleaned.replace("—", " ")
    return len(cleaned.split())


def _is_action_only(text: str) -> bool:
    return re.sub(r"\[.*?\]", "", text).strip() == ""


def _split_at_boundaries(text: str) -> list[str]:
    """Split text at sentence boundaries, falling back to clause boundaries."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    if len(parts) > 1:
        return [p for p in parts if p.strip()]
    parts = re.split(r"(?<=[,;])\s+|(?<=—)\s*", text)
    return [p for p in parts if p.strip()]


def _split_long_line(line: dict, max_words: int) -> list[dict]:
    """Break one dialogue entry into smaller entries that fit within max_words."""
    text = line["line"]
    char_id = line["character_id"]

    if _is_action_only(text):
        return [{"character_id": char_id, "line": text}]

    fragments = _split_at_boundaries(text)
    if len(fragments) <= 1:
        return [{"character_id": char_id, "line": text}]

    chunks: list[str] = []
    buf: list[str] = []
    buf_words = 0

    for frag in fragments:
        frag_words = len(frag.split())
        if buf_words + frag_words > max_words and buf:
            chunks.append(" ".join(buf))
            buf = [frag]
            buf_words = frag_words
        else:
            buf.append(frag)
            buf_words += frag_words

    if buf:
        chunks.append(" ".join(buf))

    return [{"character_id": char_id, "line": c} for c in chunks]


def split_dialogue_into_clips(
    dialogue: list[dict],
    wps: float = DEFAULT_WORDS_PER_SECOND,
) -> list[list[dict]]:
    """Partition a flat dialogue list into clip-sized groups.

    Returns a list of clips, where each clip is a list of dialogue entries
    (``{"character_id": ..., "line": ...}``).
    """
    if not dialogue:
        return [[]]

    first_budget = int(FIRST_CLIP_SECONDS * wps)
    ext_budget = int(EXTENSION_CLIP_SECONDS * wps)

    clips: list[list[dict]] = []
    cur: list[dict] = []
    cur_words = 0
    budget = first_budget

    def _flush():
        nonlocal cur, cur_words, budget
        if cur:
            clips.append(cur)
        cur = []
        cur_words = 0
        budget = ext_budget

    def _effective_words(text: str) -> int:
        if _is_action_only(text):
            return ACTION_EFFECTIVE_WORDS
        return count_spoken_words(text)

    soft_first = int(first_budget * OVERFLOW_FACTOR)
    soft_ext = int(ext_budget * OVERFLOW_FACTOR)
    soft = soft_first

    for entry in dialogue:
        clean = {"character_id": entry["character_id"], "line": entry["line"]}
        words = _effective_words(clean["line"])

        if cur_words + words <= soft:
            cur.append(clean)
            cur_words += words
            continue

        _flush()
        soft = soft_ext

        if words <= soft:
            cur.append(clean)
            cur_words = words
        else:
            for sub in _split_long_line(clean, ext_budget):
                sub_w = _effective_words(sub["line"])
                if cur_words + sub_w > soft:
                    _flush()
                cur.append(sub)
                cur_words += sub_w

    _flush()
    return clips if clips else [[]]


def _build_scene_camera(scene: dict) -> dict:
    """Extract a camera dict usable at the scene level."""
    if "camera" in scene:
        return scene["camera"]
    setting = scene.get("setting", {})
    if isinstance(setting, dict) and "camera" in setting:
        return setting["camera"]
    return {}


def add_clips_to_scene(scene: dict, wps: float) -> None:
    """Mutate *scene* in-place, adding a ``clips`` list."""
    dialogue = scene.get("audio", {}).get("dialogue", [])
    groups = split_dialogue_into_clips(dialogue, wps)
    camera = _build_scene_camera(scene)

    clips = []
    for i, group in enumerate(groups):
        clip: dict = {"clip_id": i + 1, "dialogue": group}
        if i == 0:
            clip["character_actions"] = scene.get("character_actions", "")
            if camera:
                clip["camera"] = camera
        clips.append(clip)

    scene["clips"] = clips


def convert(script: dict, wps: float) -> dict:
    """Return a copy of *script* with ``clips`` added to every scene."""
    out = json.loads(json.dumps(script))
    for scene in out.get("scenes", []):
        add_clips_to_scene(scene, wps)
    return out


def preview(script: dict, wps: float) -> None:
    for scene in script.get("scenes", []):
        dialogue = scene.get("audio", {}).get("dialogue", [])
        groups = split_dialogue_into_clips(dialogue, wps)
        print(f"\n{'=' * 60}")
        clip_label = "clip" if len(groups) == 1 else "clips"
        print(f"SCENE {scene['scene_id']}  ({len(groups)} {clip_label})")
        print(f"{'=' * 60}")
        for i, group in enumerate(groups):
            is_first = i == 0
            dur = FIRST_CLIP_SECONDS if is_first else EXTENSION_CLIP_SECONDS
            total = sum(count_spoken_words(d["line"]) for d in group)
            est = total / wps if wps else 0
            tag = "first, 8 s" if is_first else "ext, ~7 s"
            print(f"\n  Clip {i + 1} [{tag}]  {total} words  ~{est:.1f} s spoken")
            for d in group:
                name = d["character_id"]
                print(f"    {name}: {d['line']}")


def main():
    ap = argparse.ArgumentParser(description="Split script dialogue into Veo-sized clips.")
    ap.add_argument("input", help="Script-generation JSON file.")
    ap.add_argument("-o", "--output", help="Output path (default: <input>_with_clips.json).")
    ap.add_argument("--wps", type=float, default=DEFAULT_WORDS_PER_SECOND,
                    help=f"Words per second speaking rate (default {DEFAULT_WORDS_PER_SECOND}).")
    ap.add_argument("--preview", action="store_true",
                    help="Print clip breakdown without writing a file.")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        script = json.load(f)

    if args.preview:
        preview(script, args.wps)
        return

    result = convert(script, args.wps)

    out_path = args.output
    if not out_path:
        p = Path(args.input)
        out_path = str(p.with_stem(p.stem + "_with_clips"))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Wrote {out_path}")
    for scene in result["scenes"]:
        n = len(scene["clips"])
        words = sum(
            count_spoken_words(d["line"])
            for clip in scene["clips"]
            for d in clip["dialogue"]
        )
        print(f"  Scene {scene['scene_id']}: {n} clip{'s' if n != 1 else ''}, {words} spoken words")


if __name__ == "__main__":
    main()

from pathlib import Path

BASE_TASK_PROMPT = """\
You are an expert instructional designer and screenplay writer creating an interactive branching scenario based on one or more provided textbook chapters.

You will be given one file in Markdown format containing the textbook content. Your task is to identify a single core concept, principle, skill, procedure, or decision-making challenge from the material that is well-suited to being taught through a realistic scenario.

Generate a single, branching scenario with at most 3 decision points. The decision points should occur at different stages of the same scenario. For each decision point, provide a few answer options, but continue the script only along the correct option. Do not generate separate branches or alternate storylines for incorrect options.

The scenario should depict a realistic situation in which a learner must observe information, interpret context, and make a decision. You are free to invent character names, dialogue, settings, and narrative details, but every decision point, answer choice, consequence, and learning outcome must be grounded in the concepts, procedures, guidelines, or principles presented in the provided chapters. Do not introduce substantive content that is not supported by the source material or would require outside knowledge.

Scenario Constraints:
• Total scenario duration must be under 300 seconds
• Narrative scene (setup): 20-30 seconds
• Consequence scene (incorrect answer branches): 15-20 seconds
• Resolution scene (correct answers): 15-20 seconds
• Scenes follow a consistent format: narrative scene → consequence and resolution scenes → next narrative scene → etc.
• No more than 2-3 characters should appear on screen at any time
• All scenes should take place in the same setting unless a location change is necessary for the narrative
• The tone should remain professional, realistic, and educational throughout. Avoid melodrama, excessive tension, or entertainment-focused storytelling. The scenario should feel like an authentic training simulation rather than a film or television scene.
• Each character's dialogue should be no more than 2-3 sentences per turn.

Animation and Visual Style Constraints:
• Characters should follow a 2D semi-flat limited-animation style with dynamic but constrained movement
• Characters may express emotion and react through head turns, nods, hand gestures, subtle posture shifts, and facial expressions
• Avoid highly realistic animation features such as detailed lip sync, complex physics simulations, extensive locomotion, or photorealistic rendering
• Mouth movement should suggest speech without matching every phoneme
• The visual style must remain consistent across all generated clips
• Character appearances must be described with sufficient specificity to ensure visual consistency across scenes. Include skin tone, hair color and style, height and build, clothing, and any distinguishing features. These descriptions may be reused verbatim in future video-generation prompts.

Decision Point Constraints:
• Incorrect-answer consequence scenes should reveal the consequences of the misconception naturally through the narrative, without explicitly stating that the learner was wrong
• Consequence scenes should return the learner to the decision point so they can try again with that choice eliminated

Dialogue should sound natural and conversational rather than textbook-like.

The narrative scene should establish the situation clearly and end at a natural moment of uncertainty requiring a decision. The consequence scene should feel like a realistic continuation of events rather than a punishment. The resolution scene should provide a satisfying outcome that reinforces the underlying concept without becoming overly didactic.

Per-Scene Renderer Selection:
Two different renderers produce the final video, and you must choose one for every scene by setting that scene's "render_mode" field. Pick per scene based on what the scene actually has to show — a scenario will normally mix both.

• "scenario" — a character animation renderer. Choose it when the teaching happens between people: dialogue, an interview or handoff, a clinical interaction, an emotional beat, body language, a decision being made face to face. This renderer is good at characters, expression, and setting, and cannot render legible text, equations, numbers, or diagrams.
• "manim" — a programmatic graphics renderer. Choose it when the teaching happens on the screen rather than between people: equations and derivations, labelled diagrams, anatomical or molecular structures, data, graphs, timelines, step-by-step processes, before/after comparisons, anything requiring precise numbers or on-screen labels. This renderer draws crisp text and geometry and has no characters in it.

Rules for choosing:
• Decide from the scene's own content, not from the scenario as a whole.
• If a scene's point rests on a quantity, a label, a structure, or a process diagram, use "manim" even when characters could be present — the character renderer cannot draw readable text.
• If a scene's point rests on what a person says, decides, or feels, use "scenario".
• When a scene would genuinely need both, split it into two consecutive scenes with different render_mode values rather than forcing one renderer to do both.
• A "manim" scene must not depend on character_actions or on-screen characters; carry its meaning in narration plus the graphic. Its dialogue becomes voice-over narration.
• Every scene must have a render_mode of exactly "scenario" or "manim". Never leave it blank."""

OUTPUT_FORMAT_INSTRUCTION = (
    "Output your response strictly as a JSON object following the exact "
    "structure in the provided JSON file, with no additional text before or after"
)

_RULES_PATH = (
    Path(__file__).resolve().parent / "Prompt_Rules" / "script-generation-rules-llm.md"
)


def build_system_prompt() -> str:
    rules = _RULES_PATH.read_text(encoding="utf-8")
    return f"{BASE_TASK_PROMPT}\n\n{rules}\n\n{OUTPUT_FORMAT_INSTRUCTION}"

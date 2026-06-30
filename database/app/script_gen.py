import json
import os

from anthropic import Anthropic
from google import genai as google_genai

_anthropic_client = None
_gemini_client = None


def _get_anthropic() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _anthropic_client


def _get_gemini() -> google_genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = google_genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    return _gemini_client


_SYSTEM = """You are a clinical nursing educator building interactive branching video scenarios
for nursing students. Given textbook content and a scenario description, generate a structured
JSON script for a choose-your-own-adventure clinical scenario.

Return ONLY valid JSON (no markdown code fences) matching this exact schema:
{
  "title": "string",
  "nodes": [
    {
      "id": "scene_N",
      "scene_number": N,
      "title": "string",
      "script": "string — narration or dialogue for this scene",
      "video_prompt": "string — short visual description for video generation",
      "is_endpoint": false,
      "choices": [
        {
          "id": "choice_Na",
          "text": "string — the MCQ choice shown to the student",
          "destination_scene_id": "scene_M",
          "is_misconception": false,
          "feedback": "string — brief feedback shown after selecting"
        }
      ]
    }
  ]
}

Requirements:
- 3 to 6 scenes total
- Each non-endpoint node must have 2 to 4 MCQ choices
- At least one misconception branch per branching node
- Scripts must be clinically accurate and grounded in the provided textbook material
- Endpoint nodes have an empty choices array and is_endpoint set to true
"""


def _parse_raw(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]
    return json.loads(raw.strip())


def generate_script(description: str, markdown_content: str, model: str = "anthropic") -> dict:
    user_msg = (
        f"Textbook Content:\n{markdown_content[:8000]}\n\n"
        f"Scenario Description:\n{description}\n\n"
        "Generate the complete branching scenario script."
    )

    if model == "gemini":
        resp = _get_gemini().models.generate_content(
            model="gemini-2.0-flash",
            contents=f"{_SYSTEM}\n\n{user_msg}",
        )
        return _parse_raw(resp.text)

    # default: anthropic
    resp = _get_anthropic().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    return _parse_raw(resp.content[0].text)

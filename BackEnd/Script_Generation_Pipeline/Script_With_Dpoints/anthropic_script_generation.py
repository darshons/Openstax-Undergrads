from anthropic import Anthropic
import os
from dotenv import load_dotenv
from pathlib import Path
import json
import time
from Script_Generation_Pipeline.prompt_assembly import build_system_prompt


def setup_anthropic_client():
    env_path = Path(__file__).resolve().parents[2] / "backend.env"
    load_dotenv(env_path)
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return client

def generate_script_with_decision_points(markdown_file_path, user_query) -> tuple[dict, list]:

    client = setup_anthropic_client()

    system_prompt = build_system_prompt()

    MODEL = "claude-sonnet-4-6"

    model_info = client.models.retrieve(MODEL)
    TOKEN_LIMIT = model_info.max_tokens or 8096

    uploaded_md = client.beta.files.upload(file=("textbook_content", open(markdown_file_path, "rb"), "text/plain"))

    # JSON File Template
    PROJECT_DIR = Path(__file__).resolve().parents[1]

    json_file_path = PROJECT_DIR / "JSON_Templates" / "script_gen_with_dpoints.json"

    uploaded_json = client.beta.files.upload(file=("script_gen_with_decision_points", open(json_file_path, "rb"), "text/plain"))

    # Make the request
    user_query = user_query.strip()

    content = [
        {"type": "document", "source": {"type": "file", "file_id": uploaded_md.id}, "title": "Textbook Chapter"}
    ]

    content.append({"type": "document", "source": {"type": "file", "file_id": uploaded_json.id}, "title": "JSON Script Template"})

    content.append({"type": "text", "text": user_query})

    # Create a message with the uploaded file
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=TOKEN_LIMIT,
        betas=["files-api-2025-04-14"],
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    ) as stream:
        response = stream.get_final_message()

    raw = response.content[0].text
    # Extract JSON robustly regardless of code fence formatting
    start = raw.find('{')
    end = raw.rfind('}') + 1
    output_json = json.loads(raw[start:end])

    return output_json, [uploaded_md.id, uploaded_json.id]


def delete_uploaded_file(file_id):
    client = setup_anthropic_client()

    for attempt in range(3):
        try:
            client.beta.files.delete(file_id)
            return
        except Exception as e:
            if attempt == 2:
                print(f"Failed to delete {file_id}: {e}")
            else:
                time.sleep(2 ** attempt)

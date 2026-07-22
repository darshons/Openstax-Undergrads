from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from pathlib import Path
import json
import time
from Script_Generation_Pipeline.prompt_assembly import build_system_prompt

def setup_gemini_client():
    env_path = Path(__file__).resolve().parents[2] / "backend.env"
    load_dotenv(env_path)
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return client

def generate_script_with_decision_points(markdown_file_path, user_query) -> tuple[dict, list[str]]:
    client = setup_gemini_client()

    system_prompt = build_system_prompt()

    MODEL = "gemini-3.1-pro-preview"

    TOKEN_LIMIT = client.models.get(model=MODEL).output_token_limit

    # Configure the system instruction
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        max_output_tokens=TOKEN_LIMIT,
    )

    uploaded_md_file = client.files.upload(file=markdown_file_path, config=types.UploadFileConfig(display_name="textbook_content", mime_type="text/markdown"))

    # JSON File Template[
    PROJECT_DIR = Path(__file__).resolve().parents[1]
    
    json_file_path = PROJECT_DIR / "JSON_Templates" / "script_gen_with_dpoints.json"

    uploaded_json = client.files.upload(file=json_file_path, config=types.UploadFileConfig(display_name="script_gen_with_decision_points", mime_type="application/json"))

    # Make the request
    user_query = user_query.strip()

    response = client.models.generate_content(
        model=MODEL,
        contents=[uploaded_md_file, uploaded_json, user_query],
        config=config
    )   
    
    output_json = json.loads(response.text)
    
    return output_json, [uploaded_md_file.name, uploaded_json.name]

def delete_uploaded_file(file_name):
    client = setup_gemini_client()

    for attempt in range(3):
        try:
            client.files.delete(file_name)
            print(f"Successfully deleted {file_name}")
            return
        except Exception as e:
            if attempt == 2:
                print(f"Failed to delete {file_name}: {e}")
            else:
                time.sleep(2 ** attempt)

    
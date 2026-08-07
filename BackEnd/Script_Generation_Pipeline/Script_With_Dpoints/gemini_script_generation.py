from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from pathlib import Path
import json
import asyncio
from Script_Generation_Pipeline.prompt_assembly import build_system_prompt


# This function sets up the Gemini client using the API key from environment variables.
def setup_gemini_client():
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return client


# This function generates a script with decision points based on the provided Markdown file and user query. It returns the generated JSON script and a list of uploaded file names.
def generate_script_with_decision_points_gemini(
    markdown_file_path, user_query, num_decision_points: int = 2
) -> tuple[dict | None, list[str | None]]:
    client = setup_gemini_client()

    system_prompt = build_system_prompt(num_decision_points)

    MODEL = "gemini-3.1-pro-preview"

    TOKEN_LIMIT = client.models.get(model=MODEL).output_token_limit

    # Configure the system instruction
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        max_output_tokens=TOKEN_LIMIT,
    )

    uploaded_md_file = client.files.upload(
        file=markdown_file_path,
        config=types.UploadFileConfig(
            display_name="textbook_content", mime_type="text/markdown"
        ),
    )

    # JSON File Template[
    PROJECT_DIR = Path(__file__).resolve().parents[1]

    json_file_path = PROJECT_DIR / "_JSON_Templates" / "script_gen_with_dpoints.json"

    uploaded_json = client.files.upload(
        file=json_file_path,
        config=types.UploadFileConfig(
            display_name="script_gen_with_decision_points", mime_type="application/json"
        ),
    )

    # Make the request
    user_query = user_query.strip()

    response = client.models.generate_content(
        model=MODEL,
        contents=[uploaded_md_file, uploaded_json, user_query],
        config=config,
    )

    output_json = None

    if not response or not response.text:
        return output_json, [uploaded_md_file.name, uploaded_json.name]


    output_json = json.loads(response.text)

    return output_json, [uploaded_md_file.name, uploaded_json.name]


# This function deletes all uploaded files from the Gemini client and is designed to be called asynchronously.
async def delete_uploaded_files_gemini(file_names: list):
    client = setup_gemini_client()
    await asyncio.gather(
        *(delete_uploaded_file(client, file_name) for file_name in file_names)
    )


async def delete_uploaded_file(client, file_name: str):
    for attempt in range(3):
        try:
            await client.aio.files.delete(name=file_name)
            print(f"Successfully deleted {file_name}")
            return
        except Exception as e:
            if attempt == 2:
                print(f"Failed to delete {file_name}: {e}")
            else:
                await asyncio.sleep(
                    2**attempt
                )  # non-blocking # sleep for 1, 2, then 4 seconds before retrying

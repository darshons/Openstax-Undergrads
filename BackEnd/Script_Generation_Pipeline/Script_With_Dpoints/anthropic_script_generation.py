from anthropic import Anthropic, AsyncAnthropic
import os
from pathlib import Path
import json
import time
from Script_Generation_Pipeline.prompt_assembly import build_system_prompt
import asyncio
from anthropic.types.beta import BetaTextBlock


def setup_anthropic_client():
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return client


def setup_async_anthropic_client():
    client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return client


def generate_script_with_decision_points_anthropic(
    markdown_file_path, user_query
) -> tuple[dict | None, list[str | None]]:

    client = setup_anthropic_client()

    system_prompt = build_system_prompt()

    MODEL = "claude-sonnet-4-6"

    TOKEN_LIMIT = client.models.retrieve(MODEL).max_tokens or 8096

    uploaded_md = client.beta.files.upload(
        file=("textbook_content", open(markdown_file_path, "rb"), "text/plain")
    )

    # JSON File Template
    PROJECT_DIR = Path(__file__).resolve().parents[1]

    json_file_path = PROJECT_DIR / "_JSON_Templates" / "script_gen_with_dpoints.json"

    uploaded_json = client.beta.files.upload(
        file=(
            "script_gen_with_decision_points",
            open(json_file_path, "rb"),
            "text/plain",
        )
    )

    # Make the request
    user_query = user_query.strip()

    content = [
        {
            "type": "document",
            "source": {"type": "file", "file_id": uploaded_md.id},
            "title": "Textbook Chapter",
        }
    ]

    content.append(
        {
            "type": "document",
            "source": {"type": "file", "file_id": uploaded_json.id},
            "title": "JSON Script Template",
        }
    )

    content.append({"type": "text", "text": user_query})

    # Create a message with the uploaded file
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=TOKEN_LIMIT,
        betas=[
            "files-api-2025-04-14"
        ],  # Use the beta version of the files API to access the uploaded file
        system=system_prompt,  # System prompt to guide the model's behavior
        messages=[{"role": "user", "content": content}],
    ) as stream:
        response = stream.get_final_message()

    output_json = None

    if not response or not response.content or not response.content[0]:
        return output_json, [uploaded_md.id, uploaded_json.id]

    raw = response.content[0]

    assert isinstance(
        raw, BetaTextBlock
    ), f"Expected a BetaTextBlock, got {type(raw).__name__}"

    # Extract JSON robustly
    raw_text = raw.text
    start = raw_text.find("{")
    end = raw_text.rfind("}") + 1
    output_json = json.loads(raw_text[start:end])

    return output_json, [uploaded_md.id, uploaded_json.id]


async def delete_uploaded_files_anthropic(file_ids: list):
    client = setup_async_anthropic_client()
    await asyncio.gather(
        *(delete_uploaded_file(client, file_id) for file_id in file_ids)
    )


async def delete_uploaded_file(client, file_id: str):
    for attempt in range(3):
        try:
            await client.beta.files.delete(file_id)
            print(f"Successfully deleted {file_id}")
            break
        except Exception as e:
            if attempt == 2:
                print(f"Failed to delete {file_id}: {e}")
            else:
                await asyncio.sleep(
                    2**attempt
                )  # non-blocking # sleep for 1, 2, then 4 seconds before retrying

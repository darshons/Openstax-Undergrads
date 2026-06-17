from anthropic import Anthropic, AsyncAnthropic
import os
from dotenv import load_dotenv
from pathlib import Path
import json
import asyncio


def setup_anthropic_client():
    env_path = Path(__file__).resolve().parents[2] / "backend.env"
    load_dotenv(env_path)
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return client

def setup_async_anthropic_client():
    env_path = Path(__file__).resolve().parents[2] / "backend.env"
    load_dotenv(env_path)
    client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return client

def generate_script_with_decision_points(markdown_file_path, user_query) -> tuple[dict, list]:

    client = setup_anthropic_client()

    system_prompt = """
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
    • Exactly one answer choice must be correct
    • Include at least two incorrect answer choices
    • Each incorrect answer should represent a distinct misunderstanding, misconception, or reasoning error related to the source material
    • Incorrect-answer consequence scenes should reveal the consequences of the misconception naturally through the narrative, without explicitly stating that the learner was wrong
    • Consequence scenes should return the learner to the decision point so they can try again with that choice eliminated

    Dialogue should sound natural and conversational rather than textbook-like.

    The narrative scene should establish the situation clearly and end at a natural moment of uncertainty requiring a decision. The consequence scene should feel like a realistic continuation of events rather than a punishment. The resolution scene should provide a satisfying outcome that reinforces the underlying concept without becoming overly didactic.

    Output your response strictly as a JSON object following the exact structure in the provided JSON file, with no additional text before or after
    """

    MODEL = "claude-sonnet-4-6"

    TOKEN_LIMIT = client.models.retrieve(MODEL).max_tokens
    
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
        betas=["files-api-2025-04-14"], # Use the beta version of the files API to access the uploaded file
        system=system_prompt, # System prompt to guide the model's behavior
        messages=[{"role": "user", "content": content}],
    ) as stream:
        response = stream.get_final_message()
    
    output_json = response.content[0].text
    output_json = output_json.strip('```json').strip('```')
    output_json = output_json.strip() 
    
    output_json = json.loads(output_json)
    
    return output_json, [uploaded_md.id, uploaded_json.id]
    
async def delete_uploaded_files(file_ids: list):
    client = setup_async_anthropic_client()
    await asyncio.gather(*(delete_uploaded_file(client, file_id) for file_id in file_ids))
    

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
                await asyncio.sleep(2 ** attempt)  # non-blocking # sleep for 1, 2, then 4 seconds before retrying
from anthropic import Anthropic
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(env_path)

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

system_prompt = """
You are an expert instructional designer and screenplay writer, creating an interactive scenario based on one or more provided textbook chapters.

You will be given one or more chapter files in Markdown format. Your task is to identify a single core concept, principle, skill, procedure, or decision-making challenge from the material that is well-suited to being taught through a realistic scenario.

Generate a single scenario script with at most 6 scenes (including narrative and outcome scenes).

The scenario should depict a realistic situation in which a learner must observe information, interpret context, and understand how the situation unfolds. You are free to invent character names, dialogue, settings, and narrative details, but every event, action, consequence, and learning outcome must be grounded in the concepts, procedures, guidelines, or principles presented in the provided chapters. Do not introduce substantive content that is not supported by the source material.

Scenario Constraints:
• Total scenario duration must be under 300 seconds
• Narrative scene (setup): 20-30 seconds
• Outcome scene (setup resolution): 15-20 seconds
• Scenes follow a consistent format: narrative scene → outcome scene → next narrative scene → etc.
• All scenes should take place in the same setting unless a location change is necessary for the narrative
• Each character's dialogue should be no more than 2-3 sentences per turn.
• The tone should remain professional, realistic, and educational throughout. 
• Avoid melodrama, excessive tension, or entertainment-focused storytelling. The scenario should feel like an authentic training simulation rather than a film or television scene.

Animation and Visual Style Constraints:
• Characters should follow a 2D semi-flat limited-animation style with dynamic but constrained movement
• Characters may express emotion and react through head turns, nods, hand gestures, subtle posture shifts, and facial expressions
• Avoid highly realistic animation features such as detailed lip sync, complex physics simulations, extensive locomotion, or photorealistic rendering
• Mouth movement should suggest speech without matching every phoneme
• The visual style must remain consistent across all generated clips
• Character appearances must be described with sufficient specificity to ensure visual consistency across scenes. Include skin tone, hair color and style, height and build, clothing, and any distinguishing features. These descriptions may be reused verbatim in future video-generation prompts.

Narrative Constraints:
• Events and outcomes should illustrate the core concept, principle, skill, procedure, or decision-making challenge identified from the source material
• Consequences should emerge naturally from the situation and remain faithful to the concepts presented in the chapters
• Dialogue should sound natural and conversational rather than textbook-like
• The narrative scene should establish the situation clearly and end at a natural moment of uncertainty, challenge, or transition. The outcome scene should feel like a realistic continuation of events. The resolution scene should provide a satisfying outcome that reinforces the underlying concept without becoming overly didactic.

Output your response strictly as a JSON object following the exact structure in the provided JSON file, with no additional text before or after
"""

MODEL = "claude-sonnet-4-6"

TOKEN_LIMIT = client.models.retrieve(MODEL).max_tokens

# MARKDOWN
md_file_paths = ["/Users/youssef/Desktop/work/Openstax-Undergrads/textbook-content/psychology-chapter-4.2.md", 
                 "/Users/youssef/Desktop/work/Openstax-Undergrads/textbook-content/psychology-chapter-4.3.md",
                 "/Users/youssef/Desktop/work/Openstax-Undergrads/textbook-content/psychology-chapter-4.4.md"]

md_file_names = ["psychology-chapter-4.2", "psychology-chapter-4.3", "psychology-chapter-4.4"]

uploaded_md_files_ids = []

for md_file_path, md_file_name in zip(md_file_paths, md_file_names):
    uploaded_md = client.beta.files.upload(file=(md_file_name, open(md_file_path, "rb"), "text/plain"))
    uploaded_md_files_ids.append(uploaded_md.id)

# JSON File Template
json_file_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/Script_Generation_Pipeline/JSON_Templates/script_gen_without_dpoints.json"

uploaded_json = client.beta.files.upload(file=("script_gen_without_dpoints", open(json_file_path, "rb"), "text/plain"))

# Make the request
user_query = """
Generate a scenario script about a psychiatrist helping a patient diagnose and manage a sleep problem or disorder. The scenario should include discussion of the different stages of sleep and how they can affect a person's sleep quality, symptoms, and overall well-being.
"""

content = [
    {"type": "document", "source": {"type": "file", "file_id": fid}, "title": "Textbook Chapter"}
    for fid in uploaded_md_files_ids
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

# Write the response to a JSON file
output_json_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/Script_Generation_Pipeline/Script_Outputs/output_script_without_decision_points_anthropic.json"
with open(output_json_path, "w") as f:
    output_json = response.content[0].text
    output_json = output_json.strip('```json').strip('```')
    output_json = output_json.strip()
    f.write(output_json)

print("Scenario script generated and saved to:", output_json_path)

# print("\n\n")

# # List all uploaded files
# files = client.beta.files.list()
# for f in files:
#     print(f.id, f.filename)

# client.beta.files.delete(file_id)

for file_id in uploaded_md_files_ids:
    client.beta.files.delete(file_id)
    
client.beta.files.delete(uploaded_json.id)
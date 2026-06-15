from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parents[2] / "backend.env"
load_dotenv(env_path)

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

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

MODEL = "gemini-3.1-pro-preview"

TOKEN_LIMIT = client.models.get(model=MODEL).output_token_limit

# Configure the system instruction
config = types.GenerateContentConfig(
    system_instruction=system_prompt,
    max_output_tokens=TOKEN_LIMIT,
)

# MARKDOWN
md_file_paths = ["/Users/youssef/Desktop/work/Openstax-Undergrads/textbook-content/psychology-chapter-4.2.md", 
                 "/Users/youssef/Desktop/work/Openstax-Undergrads/textbook-content/psychology-chapter-4.3.md",
                 "/Users/youssef/Desktop/work/Openstax-Undergrads/textbook-content/psychology-chapter-4.4.md"]

md_file_names = ["psychology-chapter-4.2", "psychology-chapter-4.3", "psychology-chapter-4.4"]

uploaded_md_files = []

for md_file_path, md_file_name in zip(md_file_paths, md_file_names):
    uploaded_md = client.files.upload(file=md_file_path, config=types.UploadFileConfig(display_name=md_file_name, mime_type="text/markdown")) # switch to text/pdf for PDF files
    uploaded_md_files.append(uploaded_md)

# uploaded_md = client.files.get(name="files/brjip1ecdqph")


# JSON File Template
json_file_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/Script_Generation_Pipeline/JSON_Templates/script_gen_without_dpoints.json"

uploaded_json = client.files.upload(file=json_file_path, config=types.UploadFileConfig(display_name="script_gen_without_decision_points", mime_type="application/json"))

# Make the request
user_query = """
Generate a branching scenario script about a psychiatrist helping a patient diagnose and manage a sleep problem or disorder. The scenario should include discussion of the different stages of sleep and how they can affect a person's sleep quality, symptoms, and overall well-being.
"""

response = client.models.generate_content(
    model=MODEL,
    contents=[user_query, *uploaded_md_files, uploaded_json],
    config=config
)

# Write the response to a JSON file
output_json_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/Script_Generation_Pipeline/Script_Outputs/output_script_without_decision_points_gemini.json"
with open(output_json_path, "w") as f:
    f.write(response.text)

print("Scenario script generated and saved to:", output_json_path)

# print("\n\n")

# for file in client.files.list():
#     print(f"Display Name: {file.display_name}")
#     print(f"  File ID: {file.name}") # Will look like 'files/abc123xyz...'
#     print(f"  Mime Type:    {file.mime_type}")
#     print(f"  URI:          {file.uri}")
    
    
# client.files.delete(name=uploaded_md.name)
for file_id in uploaded_md_files:
    client.files.delete(name=file_id.name)

client.files.delete(name=uploaded_json.name)
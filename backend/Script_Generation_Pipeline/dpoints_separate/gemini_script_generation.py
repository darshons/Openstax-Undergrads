from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parents[2] / "backend.env"
load_dotenv(env_path)

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

system_prompt = """
You are an expert instructional designer and screenplay writer.

You will be provided with one or more textbook chapters in Markdown format, along with a JSON file containing a previously generated linear scenario script derived from those chapters.

The JSON file represents the complete linear scenario and should serve as the primary source for its characters, setting, dialogue, visual descriptions, scene structure, pacing, and narrative flow.

Your task is to convert the linear scenario into a single interactive branching scenario while preserving the original scenario as closely as possible. The original characters, setting, sequence of events, dialogue style, pacing, learning objectives, and overall narrative should remain unchanged whenever possible. Do not redesign the scenario or introduce a different situation. Instead, identify a Narrative scene within the existing script where a learner-facing decision can be inserted.

All decisions, answer choices, consequences, outcomes, and learning points must be fully grounded in the concepts, procedures, guidelines, principles, and reasoning presented in the provided chapters. Do not introduce substantive content that is not supported by the source material.

The final scenario must contain at most three decision points and follow this repeatable structure:
1. Narrative Scene (setup/introduction)
2. Decision Point (question)
3. Outcome Scene (correct branch)
4. Consequence Scene A (incorrect branch)
5. Consequence Scene B (incorrect branch)

The Narrative Scene should remain largely identical to the original setup and should conclude at a natural moment of uncertainty, judgment, action selection, interpretation, or transition. Whenever possible, the original Outcome Scene should become the correct branch.

The decision point should assess understanding of the core concept being taught. Include at least three answer choices. Exactly one answer choice must be correct, and at least two answer choices must be incorrect.

Each incorrect answer choice should represent a distinct and realistic misconception, misunderstanding, procedural error, reasoning error, or misapplication of a principle from the source material. Distractors should be plausible and appealing to learners who have not fully mastered the concept. Avoid answer choices that are obviously incorrect, humorous, careless, or exaggerated.

The Outcome Scene should represent the consequences of selecting the correct answer. It should closely follow the original scenario's intended resolution, demonstrate successful application of the relevant concept, procedure, guideline, or principle, and reinforce the learning objective through realistic consequences rather than explicit instruction.

Create one Consequence Scene for each incorrect answer choice. Each consequence scene should show the selected action being carried out, demonstrate realistic consequences that arise from the underlying misconception, remain faithful to the source material, and maintain a professional and educational tone. The limitations of the chosen approach should become apparent through the narrative itself.

Throughout the scenario, preserve the original characters, setting, visual descriptions, dialogue style, scene structure, pacing, and educational intent unless a modification is necessary to support the decision point.

Total scenario duration must be under 300 seconds.

The completed branching scenario should feel as though the decision point and resulting outcomes were naturally embedded within the original script rather than added afterward.

Output your response STRICTLY as a JSON object following the EXACT structure in the provided JSON Template file, with no additional text before or after. Do not deviate from the specified JSON format, and ensure that all required fields are included and properly filled out. The JSON should be fully compliant with the template, and any missing or extra fields will be considered an error.
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
json_template_file_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/Script_Generation_Pipeline/JSON_Templates/dpoints_separate.json"

uploaded_json_template = client.files.upload(file=json_template_file_path, config=types.UploadFileConfig(display_name="script_gen_decision_points_separate", mime_type="application/json"))

# JSON Linear Script
json_linear_script_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/Script_Generation_Pipeline/Script_Outputs/output_script_without_decision_points_gemini.json"

uploaded_json_linear_script = client.files.upload(file=json_linear_script_path, config=types.UploadFileConfig(display_name="linear_script_for_reference", mime_type="application/json"))

# Make the request
user_query = """
Generate a branching scenario script about a psychiatrist helping a patient diagnose and manage a sleep problem or disorder. The scenario should include discussion of the different stages of sleep and how they can affect a person's sleep quality, symptoms, and overall well-being.
"""

response = client.models.generate_content(
    model=MODEL,
    contents=[user_query, *uploaded_md_files, uploaded_json_template, uploaded_json_linear_script],
    config=config
)

# Write the response to a JSON file
output_json_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/Script_Generation_Pipeline/Script_Outputs/output_script_decision_points_separate_gemini.json"
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

client.files.delete(name=uploaded_json_template.name)

client.files.delete(name=uploaded_json_linear_script.name)
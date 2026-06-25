from anthropic import Anthropic
import os
from dotenv import load_dotenv
from pathlib import Path

## comment

env_path = Path(__file__).resolve().parents[2] / "backend.env"
load_dotenv(env_path)

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

system_prompt = """
You are an expert instructional designer and screenplay writer.

You will be provided with one or more textbook chapters in Markdown format, along with a JSON file containing a previously generated linear scenario script derived from those chapters.

The JSON file represents the complete linear scenario and should serve as the primary source for its characters, setting, dialogue, visual descriptions, scene structure, pacing, and narrative flow.

Your task is to convert the linear scenario into a single interactive branching scenario while preserving the original scenario as closely as possible. The original characters, setting, sequence of events, dialogue style, pacing, learning objectives, and overall narrative should remain unchanged whenever possible. Do not redesign the scenario or introduce a different situation. Instead, identify a Narrative scene within the existing script where a learner-facing decision can be inserted.

All decisions, answer choices, consequences, outcomes, and learning points must be fully grounded in the concepts, procedures, guidelines, principles, and reasoning presented in the provided chapters. Do not introduce substantive content that is not supported by the source material.

The final scenario must contain at most three decision points and follow this repeatable structure:
1. Narrative Scene (setup)
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

Output your response strictly as a JSON object following the exact structure in the provided JSON file, with no additional text before or after
"""

MODEL = "claude-sonnet-4-6"

TOKEN_LIMIT = client.models.retrieve(MODEL).max_tokens

# MARKDOWN
md_file_paths = [
    "/Users/youssef/Desktop/work/Openstax-Undergrads/textbook-content/psychology-chapter-4.2.md",
    "/Users/youssef/Desktop/work/Openstax-Undergrads/textbook-content/psychology-chapter-4.3.md",
    "/Users/youssef/Desktop/work/Openstax-Undergrads/textbook-content/psychology-chapter-4.4.md",
]

md_file_names = [
    "psychology-chapter-4.2",
    "psychology-chapter-4.3",
    "psychology-chapter-4.4",
]

uploaded_md_files_ids = []

for md_file_path, md_file_name in zip(md_file_paths, md_file_names):
    uploaded_md = client.beta.files.upload(
        file=(md_file_name, open(md_file_path, "rb"), "text/plain")
    )
    uploaded_md_files_ids.append(uploaded_md.id)

# JSON File Template
json_template_file_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/Script_Generation_Pipeline/JSON_Templates/dpoints_separate.json"

uploaded_json_template = client.beta.files.upload(
    file=(
        "script_gen_decision_points_separate",
        open(json_template_file_path, "rb"),
        "text/plain",
    )
)

# JSON Linear Script
json_linear_script_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/Script_Generation_Pipeline/Script_Outputs/output_script_without_decision_points_anthropic.json"

uploaded_json_linear_script = client.beta.files.upload(
    file=(
        "linear_script_for_reference",
        open(json_linear_script_path, "rb"),
        "text/plain",
    )
)

# Make the request
user_query = """
Generate a branching scenario script about a psychiatrist helping a patient diagnose and manage a sleep problem or disorder. The scenario should include discussion of the different stages of sleep and how they can affect a person's sleep quality, symptoms, and overall well-being.
"""

content = [
    {
        "type": "document",
        "source": {"type": "file", "file_id": fid},
        "title": "Textbook Chapter",
    }
    for fid in uploaded_md_files_ids
]

content.append(
    {
        "type": "document",
        "source": {"type": "file", "file_id": uploaded_json_template.id},
        "title": "JSON Script Template",
    }
)

content.append(
    {
        "type": "document",
        "source": {"type": "file", "file_id": uploaded_json_linear_script.id},
        "title": "JSON Linear Scenario Script",
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

# Write the response to a JSON file
output_json_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/Script_Generation_Pipeline/Script_Outputs/output_script_decision_points_separate_anthropic.json"
with open(output_json_path, "w") as f:
    output_json = response.content[0].text
    output_json = output_json.strip("```json").strip("```")
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

client.beta.files.delete(uploaded_json_template.id)

client.beta.files.delete(uploaded_json_linear_script.id)

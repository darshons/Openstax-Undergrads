from anthropic import Anthropic
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(env_path)

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# PDF OPTION
# pdf_file_path = "Clinical-Nursing-Skills-WEB/Clinical-Nursing-Skills-WEB_Chapter 1 The Role of the Nurse in Comprehensive Care.pdf"

# pdf_file_name = "Clinical-Nursing-Skills-WEB_Chapter 1 The Role of the Nurse in Comprehensive Care"

# file = client.beta.files.upload(file=(pdf_file_name, open(pdf_file_path, "rb"), "application/pdf"))

# MARKDOWN OPTION
md_file_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/Script_Generation_Pipeline/Preprocessing/output.md"

md_file_name = "psychology-chapter"

file = client.beta.files.upload(file=(md_file_name, open(md_file_path, "rb"), "text/plain"))

file_id = file.id

# Create a message with the uploaded file
response = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    betas=["files-api-2025-04-14"], # Use the beta version of the files API to access the uploaded file
    system="You are a helpful assistant who summarizes the content of the provided files.", # System prompt to guide the model's behavior
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {"type": "file", "file_id": file_id}, # Reference the uploaded file by its ID and can extend to include other files
                },
                {
                    "type": "text", 
                    "text": "What is a sulcus?" # query to be answered based on the content of the PDF file
                },
            ],
        }
    ],
)

print(response.content[0].text) # Get the output text from the response

print("\n\n")

# List all uploaded files
files = client.beta.files.list()
for f in files:
    print(f.id, f.filename)

# Delete a file when done with file as file are stored and connected to the account until deleted 
client.beta.files.delete(file_id)


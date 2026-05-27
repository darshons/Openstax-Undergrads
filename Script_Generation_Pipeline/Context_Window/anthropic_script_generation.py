from anthropic import Anthropic
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(env_path)

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

file_path = "Clinical-Nursing-Skills-WEB/Clinical-Nursing-Skills-WEB_Chapter 1 The Role of the Nurse in Comprehensive Care.pdf"

file_name = "Clinical-Nursing-Skills-WEB_Chapter 1 The Role of the Nurse in Comprehensive Care.pdf"

# Upload PDF
file = client.beta.files.upload(
    file=(file_name, open(file_path, "rb"), "application/pdf")
)

file_id = file.id

# Create a message with the uploaded file
response = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    betas=["files-api-2025-04-14"], # Use the beta version of the files API to access the uploaded file
    system="You are a helpful assistant who summarizes the content of the provided PDF files.", # System prompt to guide the model's behavior
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
                    "text": "Who is the creator of nursing, and what year did they die in?" # query to be answered based on the content of the PDF file
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


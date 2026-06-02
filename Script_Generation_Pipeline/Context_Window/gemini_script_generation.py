from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(env_path)

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Configure the system instruction
config = types.GenerateContentConfig(
    system_instruction="You are a helpful assistant who summarizes the content of the provided files.",
    max_output_tokens=2048
)

# PDF OPTION
# pdf_file_path = "Clinical-Nursing-Skills-WEB/Clinical-Nursing-Skills-WEB_Chapter 1 The Role of the Nurse in Comprehensive Care.pdf"

# file_name = "Clinical-Nursing-Skills-WEB_Chapter 1 The Role of the Nurse in Comprehensive Care"

# uploaded_pdf = client.files.upload(file=pdf_file_path, config=types.UploadFileConfig(display_name=pdf_file_name))

# uploaded_pdf = client.files.get(name="files/ri9tk6eaqrko") 

# MARKDOWN OPTION
md_file_path = "/Users/youssef/Desktop/work/Openstax-Undergrads/Script_Generation_Pipeline/Preprocessing/output.md"

md_file_name = "psychology-chapter"

uploaded_md = client.files.upload(file=md_file_path, config=types.UploadFileConfig(display_name=md_file_name, mime_type="text/markdown")) # switch to text/pdf for PDF files

# uploaded_md = client.files.get(name="files/brjip1ecdqph")

# Make the request
response = client.models.generate_content(
    model="gemini-3.5-flash", 
    contents=["What is a sulcus?", uploaded_md],
    config=config
)

print(response.text)

print("\n\n")

for file in client.files.list():
    print(f"Display Name: {file.display_name}")
    print(f"  File ID: {file.name}") # Will look like 'files/abc123xyz...'
    print(f"  Mime Type:    {file.mime_type}")
    print(f"  URI:          {file.uri}")
    
    
client.files.delete(name=uploaded_md.name)
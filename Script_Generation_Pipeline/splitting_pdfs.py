from pypdf import PdfReader, PdfWriter
import re
import os

pdf_name = "Clinical-Nursing-Skills-WEB"

reader = PdfReader(f"/Users/youssef/Desktop/{pdf_name}.pdf")

sections = []

for item in reader.outline:

    # Skip nested subsection lists
    if isinstance(item, list):
        continue

    title = item.title
    start_page = reader.get_destination_page_number(item)

    sections.append((title, start_page))

# Generate a list of sections with their corresponding start and end page numbers
for i in range(len(sections)):
    title, start_page = sections[i]
    
    end_page = None
    
    if i < len(sections) - 1:
        end_page = sections[i + 1][1]-1 # The end page of the current section is one page before the start page of the next section
    else:
        end_page = len(reader.pages) # The end page of the last section is the total number of pages in the PDF

    sections[i] = (title, start_page, end_page)

filtered_sections = [section for section in sections if re.match(r"^Chapter\s+\d+", section[0])] # Filter out sections that do not match the pattern "Chapter X"

# Create a new PDF for each filtered section
for title, start_page, end_page in filtered_sections:
    #create a directory for the output PDFs if it doesn't exist
    os.makedirs(pdf_name, exist_ok=True)
    
    writer = PdfWriter()
    
    for page_num in range(start_page, end_page + 1):
        writer.add_page(reader.pages[page_num])
    
    output_filename = f"{pdf_name}/{pdf_name}_{title}.pdf"
    with open(output_filename, "wb") as output_file:
        writer.write(output_file)

    
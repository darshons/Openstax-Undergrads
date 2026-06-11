from fastapi import APIRouter, BackgroundTasks
from Script_Generation_Pipeline.Preprocessing.html_crawler import crawl
import Script_Generation_Pipeline.Script_With_Dpoints.anthropic_script_generation as anthropic_script_generation
import Script_Generation_Pipeline.Script_With_Dpoints.gemini_script_generation as gemini_script_generation 
from pydantic import BaseModel
from pathlib import Path
import re
from typing import Any

class SceneInformation(BaseModel):
    book_title: str
    unit_num: int
    chapter_num: int | None
    page_num: float | None
    user_query: str
    model_choice: str    
    
class ModifiedScript(BaseModel):
    script: dict[str, Any]
    

api_router = APIRouter()

# This endpoint will be called by the frontend to generate the initial script based on the user's query and the relevant textbook content (currently with decision points included)
@api_router.post("/initial_script")
def generate_initial_script(scene_information: SceneInformation, background_tasks: BackgroundTasks) -> dict:
    ## parser functionality call
    parsedResult = crawl(
        scene_information.book_title,
        unit_num=scene_information.unit_num,
        chapter_num=scene_information.chapter_num, 
        page_num=scene_information.page_num,
    )

    # Merge all pages into one Markdown file
    merged = "\n\n---\n\n".join(p["markdown"] for p in parsedResult["pages"])

    # Build a more descriptive name
    def _slugify(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
 
    parts = [_slugify(scene_information.book_title)]
    if scene_information.unit_num is not None: parts.append(f"unit-{scene_information.unit_num}")
    if scene_information.chapter_num is not None: parts.append(f"ch-{scene_information.chapter_num}")
    if scene_information.page_num is not None: parts.append(f"p-{scene_information.page_num}")
 
    # Make absolute position in the project folder
    PROJECT_DIR = Path(__file__).resolve().parent
    output_dir = PROJECT_DIR / "Script_Generation_Pipeline" / "Textbook_Context"

    md_path = output_dir / f"{'_'.join(parts)}.md" 

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(merged)
    
    # script generation functionality call
    initial_script = None

    if scene_information.model_choice == "anthropic":
        initial_script, file_ids = anthropic_script_generation.generate_script_with_decision_points(str(md_path), scene_information.user_query, background_tasks)
        
        for file_id in file_ids:
            background_tasks.add_task(anthropic_script_generation.delete_uploaded_file, file_id)
        
    elif scene_information.model_choice == "gemini":
        initial_script, file_ids = gemini_script_generation.generate_script_with_decision_points(str(md_path), scene_information.user_query, background_tasks)
        
        for file_name in file_ids:
            background_tasks.add_task(gemini_script_generation.delete_uploaded_file, file_name)
    
    return {"message": "Initial script generation completed", "script": initial_script}

# This endpoint will be called by the frontend once the user has finished modifying the initial script and is ready to generate the image frames
@api_router.post("/modified_script")
def generate_final_script(modified_script: ModifiedScript) -> dict:
    print("Received modified script:", modified_script.script)
    return {"message": "Final script generation request received"}

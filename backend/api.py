from fastapi import APIRouter
from Script_Generation_Pipeline.Preprocessing.html_crawler import crawl
from Script_Generation_Pipeline.script_with_dpoints import anthropic_script_generation, gemini_script_generation
from pydantic import BaseModel
from pathlib import Path
import re

class SceneInformation(BaseModel):
    book_title: str
    unit_num: int
    chapter_num: int | None
    page_num: int | None
    user_query: str
    model_choice: str    

router = APIRouter()

@router.get("/script")
def generate_initial_script(scene_information: SceneInformation) -> dict:
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
    output_dir = PROJECT_DIR / "Script_Generation_Pipeline" / "textbook_context"
    output_dir.mkdir(exist_ok=True)

    md_path = output_dir / f"{'_'.join(parts)}.md" 

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(merged)
    
    # script generation functionality call
    initial_script = None

    if scene_information.model_choice == "anthropic":
        initial_script = anthropic_script_generation.generate_script_with_decision_points(str(md_path), scene_information.user_query)
    elif scene_information.model_choice == "gemini":
        initial_script = gemini_script_generation.generate_script_with_decision_points(str(md_path), scene_information.user_query)
        
    return {"message": "Initial script generation completed", "script": initial_script}

# This endpoint will be called by the frontend once the user has finished modifying the initial script and is ready to generate the image frames
@router.post("/script")
def generate_final_script(user_inputs: dict) -> dict:
    print("Received user inputs:", user_inputs)
    return {"message": "Final script generation request received"}
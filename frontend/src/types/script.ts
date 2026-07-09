// ── Primitive enums ────────────────────────────────────────────────────────

export type SceneType = 'narrative' | 'consequence' | 'resolution';

/** How a scene connects to what follows it. */
export type RouteType =
  | 'introduction'   // scene leads into a decision point as context
  | 'true_choice'    // scene leads into a decision point as a question
  | 'false_choice'   // scene leads into a decision point on wrong path
  | 'decision_point' // scene retries back to a decision point
  | 'scene';         // scene continues directly to another scene

export type ViewMode = 'full' | 'dialogue' | 'action' | 'camera';
export type ModelChoice = 'anthropic' | 'gemini';
export type VideoType = 'scenario' | 'manim';
export type Page = 'script' | 'assets' | 'videos' | 'student';

// ── Routing ────────────────────────────────────────────────────────────────

export interface RoutesToDP {
  type: 'introduction' | 'true_choice' | 'false_choice' | 'decision_point';
  decision_point_id: number;
}

export interface RoutesToScene {
  type: 'scene';
  scene_id: number;
}

export type RoutesTo = RoutesToDP | RoutesToScene;

// ── Character ──────────────────────────────────────────────────────────────

export interface CharacterAppearance {
  skin_tone: string;
  hair: string;
  build: string;
  uniform: string;
  distinguishing_features: string;
}

export interface Character {
  character_id: string;
  name: string;
  role: string;
  appearance: CharacterAppearance;
  emotional_baseline: string;
}

// ── Scene audio ────────────────────────────────────────────────────────────

export interface DialogueLine {
  character_id: string;
  line: string;
  character_position?: string;
}

/** Alternate dialogue format some backend responses return. */
export interface Clip {
  character_id: string;
  dialogue: string;
}

export interface Audio {
  dialogue: DialogueLine[];
  sound_effects: string;
  ambience: string;
  /** Present in some backend responses as an alternative to dialogue[]. */
  clips?: Clip[];
}

// ── Camera ─────────────────────────────────────────────────────────────────

/** Per-scene camera (present in SAMPLE_SCRIPT format, not in LLM template). */
export interface Camera {
  angle: string;
  movement: string;
  lens_effect: string;
}

// ── Root-level setting (LLM template format) ───────────────────────────────

export interface FurnitureItem {
  name: string;
  count: number;
  description: string;
}

export interface ScriptSettingCamera {
  angle: string;
  perspective: string;
}

export interface ScriptSetting {
  location: string;
  scene_description: string;
  light_source: string;
  time_of_day: string;
  atmosphere: string;
  background_furniture: FurnitureItem[];
  background_equipment: FurnitureItem[];
  camera: ScriptSettingCamera;
}

// ── Character position within a scene ─────────────────────────────────────

export interface CharacterPosition {
  character_id: string;
  position: string;
}

// ── Scene ──────────────────────────────────────────────────────────────────

export interface Scene {
  scene_id: number;
  /** Primary type field from backend. */
  type?: SceneType;
  /** Alternate type field some backend responses use. */
  scene_type?: string;
  scene_summary: string;
  duration_seconds: number;
  /** Per-scene setting string (SAMPLE_SCRIPT format only; template uses root-level setting). */
  setting?: string;
  character_actions: string;
  initial_character_positions?: CharacterPosition[];
  /** Per-scene camera (SAMPLE_SCRIPT format only; template puts camera in root setting). */
  camera?: Camera;
  audio: Audio;
  routes_to?: RoutesTo;
  /** Narration copy used as display fallback in video page. */
  narration_text?: string;
  /** Generic description used as display fallback. */
  description?: string;
}

// ── Decision point ─────────────────────────────────────────────────────────

export interface Choice {
  choice_id: string;
  text: string;
  is_correct: boolean;
  misconception: string | null;
  routes_to_scene: number | null;
}

export interface DecisionPoint {
  decision_point_id: number;
  question_text: string;
  associated_introduction_scene_id: number;
  choices: Choice[];
}

// ── Script (root) ──────────────────────────────────────────────────────────

export interface Script {
  title: string;
  learning_goal: string;
  target_audience: string;
  total_duration_seconds: number;
  visual_style: string;
  characters: Character[];
  /** Root-level setting (LLM template format). Absent in SAMPLE_SCRIPT format. */
  setting?: ScriptSetting;
  scenes: Scene[];
  decision_points: DecisionPoint[];
}

// ── Asset image state ──────────────────────────────────────────────────────

export interface AssetImages {
  bgPath: string | null;
  charPaths: Record<string, string>; // character_id → absolute server path
  framePaths: Record<string, string>; // scene_id (string) → absolute server path
}

export type AssetsStep = 'idle' | 'generating' | 'done' | 'error';

// ── Generate request (matches SceneInformation Pydantic model in api.py) ──

export interface GenerateRequest {
  book_title: string;
  unit_num: number;
  chapter_num?: number | null;
  page_num?: string | null;
  user_query: string;
  model_choice: ModelChoice;
  video_type: VideoType;
}

import type { AssetImages, GenerateRequest, Script } from '../types/script';

export async function fetchInitialScript(
  req: GenerateRequest,
): Promise<{ script: Script; requestId: string }> {
  const res = await fetch('/instructor_api/initial_script', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Generation failed (${res.status})`);
  const data = await res.json();
  return { script: data.script as Script, requestId: data.request_id as string };
}

export async function generateBackgroundImage(
  script: Script,
  requestId: string,
): Promise<string> {
  const res = await fetch('/instructor_api/generate_background_image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ script, request_id: requestId }),
  });
  if (!res.ok) throw new Error(`Background generation failed (${res.status})`);
  const data = await res.json();
  return data.background_image_file_path as string;
}

export async function generateCharacterImages(
  script: Script,
  requestId: string,
): Promise<Record<string, string>> {
  const res = await fetch('/instructor_api/generate_character_images', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ script, request_id: requestId }),
  });
  if (!res.ok) throw new Error(`Character image generation failed (${res.status})`);
  const data = await res.json();
  return data.character_image_file_mapping as Record<string, string>;
}

export async function generateOpeningFrames(
  script: Script,
  requestId: string,
  backgroundImagePath: string,
  characterImageFileMapping: Record<string, string>,
): Promise<Record<string, string>> {
  const res = await fetch('/instructor_api/generate_opening_frames', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      script,
      request_id: requestId,
      background_image_path: backgroundImagePath,
      character_image_file_mapping: characterImageFileMapping,
    }),
  });
  if (!res.ok) throw new Error(`Opening frame generation failed (${res.status})`);
  const data = await res.json();
  return data.opening_scene_frame_file_mapping as Record<string, string>;
}

// ── Retry with optional user feedback ──────────────────────────────────────
// Response shape differs when feedback is provided vs plain retry:
//   background: always background_image_file_path (string)
//   character:  no feedback → character_image_file_mapping (dict)
//               with feedback → character_image_file_path (string)
//   frame:      no feedback → opening_scene_frame_file_mapping (dict)
//               with feedback → opening_frame_image_file_path (string)

export async function retryBackgroundImage(
  script: Script,
  requestId: string,
  feedback?: string,
): Promise<string> {
  const res = await fetch('/instructor_api/retry_generate_background_image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_request: { script, request_id: requestId },
      user_feedback: feedback ?? null,
      retry_image_id: null,
    }),
  });
  if (!res.ok) throw new Error(`Background retry failed (${res.status})`);
  const data = await res.json();
  return data.background_image_file_path as string;
}

export async function retryCharacterImage(
  script: Script,
  requestId: string,
  characterId: string,
  feedback?: string,
): Promise<string> {
  const res = await fetch('/instructor_api/retry_generate_character_image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_request: { script, request_id: requestId },
      user_feedback: feedback ?? null,
      retry_image_id: characterId,
    }),
  });
  if (!res.ok) throw new Error(`Character retry failed (${res.status})`);
  const data = await res.json();
  return feedback
    ? (data.character_image_file_path as string)
    : (data.character_image_file_mapping as Record<string, string>)[characterId];
}

export async function retryOpeningFrame(
  script: Script,
  requestId: string,
  bgPath: string,
  charPaths: Record<string, string>,
  sceneId: string,
  feedback?: string,
): Promise<string> {
  const res = await fetch('/instructor_api/retry_generate_opening_frames', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_request: {
        script,
        request_id: requestId,
        background_image_path: bgPath,
        character_image_file_mapping: charPaths,
      },
      user_feedback: feedback ?? null,
      retry_image_id: sceneId,
    }),
  });
  if (!res.ok) throw new Error(`Frame retry failed (${res.status})`);
  const data = await res.json();
  return feedback
    ? (data.opening_frame_image_file_path as string)
    : (data.opening_scene_frame_file_mapping as Record<string, string>)[sceneId];
}

/**
 * Convert an absolute server-side file path into a URL served by the backend.
 * The backend's FileResponse needs the absolute path back, so the leading
 * slash on serverPath must be preserved (hence the double slash below) -
 * FastAPI's :path converter treats everything after "/image/" as the value,
 * so stripping it would hand the server a relative path that doesn't exist.
 */
export function imageUrl(serverPath: string): string {
  const qIdx = serverPath.indexOf('?');
  const path = qIdx === -1 ? serverPath : serverPath.slice(0, qIdx);
  const qs = qIdx === -1 ? '' : serverPath.slice(qIdx);
  return `/instructor_api/image/${path}${qs}`;
}

/**
 * video_paths maps scene order to a video file path that must already exist
 * on the backend's own filesystem (the server reads and uploads it directly).
 * There's no scene-video generation step yet, so callers pass {} for now.
 */
export async function publishScenario(
  projectName: string,
  script: Script,
  videoPaths: Record<number, string> = {},
): Promise<void> {
  const res = await fetch('/instructor_api/upload_project_info', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_name: projectName, script, video_paths: videoPaths }),
  });
  if (res.status === 409) throw new Error(`A project named "${projectName}" already exists`);
  if (!res.ok) throw new Error(`Publish failed (${res.status})`);
}

/**
 * Convert an absolute server-side video file path into a URL served by the
 * backend (GET /instructor_api/video/{path:path}), mirroring imageUrl()'s
 * leading-slash handling.
 */
export function videoUrl(serverPath: string): string {
  const qIdx = serverPath.indexOf('?');
  const path = qIdx === -1 ? serverPath : serverPath.slice(0, qIdx);
  const qs = qIdx === -1 ? '' : serverPath.slice(qIdx);
  return `/instructor_api/video/${path}${qs}`;
}

export type VideoGenState =
  | 'idle'
  | 'queued'
  | 'planning_clips'
  | 'rendering'
  | 'done'
  | 'completed_with_errors'
  | 'failed';

export interface VideoStatus {
  state: VideoGenState;
  completed_scenes: Record<string, string>;
  failed_scenes: Record<string, string>;
  error?: string;
}

/**
 * Kicks off Veo scenario video generation for an approved script. Returns
 * once the job is queued server-side — poll getVideoStatus for progress.
 * background_image_path/character_image_file_mapping come straight from the
 * already-generated Studio assets and anchor character/environment
 * consistency across every scene's first clip.
 */
export async function generateVideos(
  script: Script,
  requestId: string,
  backgroundImagePath: string,
  characterImageFileMapping: Record<string, string>,
): Promise<void> {
  const res = await fetch('/instructor_api/generate_videos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      script,
      request_id: requestId,
      background_image_path: backgroundImagePath,
      character_image_file_mapping: characterImageFileMapping,
    }),
  });
  if (!res.ok) throw new Error(`Video generation failed to start (${res.status})`);
}

export async function getVideoStatus(requestId: string): Promise<VideoStatus> {
  const res = await fetch(`/instructor_api/video_status/${encodeURIComponent(requestId)}`);
  if (!res.ok) throw new Error(`Video status check failed (${res.status})`);
  return res.json();
}

// ── Manim graphics video generation ─────────────────────────────────────────
// Mirrors generateVideos/getVideoStatus above, but the pipeline needs no
// reference images (diagrams, not characters) and its status.json uses a
// finer-grained, open-ended state string (e.g. "scene_3_of_8") rather than
// Veo's fixed enum. normalizeManimState folds that into the same VideoGenState
// union so VideoPage's state handling stays video-type-agnostic.

interface RawManimStatus {
  state: string; // queued | assets | scene_k_of_n | stitching | done | error
  completed_scenes: Record<string, string>;
  failed_scenes: Record<string, string>;
  manifest?: unknown;
  error?: string | null;
}

function normalizeManimState(state: string): VideoGenState {
  if (state === 'done') return 'done';
  if (state === 'error') return 'failed';
  if (state === 'queued') return 'queued';
  return 'rendering'; // assets | scene_k_of_n | stitching
}

export async function generateManimVideos(
  script: Script,
  requestId: string,
): Promise<void> {
  const res = await fetch('/instructor_api/generate_manim_videos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ script, request_id: requestId }),
  });
  if (!res.ok) throw new Error(`Manim video generation failed to start (${res.status})`);
}

export async function getManimStatus(requestId: string): Promise<VideoStatus> {
  const res = await fetch(`/instructor_api/manim_video_status/${encodeURIComponent(requestId)}`);
  if (!res.ok) throw new Error(`Manim status check failed (${res.status})`);
  const data = (await res.json()) as RawManimStatus;
  return {
    state: normalizeManimState(data.state),
    completed_scenes: data.completed_scenes,
    failed_scenes: data.failed_scenes,
    error: data.error ?? undefined,
  };
}

interface ScenarioAssets {
  script: Script;
  assetImages: AssetImages;
  videoLinks: Record<string, string>;
}

async function resolveAssetsResponse(
  res: Response,
  label: string,
): Promise<ScenarioAssets> {
  if (!res.ok) throw new Error(`Scenario "${label}" not found (${res.status})`);
  const data = await res.json();

  const scriptRes = await fetch(data.script_link as string);
  if (!scriptRes.ok) throw new Error(`Failed to load script for "${label}"`);
  const script = (await scriptRes.json()) as Script;

  return {
    script,
    assetImages: { bgPath: null, charPaths: {}, framePaths: {} },
    videoLinks: data.video_links as Record<string, string>,
  };
}

export async function fetchScenario(projectName: string): Promise<ScenarioAssets> {
  const res = await fetch(`/student_api/assets/${encodeURIComponent(projectName)}`);
  return resolveAssetsResponse(res, projectName);
}

/** Loads the coworker's hardcoded test fixture (1 script, 3 mismatched videos) for testing playback. */
export async function fetchDummyScenario(): Promise<ScenarioAssets> {
  const res = await fetch('/student_api/dummy_assets');
  return resolveAssetsResponse(res, 'dummy');
}

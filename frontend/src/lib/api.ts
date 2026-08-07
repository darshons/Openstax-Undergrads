import type { AssetImages, GenerateRequest, ScenarioBackend, Script } from '../types/script';

/**
 * Backend base URL.
 *  - Override with VITE_API_BASE (e.g. VITE_API_BASE=http://myhost:8000).
 *  - Dev default: http://localhost:8000 (FastAPI dev server; CORS is open).
 *  - Prod default: same-origin '/openstax-api' — the reverse proxy is expected
 *    to strip that prefix and forward to the backend root, e.g. nginx:
 *      location /openstax-api/ { proxy_pass http://127.0.0.1:8000/; }
 * All routes below use '/instructor_api/...' (FastAPI mounts the instructor router there).
 */
export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  (import.meta.env.DEV ? 'http://localhost:8000' : '/openstax-api');

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export async function fetchInitialScript(
  req: GenerateRequest,
): Promise<{ script: Script; requestId: string }> {
  const res = await fetch(apiUrl('/instructor_api/initial_script'), {
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
  const res = await fetch(apiUrl('/instructor_api/generate_background_image'), {
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
  const res = await fetch(apiUrl('/instructor_api/generate_character_images'), {
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
  const res = await fetch(apiUrl('/instructor_api/generate_opening_frames'), {
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
  const res = await fetch(apiUrl('/instructor_api/retry_generate_background_image'), {
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
  const res = await fetch(apiUrl('/instructor_api/retry_generate_character_image'), {
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
  const res = await fetch(apiUrl('/instructor_api/retry_generate_opening_frames'), {
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

/** Convert an absolute server-side file path into a URL served by the backend. */
export function imageUrl(serverPath: string): string {
  const qIdx = serverPath.indexOf('?');
  const path = qIdx === -1 ? serverPath : serverPath.slice(0, qIdx);
  const qs = qIdx === -1 ? '' : serverPath.slice(qIdx);
  return apiUrl(`/instructor_api/image/${path.replace(/^\//, '')}${qs}`);
}

/** Convert an absolute server-side video path into a URL served by the backend. */
export function videoUrl(serverPath: string): string {
  return apiUrl(`/instructor_api/video/${serverPath}`);
}

/** Kick off Manim branching-video generation for the current edited script. */
export async function generateManimVideos(
  script: Script,
  requestId: string,
): Promise<{ status: string; requestId: string }> {
  const res = await fetch(apiUrl('/instructor_api/generate_manim_videos'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ script, request_id: requestId }),
  });
  if (!res.ok) throw new Error(`Manim video generation failed (${res.status})`);
  const data = await res.json();
  return { status: data.status as string, requestId: data.request_id as string };
}

export interface ManimStatus {
  state: string; // queued | assets | scene_k_of_n | stitching | done | partial | error
  completed_scenes: Record<string, string>; // scene_id -> server video path
  failed_scenes: Record<string, string>;
  manifest?: unknown;
  error?: string | null;
}

/** Kick off character-scene video generation on the chosen backend. */
export async function generateScenarioVideos(
  script: Script,
  requestId: string,
  backend: ScenarioBackend,
  opts: {
    backgroundImagePath?: string | null;
    characterImageFileMapping?: Record<string, string> | null;
    characterLora?: string | null;
  } = {},
): Promise<{ status: string; backend: string }> {
  const res = await fetch(apiUrl('/instructor_api/generate_videos'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      script,
      request_id: requestId,
      backend,
      background_image_path: opts.backgroundImagePath ?? null,
      character_image_file_mapping: opts.characterImageFileMapping ?? null,
      character_lora: opts.characterLora ?? null,
    }),
  });
  if (!res.ok) {
    // The backend returns a usable message for the common cases (missing
    // GEMINI_API_KEY, missing reference images) -- surface it rather than a code.
    const detail = await res.json().then(d => d?.detail).catch(() => null);
    throw new Error(detail || `Scenario video generation failed (${res.status})`);
  }
  const data = await res.json();
  return { status: data.status as string, backend: data.backend as string };
}

/** Poll the status of a character-scene generation run. */
export async function getScenarioStatus(requestId: string): Promise<ManimStatus> {
  const res = await fetch(apiUrl(`/instructor_api/video_status/${requestId}`));
  if (!res.ok) throw new Error(`Status check failed (${res.status})`);
  return (await res.json()) as ManimStatus;
}

/** Poll the status of a Manim video-generation run. */
export async function getManimStatus(requestId: string): Promise<ManimStatus> {
  const res = await fetch(apiUrl(`/instructor_api/manim_video_status/${requestId}`));
  if (!res.ok) throw new Error(`Status check failed (${res.status})`);
  return (await res.json()) as ManimStatus;
}

/**
 * Publish a script + its rendered scene videos to Supabase storage under
 * projectName, so students can fetch it via fetchScenario. There's no
 * scene-video generation step wired into the Student flow yet, so callers
 * pass {} for videoPaths for now.
 */
export async function publishScenario(
  projectName: string,
  script: Script,
  videoPaths: Record<number, string> = {},
): Promise<void> {
  const res = await fetch(apiUrl('/instructor_api/upload_project_info'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_name: projectName, script, video_paths: videoPaths }),
  });
  if (res.status === 409) throw new Error(`A project named "${projectName}" already exists`);
  if (!res.ok) throw new Error(`Publish failed (${res.status})`);
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

/** Fetch a published scenario's script + video links by project name. */
export async function fetchScenario(projectName: string): Promise<ScenarioAssets> {
  const res = await fetch(apiUrl(`/student_api/assets/${encodeURIComponent(projectName)}`));
  return resolveAssetsResponse(res, projectName);
}

/** Loads a hardcoded test fixture for testing student playback without a real publish. */
export async function fetchDummyScenario(): Promise<ScenarioAssets> {
  const res = await fetch(apiUrl('/student_api/dummy_assets'));
  return resolveAssetsResponse(res, 'dummy');
}

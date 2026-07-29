import type { GenerateRequest, Script } from '../types/script';

/**
 * Backend base URL.
 *  - Override with VITE_API_BASE (e.g. VITE_API_BASE=http://myhost:8000).
 *  - Dev default: http://localhost:8000 (FastAPI dev server; CORS is open).
 *  - Prod default: same-origin '/openstax-api' — the reverse proxy is expected
 *    to strip that prefix and forward to the backend root, e.g. nginx:
 *      location /openstax-api/ { proxy_pass http://127.0.0.1:8000/; }
 * All routes below keep their '/api/...' path (FastAPI mounts the router at /api).
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
  const res = await fetch(apiUrl('/api/initial_script'), {
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
  const res = await fetch(apiUrl('/api/generate_background_image'), {
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
  const res = await fetch(apiUrl('/api/generate_character_images'), {
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
  const res = await fetch(apiUrl('/api/generate_opening_frames'), {
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
  const res = await fetch(apiUrl('/api/retry_generate_background_image'), {
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
  const res = await fetch(apiUrl('/api/retry_generate_character_image'), {
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
  const res = await fetch(apiUrl('/api/retry_generate_opening_frames'), {
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
  return apiUrl(`/api/image/${path.replace(/^\//, '')}${qs}`);
}

/** Convert an absolute server-side video path into a URL served by the backend. */
export function videoUrl(serverPath: string): string {
  return apiUrl(`/api/video/${serverPath}`);
}

/** Kick off Manim branching-video generation for the current edited script. */
export async function generateManimVideos(
  script: Script,
  requestId: string,
): Promise<{ status: string; requestId: string }> {
  const res = await fetch(apiUrl('/api/generate_manim_videos'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ script, request_id: requestId }),
  });
  if (!res.ok) throw new Error(`Manim video generation failed (${res.status})`);
  const data = await res.json();
  return { status: data.status as string, requestId: data.request_id as string };
}

export interface ManimStatus {
  state: string; // queued | assets | scene_k_of_n | stitching | done | error
  completed_scenes: Record<string, string>; // scene_id -> server video path
  failed_scenes: Record<string, string>;
  manifest?: unknown;
  error?: string | null;
}

/** Poll the status of a Manim video-generation run. */
export async function getManimStatus(requestId: string): Promise<ManimStatus> {
  const res = await fetch(apiUrl(`/api/manim_video_status/${requestId}`));
  if (!res.ok) throw new Error(`Status check failed (${res.status})`);
  return (await res.json()) as ManimStatus;
}

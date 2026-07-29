import type { GenerateRequest, Script } from '../types/script';

export async function fetchInitialScript(
  req: GenerateRequest,
): Promise<{ script: Script; requestId: string }> {
  const res = await fetch('/api/initial_script', {
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
  const res = await fetch('/api/generate_background_image', {
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
  const res = await fetch('/api/generate_character_images', {
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
  const res = await fetch('/api/generate_opening_frames', {
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
  const res = await fetch('/api/retry_generate_background_image', {
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
  const res = await fetch('/api/retry_generate_character_image', {
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
  const res = await fetch('/api/retry_generate_opening_frames', {
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
  return `/api/image/${path.replace(/^\//, '')}${qs}`;
}

/** Convert an absolute server-side video path into a URL served by the backend. */
export function videoUrl(serverPath: string): string {
  return `/api/video/${serverPath}`;
}

/** Kick off Manim branching-video generation for the current edited script. */
export async function generateManimVideos(
  script: Script,
  requestId: string,
): Promise<{ status: string; requestId: string }> {
  const res = await fetch('/api/generate_manim_videos', {
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
  const res = await fetch(`/api/manim_video_status/${requestId}`);
  if (!res.ok) throw new Error(`Status check failed (${res.status})`);
  return (await res.json()) as ManimStatus;
}

export interface ManimAsset {
  path: string; // run-relative, pass to manimAssetUrl / getManimAssetText
  name: string;
  role: 'run' | 'asset_kit' | 'scene' | 'scene_code' | 'scene_error';
  kind: 'text' | 'image' | 'video' | 'other';
  size_bytes: number;
}

export interface ManimSceneAssets {
  scene_id: number | null;
  video: ManimAsset | null;
  plan: ManimAsset | null;
  code_versions: ManimAsset[]; // ordered v0..vN
  latest_code: ManimAsset | null;
  error_logs: ManimAsset[];
  artifacts: ManimAsset[]; // grid-critic snapshots + overlays
}

export interface ManimAssets {
  request_id: string;
  run: ManimAsset[]; // manifest.json, generation_log.jsonl, golden_path.mp4, ...
  asset_kit: ManimAsset[];
  scenes: ManimSceneAssets[];
}

/** List every intermediate a Manim run produced, grouped per scene. */
export async function getManimAssets(requestId: string): Promise<ManimAssets> {
  const res = await fetch(`/api/manim_assets/${requestId}`);
  if (!res.ok) throw new Error(`Asset listing failed (${res.status})`);
  return (await res.json()) as ManimAssets;
}

/** URL for one intermediate, by its run-relative path (use for <img>/<video>). */
export function manimAssetUrl(requestId: string, assetPath: string): string {
  return `/api/manim_asset/${requestId}/${assetPath}`;
}

/** Fetch a text intermediate (a scene's plan or generated Manim source). */
export async function getManimAssetText(requestId: string, assetPath: string): Promise<string> {
  const res = await fetch(manimAssetUrl(requestId, assetPath));
  if (!res.ok) throw new Error(`Asset fetch failed (${res.status})`);
  return await res.text();
}

/** Re-render ONE scene from edited input, reusing the run's frozen asset kit.
 *
 * Pass `plan` to re-plan by hand, `code` to render your own Manim source
 * verbatim, or `script` to change the scene's dialogue/routing. Omit all three
 * for a plain retry. Returns immediately — poll getManimStatus for progress. */
export async function regenerateManimScene(
  requestId: string,
  sceneId: number,
  edits: { plan?: string; code?: string; script?: Script; restitch?: boolean } = {},
): Promise<{ status: string; sceneId: number }> {
  const res = await fetch(`/api/regenerate_manim_scene/${requestId}/${sceneId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      plan: edits.plan ?? null,
      code: edits.code ?? null,
      script: edits.script ?? null,
      restitch: edits.restitch ?? true,
    }),
  });
  if (!res.ok) throw new Error(`Scene regeneration failed (${res.status})`);
  const data = await res.json();
  return { status: data.status as string, sceneId: data.scene_id as number };
}

import type { AssetImages, GenerateRequest, Script } from '../types/script';

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

export async function publishScenario(
  name: string,
  script: Script,
  assetImages: AssetImages,
): Promise<void> {
  const res = await fetch('/api/scenario/publish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, script, asset_images: assetImages }),
  });
  if (!res.ok) throw new Error(`Publish failed (${res.status})`);
}

export async function fetchScenario(
  name: string,
): Promise<{ script: Script; assetImages: AssetImages }> {
  const res = await fetch(`/api/scenario/${encodeURIComponent(name)}`);
  if (!res.ok) throw new Error(`Scenario "${name}" not found (${res.status})`);
  const data = await res.json();
  return { script: data.script as Script, assetImages: data.asset_images as AssetImages };
}

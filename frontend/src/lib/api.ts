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

/** Convert an absolute server-side file path into a URL served by the backend. */
export function imageUrl(serverPath: string): string {
  return `/api/image/${serverPath}`;
}

export function fmtDuration(secs: number | null | undefined): string {
  if (secs == null) return '—';
  const m = Math.floor(secs / 60), s = secs % 60;
  return m > 0 ? `${m}:${String(s).padStart(2, '0')}` : `${s}s`;
}

export function characterName(characters: { character_id: string; name: string }[], id: string): string {
  const c = characters.find(c => c.character_id === id);
  return c ? c.name : id;
}

export const SCENE_TYPES = ['narrative', 'consequence', 'resolution'] as const;
export const ROUTE_TYPES = ['introduction', 'true_choice', 'false_choice'] as const;

/**
 * Converts a scene_id -> video URL map (what VideoPage tracks) into the
 * position-keyed "scene_N.mp4" -> URL format StudentPlayer's videoLinks prop expects.
 */
export function sceneVideoLinks(
  scenes: { scene_id: number }[],
  sceneVideos: Record<number, string>,
): Record<string, string> {
  const links: Record<string, string> = {};
  scenes.forEach((scene, i) => {
    const url = sceneVideos[scene.scene_id];
    if (url) links[`scene_${i + 1}.mp4`] = url;
  });
  return links;
}

import type { AssetImages, Script } from '../types/script';

/**
 * Stopgap client-side persistence until the backend supports
 * POST /api/scenario/publish + GET /api/scenario/:id. Stores the single
 * most-recently-published scenario so the Student flow can be reached
 * from the landing page without going through the Creator Studio session.
 */
const STORAGE_KEY = 'openstax:savedScenario';

export interface SavedScenario {
  script: Script;
  assetImages: AssetImages;
}

export function saveScenario(script: Script, assetImages: AssetImages): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ script, assetImages }));
}

export function loadScenario(): SavedScenario | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  return JSON.parse(raw) as SavedScenario;
}

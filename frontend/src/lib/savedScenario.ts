import type { AssetImages, Script } from '../types/script';

/**
 * Client-side fallback so the Student flow is reachable from the landing page
 * without a real publish - PlayerPage falls back to this when a requested
 * project name isn't found via fetchScenario.
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

import type { GenerateRequest, Script } from '../types/script';

export async function fetchInitialScript(req: GenerateRequest): Promise<Script> {
  const res = await fetch('/api/initial_script', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Generation failed (${res.status})`);
  const data = await res.json();
  return data.script as Script;
}

export async function fetchDummyPaths(target: 'script' | 'images' | 'video') {
  const res = await fetch(`/api/dummy_paths?target=${target}`);
  if (!res.ok) throw new Error(`Failed to fetch paths (${res.status})`);
  return res.json();
}

// In production the backend is deployed as a sibling Vercel service mounted at
// the "/_/backend" route prefix (see the root vercel.json). Locally it runs on
// uvicorn at :8000. Override with NEXT_PUBLIC_API_BASE when needed.
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  (process.env.NODE_ENV === "production"
    ? "/_/backend/api"
    : "http://localhost:8000/api");

export interface ScenarioResponse {
  id: string;
  chapter_reference: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface EdgeResponse {
  id: string;
  origin_node_id: string;
  destination_node_id: string;
  choice_text: string;
  is_misconception_branch: boolean;
}

export interface NodeDetail {
  id: string;
  scenario_id: string;
  video_path: string | null;
  node_prompt: string | null;
  is_endpoint: boolean;
  outgoing_edges: EdgeResponse[];
}

export interface ScriptChoice {
  id: string;
  text: string;
  destination_scene_id: string;
  is_misconception: boolean;
  feedback: string;
}

export interface ScriptNode {
  id: string;
  scene_number: number;
  title: string;
  script: string;
  video_prompt: string;
  is_endpoint: boolean;
  choices: ScriptChoice[];
}

export interface Script {
  title: string;
  nodes: ScriptNode[];
}

export interface ScenarioDetail extends ScenarioResponse {
  nodes: NodeDetail[];
  script: Script | null;
}

export interface GenerateRequest {
  book_title: string;
  unit_num: number;
  chapter_num?: number;
  page_num?: string;
  user_query: string;
  model_choice: "anthropic" | "gemini";
}

export interface GenerateResponse {
  message: string;
  script: Script;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function getScenarios(): Promise<ScenarioResponse[]> {
  return apiFetch<ScenarioResponse[]>("/scenarios");
}

export function getScenario(id: string): Promise<ScenarioDetail> {
  return apiFetch<ScenarioDetail>(`/scenarios/${id}`);
}

export function generateScenario(req: GenerateRequest): Promise<GenerateResponse> {
  return apiFetch<GenerateResponse>("/initial_script", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function submitModifiedScript(script: unknown): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/modified_script", {
    method: "POST",
    body: JSON.stringify({ script }),
  });
}

// Persist the user's edited script for a scenario. The current backend
// `/modified_script` endpoint accepts the script payload; the scenarioId is
// accepted here for forward compatibility with a per-scenario save route.
export function saveScript(
  scenarioId: string,
  script: Script
): Promise<{ message: string }> {
  void scenarioId;
  return submitModifiedScript(script);
}

export function updateNode(
  scenarioId: string,
  nodeId: string,
  nodePrompt: string
): Promise<NodeDetail> {
  return apiFetch<NodeDetail>(`/scenarios/${scenarioId}/nodes/${nodeId}`, {
    method: "PUT",
    body: JSON.stringify({ node_prompt: nodePrompt }),
  });
}

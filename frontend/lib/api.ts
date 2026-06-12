const API_BASE = "http://localhost:8000/api";

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
  textbook: string;
  chapters: string[];
  units: string;
  description: string;
}

export interface GenerateResponse {
  scenario_id: string;
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
  return apiFetch<GenerateResponse>("/scenarios/generate", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function saveScript(
  scenarioId: string,
  script: Script
): Promise<{ scenario_id: string }> {
  return apiFetch(`/scenarios/${scenarioId}/script`, {
    method: "PUT",
    body: JSON.stringify({ script }),
  });
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

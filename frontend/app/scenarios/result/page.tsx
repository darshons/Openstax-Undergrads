"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { submitModifiedScript } from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DialogueLine {
  character_id: string;
  line: string;
}

interface Scene {
  scene_id: number;
  type: string;
  duration_seconds: number;
  setting: string;
  character_actions: string;
  camera: Record<string, unknown>;
  audio: {
    dialogue: DialogueLine[];
    sound_effects: string;
    ambience: string;
  };
  routes_to: Record<string, unknown>;
}

interface Choice {
  choice_id: string;
  text: string;
  is_correct: boolean;
  misconception: string | null;
  routes_to_scene: number;
}

interface DecisionPoint {
  decision_point_id: number;
  question_text: string;
  associated_introduction_scene_id: number;
  choices: Choice[];
}

interface Character {
  character_id: string;
  name: string;
  role: string;
  emotional_baseline: string;
  appearance: Record<string, string>;
}

interface Script {
  title: string;
  learning_goal: string;
  target_audience: string;
  total_duration_seconds: number;
  visual_style: string;
  characters: Character[];
  scenes: Scene[];
  decision_points: DecisionPoint[];
  [key: string]: unknown;
}

// ─── Small shared components ──────────────────────────────────────────────────

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-wide text-[#9b9590] mb-1.5">
      {children}
    </p>
  );
}

function EditArea({
  value,
  onChange,
  rows = 3,
  mono = false,
}: {
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  mono?: boolean;
}) {
  return (
    <textarea
      value={value}
      rows={rows}
      onChange={(e) => onChange(e.target.value)}
      className={`w-full rounded-xl border border-[#d8d5d0] bg-[#fafaf9] px-3.5 py-2.5 text-sm text-[#1a1a1a] leading-relaxed focus:outline-none focus:ring-2 focus:ring-[#F47C20] focus:border-[#F47C20] focus:bg-white resize-none transition-colors ${mono ? "font-mono text-xs" : ""}`}
    />
  );
}

function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`bg-white rounded-2xl border border-[#e8e6e3] shadow-sm p-6 ${className}`}>
      {children}
    </div>
  );
}

function SectionTitle({
  num,
  children,
}: {
  num?: number;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3 mb-5">
      {num !== undefined && (
        <span className="flex-shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white bg-[#F47C20]">
          {num}
        </span>
      )}
      <h2 className="text-base font-bold text-[#1a1a1a]">{children}</h2>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function ScriptReviewPage() {
  const router = useRouter();
  const [script, setScript] = useState<Script | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem("generated_script");
    if (raw) {
      try {
        setScript(JSON.parse(raw));
      } catch {
        setError("Could not parse the generated script. Please go back and regenerate.");
      }
    } else {
      setError("No script found. Please go back and generate one first.");
    }
  }, []);

  function updateTop(field: keyof Script, value: string) {
    setScript((prev) => prev ? { ...prev, [field]: value } : prev);
  }

  function updateCharacter(idx: number, field: keyof Character, value: string) {
    setScript((prev) => {
      if (!prev) return prev;
      const chars = prev.characters.map((c, i) =>
        i === idx ? { ...c, [field]: value } : c
      );
      return { ...prev, characters: chars };
    });
  }

  function updateScene(idx: number, field: keyof Scene, value: string) {
    setScript((prev) => {
      if (!prev) return prev;
      const scenes = prev.scenes.map((s, i) =>
        i === idx ? { ...s, [field]: value } : s
      );
      return { ...prev, scenes };
    });
  }

  function updateDialogue(sceneIdx: number, lineIdx: number, value: string) {
    setScript((prev) => {
      if (!prev) return prev;
      const scenes = prev.scenes.map((s, si) => {
        if (si !== sceneIdx) return s;
        const dialogue = s.audio.dialogue.map((d, di) =>
          di === lineIdx ? { ...d, line: value } : d
        );
        return { ...s, audio: { ...s.audio, dialogue } };
      });
      return { ...prev, scenes };
    });
  }

  function updateSceneAudio(sceneIdx: number, field: "sound_effects" | "ambience", value: string) {
    setScript((prev) => {
      if (!prev) return prev;
      const scenes = prev.scenes.map((s, si) =>
        si === sceneIdx ? { ...s, audio: { ...s.audio, [field]: value } } : s
      );
      return { ...prev, scenes };
    });
  }

  function updateDecisionQuestion(dpIdx: number, value: string) {
    setScript((prev) => {
      if (!prev) return prev;
      const decision_points = prev.decision_points.map((dp, i) =>
        i === dpIdx ? { ...dp, question_text: value } : dp
      );
      return { ...prev, decision_points };
    });
  }

  function updateChoice(dpIdx: number, cIdx: number, value: string) {
    setScript((prev) => {
      if (!prev) return prev;
      const decision_points = prev.decision_points.map((dp, i) => {
        if (i !== dpIdx) return dp;
        const choices = dp.choices.map((c, ci) =>
          ci === cIdx ? { ...c, text: value } : c
        );
        return { ...dp, choices };
      });
      return { ...prev, decision_points };
    });
  }

  async function handleSubmit() {
    if (!script) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitModifiedScript(script);
      setSubmitted(true);
      sessionStorage.setItem("modified_script", JSON.stringify(script));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  // ── Loading / error states ──
  if (error && !script) {
    return (
      <main className="min-h-screen flex items-center justify-center px-6">
        <div className="text-center">
          <p className="text-sm text-red-600 mb-4">{error}</p>
          <button
            onClick={() => router.push("/")}
            className="text-sm text-[#F47C20] hover:underline"
          >
            ← Back to setup
          </button>
        </div>
      </main>
    );
  }

  if (!script) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <svg className="animate-spin h-6 w-6 text-[#F47C20]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
      </main>
    );
  }

  return (
    <main className="min-h-screen pb-36 py-12 px-4 sm:px-6">
      <div className="max-w-3xl mx-auto">

        {/* Hero */}
        <div className="mb-10">
          <div className="inline-flex items-center gap-2 rounded-full bg-[#fff3e8] border border-[#fcd9b8] px-3.5 py-1.5 mb-5">
            <span className="w-2 h-2 rounded-full bg-[#F47C20]" />
            <span className="text-xs font-semibold text-[#b85e0e] tracking-wide uppercase">
              Step 2 of 3 — Review & Edit Script
            </span>
          </div>
          <h1 className="text-3xl font-bold text-[#1a1a1a] leading-snug tracking-tight">
            {script.title}
          </h1>
          <p className="mt-2 text-[15px] text-[#6b6560]">
            Review the generated script below. Edit any field, then submit to proceed to image frame generation.
          </p>
        </div>

        <div className="space-y-5">

          {/* 1. Overview */}
          <Card>
            <SectionTitle num={1}>Overview</SectionTitle>
            <div className="space-y-4">
              <div>
                <FieldLabel>Title</FieldLabel>
                <EditArea rows={1} value={script.title} onChange={(v) => updateTop("title", v)} />
              </div>
              <div>
                <FieldLabel>Learning Goal</FieldLabel>
                <EditArea rows={3} value={script.learning_goal} onChange={(v) => updateTop("learning_goal", v)} />
              </div>
              <div>
                <FieldLabel>Target Audience</FieldLabel>
                <EditArea rows={2} value={script.target_audience} onChange={(v) => updateTop("target_audience", v)} />
              </div>
            </div>
          </Card>

          {/* 2. Visual Style */}
          <Card>
            <SectionTitle num={2}>Visual Style</SectionTitle>
            <EditArea rows={4} value={script.visual_style} onChange={(v) => updateTop("visual_style", v)} />
          </Card>

          {/* 3. Characters */}
          <Card>
            <SectionTitle num={3}>Characters</SectionTitle>
            <div className="space-y-5">
              {script.characters.map((char, ci) => (
                <div key={char.character_id} className="rounded-xl border border-[#f0ede9] bg-[#fafaf9] p-4 space-y-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold text-[#F47C20] uppercase tracking-wide">
                      {char.character_id}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <FieldLabel>Name</FieldLabel>
                      <input
                        type="text"
                        value={char.name}
                        onChange={(e) => updateCharacter(ci, "name", e.target.value)}
                        className="w-full rounded-lg border border-[#d8d5d0] bg-white px-3 py-2 text-sm text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#F47C20] focus:border-[#F47C20] transition-colors"
                      />
                    </div>
                    <div>
                      <FieldLabel>Role</FieldLabel>
                      <input
                        type="text"
                        value={char.role}
                        onChange={(e) => updateCharacter(ci, "role", e.target.value)}
                        className="w-full rounded-lg border border-[#d8d5d0] bg-white px-3 py-2 text-sm text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#F47C20] focus:border-[#F47C20] transition-colors"
                      />
                    </div>
                  </div>
                  <div>
                    <FieldLabel>Emotional Baseline</FieldLabel>
                    <EditArea rows={2} value={char.emotional_baseline} onChange={(v) => updateCharacter(ci, "emotional_baseline", v)} />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* 4. Scenes */}
          <Card>
            <SectionTitle num={4}>Scenes</SectionTitle>
            <div className="space-y-6">
              {script.scenes.map((scene, si) => (
                <div key={scene.scene_id} className="rounded-xl border border-[#f0ede9] overflow-hidden">
                  {/* Scene header */}
                  <div className="flex items-center gap-3 px-4 py-3 bg-[#fafaf9] border-b border-[#f0ede9]">
                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white bg-[#F47C20] flex-shrink-0">
                      {scene.scene_id}
                    </span>
                    <span className="text-sm font-semibold text-[#1a1a1a] capitalize">{scene.type.replace(/-/g, " ")}</span>
                    <span className="ml-auto text-xs text-[#9b9590]">{scene.duration_seconds}s</span>
                  </div>

                  <div className="p-4 space-y-4">
                    <div>
                      <FieldLabel>Setting</FieldLabel>
                      <EditArea rows={3} value={scene.setting} onChange={(v) => updateScene(si, "setting", v)} />
                    </div>
                    <div>
                      <FieldLabel>Character Actions</FieldLabel>
                      <EditArea rows={2} value={scene.character_actions} onChange={(v) => updateScene(si, "character_actions", v)} />
                    </div>

                    {/* Dialogue */}
                    {scene.audio.dialogue.length > 0 && (
                      <div>
                        <FieldLabel>Dialogue</FieldLabel>
                        <div className="space-y-2">
                          {scene.audio.dialogue.map((line, li) => (
                            <div key={li} className="flex gap-2.5">
                              <span className="flex-shrink-0 mt-2.5 text-[11px] font-bold text-[#F47C20] uppercase w-20 truncate">
                                {line.character_id}
                              </span>
                              <div className="flex-1">
                                <EditArea rows={2} value={line.line} onChange={(v) => updateDialogue(si, li, v)} />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <FieldLabel>Sound Effects</FieldLabel>
                        <EditArea rows={2} value={scene.audio.sound_effects} onChange={(v) => updateSceneAudio(si, "sound_effects", v)} />
                      </div>
                      <div>
                        <FieldLabel>Ambience</FieldLabel>
                        <EditArea rows={2} value={scene.audio.ambience} onChange={(v) => updateSceneAudio(si, "ambience", v)} />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* 5. Decision Points */}
          {script.decision_points.length > 0 && (
            <Card>
              <SectionTitle num={5}>Decision Points</SectionTitle>
              <div className="space-y-6">
                {script.decision_points.map((dp, di) => (
                  <div key={dp.decision_point_id} className="rounded-xl border border-[#f0ede9] overflow-hidden">
                    <div className="px-4 py-3 bg-[#fafaf9] border-b border-[#f0ede9] flex items-center gap-2">
                      <span className="text-xs font-bold text-[#F47C20] uppercase tracking-wide">
                        Decision Point {dp.decision_point_id}
                      </span>
                      <span className="text-xs text-[#9b9590]">— after scene {dp.associated_introduction_scene_id}</span>
                    </div>
                    <div className="p-4 space-y-4">
                      <div>
                        <FieldLabel>Question</FieldLabel>
                        <EditArea rows={3} value={dp.question_text} onChange={(v) => updateDecisionQuestion(di, v)} />
                      </div>
                      <div>
                        <FieldLabel>Choices</FieldLabel>
                        <div className="space-y-2">
                          {dp.choices.map((choice, ci) => (
                            <div key={choice.choice_id} className="flex gap-2.5">
                              <span className={`flex-shrink-0 mt-2.5 inline-flex items-center justify-center w-5 h-5 rounded-full text-[11px] font-bold text-white ${choice.is_correct ? "bg-[#5eb146]" : "bg-red-400"}`}>
                                {choice.choice_id}
                              </span>
                              <div className="flex-1">
                                <EditArea rows={2} value={choice.text} onChange={(v) => updateChoice(di, ci, v)} />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

        </div>

        {/* Error */}
        {error && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

      </div>

      {/* Sticky submit bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-[#e8e6e3] px-4 sm:px-6 py-4 z-50">
        <div className="max-w-3xl mx-auto flex items-center justify-between gap-4">
          <button
            onClick={() => router.push("/")}
            className="text-sm text-[#6b6560] hover:text-[#F47C20] transition-colors"
          >
            ← Back to setup
          </button>

          {submitted ? (
            <div className="flex items-center gap-2 text-sm font-medium text-[#5eb146]">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M5 8l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Script submitted — proceeding to image generation
            </div>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className={`rounded-2xl px-8 py-3.5 text-[15px] font-semibold text-white transition-all shadow-sm ${
                submitting
                  ? "bg-[#F47C20] opacity-60 cursor-not-allowed"
                  : "bg-[#F47C20] hover:bg-[#d96a15] active:scale-[0.99] shadow-[0_2px_8px_rgba(244,124,32,0.30)]"
              }`}
            >
              {submitting ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                  Submitting…
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  Save & Continue to Image Generation
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M3 8h10M9 4l4 4-4 4" stroke="white" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </span>
              )}
            </button>
          )}
        </div>
      </div>
    </main>
  );
}

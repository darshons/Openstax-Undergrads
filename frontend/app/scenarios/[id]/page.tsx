"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { getScenario, saveScript, ScenarioDetail, Script, ScriptNode } from "@/lib/api";

function SceneCard({
  node,
  index,
  onScriptChange,
}: {
  node: ScriptNode;
  index: number;
  onScriptChange: (id: string, value: string) => void;
}) {
  return (
    <div className="bg-white rounded-xl border border-[#e0e0e0] shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#f0f0f0] bg-[#fafafa]">
        <div className="flex items-center gap-3 min-w-0">
          <span className="flex-shrink-0 inline-flex items-center justify-center h-7 w-7 rounded-full text-xs font-bold text-white bg-[#F47C20]">
            {index + 1}
          </span>
          <div className="min-w-0">
            <h3 className="font-semibold text-[#1a1a1a] text-sm truncate">
              {node.title || `Scene ${index + 1}`}
            </h3>
            {node.video_prompt && (
              <p className="text-xs text-[#9b9b9b] mt-0.5 truncate">
                {node.video_prompt}
              </p>
            )}
          </div>
          {node.is_endpoint && (
            <span className="flex-shrink-0 rounded-full bg-[#edf7e8] text-[#3a8a2a] text-xs font-medium px-2.5 py-0.5">
              Endpoint
            </span>
          )}
        </div>
        {node.choices.length > 0 && (
          <span className="flex-shrink-0 text-xs text-[#9b9b9b] ml-4">
            {node.choices.length} choice{node.choices.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Script */}
      <div className="px-6 py-5">
        <label className="block text-xs font-semibold text-[#6b6b6b] uppercase tracking-wide mb-2">
          Scene Script
        </label>
        <textarea
          value={node.script}
          onChange={(e) => onScriptChange(node.id, e.target.value)}
          rows={5}
          className="w-full rounded-lg border border-[#d0d0d0] px-4 py-3 text-sm text-[#1a1a1a] leading-relaxed placeholder-[#b0b0b0] focus:outline-none focus:ring-2 focus:ring-[#F47C20] focus:border-[#F47C20] resize-none transition-colors"
          placeholder="Scene narration or dialogue…"
        />
      </div>

      {/* Choices */}
      {node.choices.length > 0 && (
        <div className="px-6 pb-5 border-t border-[#f0f0f0] pt-4">
          <p className="text-xs font-semibold text-[#6b6b6b] uppercase tracking-wide mb-3">
            Branching Choices
          </p>
          <ul className="space-y-3">
            {node.choices.map((choice, i) => (
              <li key={choice.id} className="flex items-start gap-3">
                <span
                  className={`flex-shrink-0 inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold text-white mt-0.5 ${
                    choice.is_misconception ? "bg-red-400" : "bg-[#5eb146]"
                  }`}
                >
                  {String.fromCharCode(65 + i)}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-[#2d2d2d] leading-snug">{choice.text}</p>
                  {choice.feedback && (
                    <p className="text-xs text-[#9b9b9b] mt-0.5 italic">{choice.feedback}</p>
                  )}
                  {choice.is_misconception && (
                    <span className="text-xs text-red-500 font-medium">misconception branch</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function ScenarioEditor() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [scenario, setScenario] = useState<ScenarioDetail | null>(null);
  const [localScript, setLocalScript] = useState<Script | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getScenario(id)
      .then((s) => {
        setScenario(s);
        if (s.script) setLocalScript(s.script);
      })
      .catch((e) => setFetchError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  function handleScriptChange(nodeId: string, value: string) {
    setLocalScript((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        nodes: prev.nodes.map((n) => (n.id === nodeId ? { ...n, script: value } : n)),
      };
    });
  }

  async function handleSave() {
    if (!localScript || !scenario) return;
    setSaving(true);
    setSaveError(null);
    try {
      await saveScript(scenario.id, localScript);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-[#6b6b6b]">
          <svg
            className="animate-spin h-7 w-7 text-[#F47C20]"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          <p className="text-sm">Generating scenario…</p>
        </div>
      </main>
    );
  }

  if (fetchError || !scenario) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 text-sm mb-3">{fetchError ?? "Scenario not found."}</p>
          <button onClick={() => router.push("/")} className="text-sm text-[#F47C20] hover:underline">
            ← Back to setup
          </button>
        </div>
      </main>
    );
  }

  const nodes = localScript?.nodes ?? [];

  return (
    <main className="min-h-screen py-10 px-6">
      <div className="max-w-3xl mx-auto">
        {/* Top bar: breadcrumb + save */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => router.push("/")}
              className="text-sm text-[#F47C20] hover:underline"
            >
              ← Back
            </button>
            <span className="text-[#d0d0d0]">·</span>
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white bg-[#F47C20]">
              2
            </span>
            <span className="text-sm text-[#6b6b6b]">Step 2 of 3 — Review &amp; Edit Script</span>
          </div>

          <div className="flex items-center gap-3">
            {saveSuccess && <span className="text-sm text-[#5eb146] font-medium">Saved!</span>}
            {saveError && <span className="text-sm text-red-500">{saveError}</span>}
            {localScript && (
              <button
                onClick={handleSave}
                disabled={saving}
                className="rounded-lg border border-[#d0d0d0] bg-white px-4 py-2 text-sm font-medium text-[#2d2d2d] hover:border-[#F47C20] hover:text-[#F47C20] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {saving ? "Saving…" : "Save Changes"}
              </button>
            )}
          </div>
        </div>

        {/* Page heading */}
        <div className="mb-7">
          <h1 className="text-[1.5rem] font-bold text-[#1a1a1a] leading-tight">
            {localScript?.title ?? scenario.chapter_reference}
          </h1>
          <p className="mt-1 text-sm text-[#6b6b6b]">
            {nodes.length} scene{nodes.length !== 1 ? "s" : ""} — edit each scene below, then save your changes.
          </p>
        </div>

        {/* Scene cards */}
        <div className="space-y-5">
          {nodes.map((node, i) => (
            <SceneCard
              key={node.id}
              node={node}
              index={i}
              onScriptChange={handleScriptChange}
            />
          ))}
        </div>

        {/* Continue CTA */}
        <div className="mt-12 pt-8 border-t border-[#e0e0e0]">
          <div className="bg-white rounded-xl border border-[#e0e0e0] shadow-sm px-8 py-8 text-center">
            <h2 className="text-lg font-semibold text-[#1a1a1a] mb-1">
              Ready to generate videos?
            </h2>
            <p className="text-sm text-[#6b6b6b] mb-6">
              Save your changes and continue to the video generation step.
            </p>
            <button
              onClick={async () => {
                await handleSave();
                alert("Video generation — coming soon.");
              }}
              className="rounded-xl bg-[#5eb146] hover:bg-[#4d9a38] px-8 py-3.5 text-base font-semibold text-white transition-colors shadow-sm active:scale-[0.99]"
            >
              Save &amp; Continue to Video Generation →
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { generateScenario } from "@/lib/api";

const TEXTBOOKS = ["Clinical Nursing", "Anatomy & Physiology"] as const;
type Textbook = (typeof TEXTBOOKS)[number];

const TEXTBOOK_UNITS: Record<Textbook, string[]> = {
  "Clinical Nursing": [
    "Unit I — Foundations of Practice",
    "Unit II — Health Assessment",
    "Unit III — Clinical Interventions",
    "Unit IV — Specialty Care",
  ],
  "Anatomy & Physiology": [
    "Unit I — Cells & Tissues",
    "Unit II — Support & Movement",
    "Unit III — Regulation & Integration",
    "Unit IV — Fluid & Homeostasis",
  ],
};

const CHAPTERS_BY_UNIT: Record<string, string[]> = {
  "Unit I — Foundations of Practice": [
    "Ch 1 — Patient Assessment",
    "Ch 2 — Medication Administration",
  ],
  "Unit II — Health Assessment": [
    "Ch 3 — Respiratory Care",
    "Ch 4 — Cardiac Monitoring",
  ],
  "Unit III — Clinical Interventions": [
    "Ch 5 — Wound Management",
    "Ch 6 — IV Therapy",
  ],
  "Unit IV — Specialty Care": [
    "Ch 7 — Pediatric Nursing",
    "Ch 8 — Critical Care",
  ],
  "Unit I — Cells & Tissues": [
    "Ch 1 — Cell Biology",
    "Ch 2 — Tissue Types",
  ],
  "Unit II — Support & Movement": [
    "Ch 3 — Skeletal System",
    "Ch 4 — Muscular System",
  ],
  "Unit III — Regulation & Integration": [
    "Ch 5 — Nervous System",
    "Ch 6 — Endocrine System",
  ],
  "Unit IV — Fluid & Homeostasis": [
    "Ch 7 — Cardiovascular System",
    "Ch 8 — Renal System",
  ],
};

const MAX_CHAPTERS = 3;

function SectionLabel({
  title,
  required,
  count,
  cap,
}: {
  title: string;
  required?: boolean;
  count?: number;
  cap?: number;
}) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-[#1a1a1a]">{title}</span>
        {required ? (
          <span className="text-[10px] font-semibold uppercase tracking-wide text-[#b85e0e] bg-[#fff3e8] border border-[#fcd9b8] rounded-full px-2 py-0.5">
            Required
          </span>
        ) : (
          <span className="text-[10px] font-semibold uppercase tracking-wide text-[#6b6560] bg-[#f3f1ee] border border-[#e0ddd9] rounded-full px-2 py-0.5">
            Optional
          </span>
        )}
      </div>
      {cap !== undefined && count !== undefined && (
        <span className={`text-xs font-medium tabular-nums ${count >= cap ? "text-[#F47C20]" : "text-[#9b9590]"}`}>
          {count}/{cap} selected
        </span>
      )}
    </div>
  );
}

export default function GenerationSetup() {
  const router = useRouter();
  const [textbook, setTextbook] = useState<Textbook>("Clinical Nursing");
  const [selectedUnits, setSelectedUnits] = useState<string[]>([]);
  const [useAllUnits, setUseAllUnits] = useState(true);
  const [selectedChapters, setSelectedChapters] = useState<string[]>([]);
  const [pageNumbers, setPageNumbers] = useState("");
  const [description, setDescription] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const availableChapters = useAllUnits
    ? TEXTBOOK_UNITS[textbook].flatMap((u) => CHAPTERS_BY_UNIT[u] ?? [])
    : selectedUnits.flatMap((u) => CHAPTERS_BY_UNIT[u] ?? []);

  function toggleUnit(unit: string) {
    setSelectedUnits((prev) => {
      const next = prev.includes(unit) ? prev.filter((u) => u !== unit) : [...prev, unit];
      // drop chapters that no longer belong to selected units
      const validChapters = next.flatMap((u) => CHAPTERS_BY_UNIT[u] ?? []);
      setSelectedChapters((ch) => ch.filter((c) => validChapters.includes(c)));
      return next;
    });
  }

  function toggleChapter(chapter: string) {
    setSelectedChapters((prev) => {
      if (prev.includes(chapter)) return prev.filter((c) => c !== chapter);
      if (prev.length >= MAX_CHAPTERS) return prev;
      return [...prev, chapter];
    });
  }

  function handleTextbookChange(tb: Textbook) {
    setTextbook(tb);
    setSelectedUnits([]);
    setUseAllUnits(true);
    setSelectedChapters([]);
  }

  const unitValue = useAllUnits
    ? "All Units"
    : selectedUnits.length > 0
    ? selectedUnits.join(", ")
    : "All Units";

  const canSubmit =
    description.trim().length > 0 &&
    (useAllUnits || selectedUnits.length > 0) &&
    !generating;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    setGenerating(true);
    setError(null);
    try {
      const { scenario_id } = await generateScenario({
        textbook,
        chapters: selectedChapters,
        units: unitValue,
        description: description.trim(),
      });
      router.push(`/scenarios/${scenario_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed. Please try again.");
      setGenerating(false);
    }
  }

  return (
    <main className="min-h-screen py-12 px-4 sm:px-6">
      <div className="max-w-2xl mx-auto">

        {/* Hero */}
        <div className="mb-10">
          <div className="inline-flex items-center gap-2 rounded-full bg-[#fff3e8] border border-[#fcd9b8] px-3.5 py-1.5 mb-5">
            <span className="w-2 h-2 rounded-full bg-[#F47C20] animate-pulse" />
            <span className="text-xs font-semibold text-[#b85e0e] tracking-wide uppercase">
              Step 1 of 3 — Configure
            </span>
          </div>
          <h1 className="text-3xl font-bold text-[#1a1a1a] leading-snug tracking-tight">
            Generate a Clinical Scenario
          </h1>
          <p className="mt-2.5 text-[15px] text-[#6b6560] leading-relaxed max-w-lg">
            Select your textbook content and describe the scenario. We&apos;ll parse
            the material and use Claude to generate a branching script.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">

          {/* 1. Textbook — required */}
          <div className="bg-white rounded-2xl border border-[#e8e6e3] shadow-sm p-6">
            <SectionLabel title="Textbook" required />
            <div className="flex flex-wrap gap-2.5">
              {TEXTBOOKS.map((tb) => (
                <button
                  key={tb}
                  type="button"
                  onClick={() => handleTextbookChange(tb)}
                  className={`rounded-xl px-4 py-2.5 text-sm font-medium border transition-all ${
                    textbook === tb
                      ? "bg-[#F47C20] border-[#F47C20] text-white shadow-sm"
                      : "bg-white border-[#d8d5d0] text-[#4a4540] hover:border-[#F47C20] hover:text-[#F47C20]"
                  }`}
                >
                  {tb}
                </button>
              ))}
            </div>
          </div>

          {/* 2. Units — required */}
          <div className="bg-white rounded-2xl border border-[#e8e6e3] shadow-sm p-6">
            <SectionLabel title="Units" required />

            {/* All Units toggle */}
            <div className="flex gap-2 mb-4">
              <button
                type="button"
                onClick={() => { setUseAllUnits(true); setSelectedUnits([]); }}
                className={`rounded-lg px-3.5 py-2 text-sm border transition-all ${
                  useAllUnits
                    ? "bg-[#F47C20] border-[#F47C20] text-white font-medium"
                    : "bg-white border-[#d8d5d0] text-[#4a4540] hover:border-[#F47C20] hover:text-[#F47C20]"
                }`}
              >
                All Units
              </button>
              <button
                type="button"
                onClick={() => setUseAllUnits(false)}
                className={`rounded-lg px-3.5 py-2 text-sm border transition-all ${
                  !useAllUnits
                    ? "bg-[#F47C20] border-[#F47C20] text-white font-medium"
                    : "bg-white border-[#d8d5d0] text-[#4a4540] hover:border-[#F47C20] hover:text-[#F47C20]"
                }`}
              >
                Specific Units
              </button>
            </div>

            {/* Specific unit chips */}
            {!useAllUnits && (
              <div className="flex flex-wrap gap-2 pt-3 border-t border-[#f0ede9]">
                {TEXTBOOK_UNITS[textbook].map((unit) => {
                  const active = selectedUnits.includes(unit);
                  return (
                    <button
                      key={unit}
                      type="button"
                      onClick={() => toggleUnit(unit)}
                      className={`rounded-lg px-3.5 py-2 text-sm border transition-all ${
                        active
                          ? "bg-[#fff3e8] border-[#F47C20] text-[#b85e0e] font-medium"
                          : "bg-white border-[#d8d5d0] text-[#4a4540] hover:border-[#F47C20] hover:text-[#F47C20]"
                      }`}
                    >
                      {active && <span className="mr-1.5 text-[#F47C20]">✓</span>}
                      {unit}
                    </button>
                  );
                })}
              </div>
            )}

            {!useAllUnits && selectedUnits.length === 0 && (
              <p className="mt-2 text-xs text-[#b85e0e] flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.5"/>
                  <path d="M6 4v2.5M6 8h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
                Select at least one unit to continue.
              </p>
            )}
          </div>

          {/* 3. Chapters — optional */}
          <div className="bg-white rounded-2xl border border-[#e8e6e3] shadow-sm p-6">
            <SectionLabel
              title="Chapters"
              count={selectedChapters.length}
              cap={MAX_CHAPTERS}
            />
            <div className="flex flex-wrap gap-2">
              {availableChapters.map((chapter) => {
                const checked = selectedChapters.includes(chapter);
                const atCap = !checked && selectedChapters.length >= MAX_CHAPTERS;
                return (
                  <button
                    key={chapter}
                    type="button"
                    disabled={atCap}
                    onClick={() => toggleChapter(chapter)}
                    className={`rounded-lg px-3.5 py-2 text-sm border transition-all ${
                      checked
                        ? "bg-[#fff3e8] border-[#F47C20] text-[#b85e0e] font-medium"
                        : atCap
                        ? "bg-[#fafaf9] border-[#e8e6e3] text-[#c0bcb8] cursor-not-allowed"
                        : "bg-white border-[#d8d5d0] text-[#4a4540] hover:border-[#F47C20] hover:text-[#F47C20]"
                    }`}
                  >
                    {checked && <span className="mr-1.5 text-[#F47C20]">✓</span>}
                    {chapter}
                  </button>
                );
              })}
            </div>
            {selectedChapters.length === MAX_CHAPTERS && (
              <p className="mt-3 text-xs text-[#b85e0e] flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.5"/>
                  <path d="M6 4v2.5M6 8h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
                Cap reached — deselect a chapter to swap.
              </p>
            )}
          </div>

          {/* 4. Page Numbers — optional */}
          <div className="bg-white rounded-2xl border border-[#e8e6e3] shadow-sm p-6">
            <SectionLabel title="Page Numbers" />
            <input
              type="text"
              value={pageNumbers}
              onChange={(e) => setPageNumbers(e.target.value)}
              placeholder="e.g. 42–56, 78–90, 110"
              className="w-full rounded-xl border border-[#d8d5d0] bg-[#fafaf9] px-4 py-2.5 text-sm text-[#1a1a1a] placeholder-[#b0aba6] focus:outline-none focus:ring-2 focus:ring-[#F47C20] focus:border-[#F47C20] focus:bg-white transition-colors"
            />
            <p className="mt-2 text-xs text-[#9b9590]">
              Narrow the content to specific page ranges within the selected material.
            </p>
          </div>

          {/* 5. Description */}
          <div className="bg-white rounded-2xl border border-[#e8e6e3] shadow-sm p-6">
            <div className="flex items-center gap-2 mb-1.5">
              <label htmlFor="description" className="text-sm font-semibold text-[#1a1a1a]">
                Scenario Description
              </label>
              <span className="text-[10px] font-semibold uppercase tracking-wide text-[#b85e0e] bg-[#fff3e8] border border-[#fcd9b8] rounded-full px-2 py-0.5">
                Required
              </span>
            </div>
            <p className="text-xs text-[#9b9590] mb-3">
              Describe the patient, clinical situation, and learning objectives.
            </p>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
              placeholder="e.g. A 68-year-old patient presents with sudden chest pain and shortness of breath. The learner must assess and triage a suspected STEMI while coordinating with the care team."
              className="w-full rounded-xl border border-[#d8d5d0] bg-[#fafaf9] px-4 py-3 text-sm text-[#1a1a1a] placeholder-[#b0aba6] leading-relaxed focus:outline-none focus:ring-2 focus:ring-[#F47C20] focus:border-[#F47C20] focus:bg-white resize-none transition-colors"
            />
            <div className="mt-2 flex justify-end">
              <span className={`text-xs tabular-nums ${description.length > 0 ? "text-[#9b9590]" : "text-transparent"}`}>
                {description.length} chars
              </span>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3.5 text-sm text-red-700 flex items-start gap-2.5">
              <svg className="flex-shrink-0 mt-0.5 w-4 h-4" fill="none" viewBox="0 0 16 16">
                <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M8 5v3.5M8 10.5h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={!canSubmit}
            className={`w-full rounded-2xl px-6 py-4 text-[15px] font-semibold text-white transition-all shadow-sm ${
              canSubmit
                ? "bg-[#F47C20] hover:bg-[#d96a15] active:scale-[0.99] shadow-[0_2px_8px_rgba(244,124,32,0.30)]"
                : "bg-[#F47C20] opacity-40 cursor-not-allowed"
            }`}
          >
            {generating ? (
              <span className="flex items-center justify-center gap-2.5">
                <svg className="animate-spin h-4 w-4 text-white flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                Parsing content &amp; generating script…
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                Generate Script
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M3 8h10M9 4l4 4-4 4" stroke="white" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </span>
            )}
          </button>

          {generating && (
            <p className="text-center text-xs text-[#9b9590]">
              This may take 20–30 seconds while content is parsed and the script is generated.
            </p>
          )}
        </form>
      </div>
    </main>
  );
}

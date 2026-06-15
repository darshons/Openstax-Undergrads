"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { generateScenario } from "@/lib/api";

const TEXTBOOKS: { label: string; slug: string }[] = [
  { label: "Fundamentals of Nursing",    slug: "fundamentals-nursing" },
  { label: "Clinical Nursing Skills",    slug: "clinical-nursing-skills" },
  { label: "Medical-Surgical Nursing",   slug: "medical-surgical-nursing" },
  { label: "Anatomy and Physiology 2e",  slug: "anatomy-and-physiology-2e" },
  { label: "University Physics Vol. 1",  slug: "university-physics-volume-1" },
];

function SectionLabel({
  title,
  required,
}: {
  title: string;
  required?: boolean;
}) {
  return (
    <div className="flex items-center gap-2 mb-3">
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
  );
}

function NumberInput({
  id,
  value,
  onChange,
  placeholder,
  min = 1,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  min?: number;
}) {
  return (
    <div className="flex items-center gap-2 w-36">
      <button
        type="button"
        onClick={() => {
          const n = parseInt(value) || 0;
          if (n > min) onChange(String(n - 1));
        }}
        className="flex-shrink-0 w-8 h-8 rounded-lg border border-[#d8d5d0] bg-white text-[#4a4540] text-lg font-medium hover:border-[#F47C20] hover:text-[#F47C20] transition-colors flex items-center justify-center"
      >
        −
      </button>
      <input
        id={id}
        type="number"
        min={min}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-16 text-center rounded-lg border border-[#d8d5d0] bg-[#fafaf9] px-2 py-1.5 text-sm text-[#1a1a1a] placeholder-[#b0aba6] focus:outline-none focus:ring-2 focus:ring-[#F47C20] focus:border-[#F47C20] focus:bg-white transition-colors [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
      />
      <button
        type="button"
        onClick={() => {
          const n = parseInt(value) || 0;
          onChange(String(n + 1));
        }}
        className="flex-shrink-0 w-8 h-8 rounded-lg border border-[#d8d5d0] bg-white text-[#4a4540] text-lg font-medium hover:border-[#F47C20] hover:text-[#F47C20] transition-colors flex items-center justify-center"
      >
        +
      </button>
    </div>
  );
}

export default function GenerationSetup() {
  const router = useRouter();
  const [textbook, setTextbook] = useState(TEXTBOOKS[0]);
  const [unitNum, setUnitNum] = useState("1");
  const [chapterNum, setChapterNum] = useState("");
  const [pageNum, setPageNum] = useState("");
  const [aiModel, setAiModel] = useState<"anthropic" | "gemini">("anthropic");
  const [description, setDescription] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit =
    description.trim().length > 0 &&
    unitNum.trim().length > 0 &&
    parseInt(unitNum) >= 1 &&
    !generating;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    setGenerating(true);
    setError(null);
    try {
      const result = await generateScenario({
        book_title: textbook.slug,
        unit_num: parseInt(unitNum),
        chapter_num: chapterNum ? parseInt(chapterNum) : undefined,
        page_num: pageNum.trim() || undefined,
        user_query: description.trim(),
        model_choice: aiModel,
      });
      sessionStorage.setItem("generated_script", JSON.stringify(result.script));
      router.push("/scenarios/result");
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

          {/* 1. Textbook */}
          <div className="bg-white rounded-2xl border border-[#e8e6e3] shadow-sm p-6">
            <SectionLabel title="Textbook" required />
            <div className="flex flex-wrap gap-2.5">
              {TEXTBOOKS.map((tb) => (
                <button
                  key={tb.slug}
                  type="button"
                  onClick={() => setTextbook(tb)}
                  className={`rounded-xl px-4 py-2.5 text-sm font-medium border transition-all ${
                    textbook.slug === tb.slug
                      ? "bg-[#F47C20] border-[#F47C20] text-white shadow-sm"
                      : "bg-white border-[#d8d5d0] text-[#4a4540] hover:border-[#F47C20] hover:text-[#F47C20]"
                  }`}
                >
                  {tb.label}
                </button>
              ))}
            </div>
          </div>

          {/* 2. Unit — required */}
          <div className="bg-white rounded-2xl border border-[#e8e6e3] shadow-sm p-6">
            <SectionLabel title="Unit Number" required />
            <NumberInput
              id="unit_num"
              value={unitNum}
              onChange={setUnitNum}
              placeholder="1"
            />
          </div>

          {/* 3. Chapter — optional */}
          <div className="bg-white rounded-2xl border border-[#e8e6e3] shadow-sm p-6">
            <SectionLabel title="Chapter Number" />
            <NumberInput
              id="chapter_num"
              value={chapterNum}
              onChange={setChapterNum}
              placeholder="—"
            />
            {chapterNum && (
              <button
                type="button"
                onClick={() => { setChapterNum(""); setPageNum(""); }}
                className="mt-2.5 text-xs text-[#9b9590] hover:text-[#F47C20] transition-colors"
              >
                Clear
              </button>
            )}
          </div>

          {/* 4. Page — optional, only meaningful with a chapter */}
          <div className={`bg-white rounded-2xl border shadow-sm p-6 transition-opacity ${
            chapterNum ? "border-[#e8e6e3] opacity-100" : "border-[#f0ede9] opacity-50 pointer-events-none"
          }`}>
            <SectionLabel title="Page / Section Number" />
            <input
              type="text"
              value={pageNum}
              onChange={(e) => setPageNum(e.target.value)}
              placeholder="e.g. 2.1"
              disabled={!chapterNum}
              className="w-36 rounded-xl border border-[#d8d5d0] bg-[#fafaf9] px-4 py-2.5 text-sm text-[#1a1a1a] placeholder-[#b0aba6] focus:outline-none focus:ring-2 focus:ring-[#F47C20] focus:border-[#F47C20] focus:bg-white transition-colors"
            />
            <p className="mt-2 text-xs text-[#9b9590]">
              Narrow to a specific section within the chapter (e.g. <span className="font-mono">2.1</span>).
            </p>
          </div>

          {/* 5. AI Model */}
          <div className="bg-white rounded-2xl border border-[#e8e6e3] shadow-sm p-6">
            <SectionLabel title="AI Model" required />
            <div className="flex flex-wrap gap-2.5">
              {(
                [
                  { id: "anthropic" as const, label: "Anthropic Claude", sub: "claude-sonnet-4-6" },
                  { id: "gemini" as const, label: "Google Gemini", sub: "gemini-2.0-flash" },
                ] as const
              ).map(({ id, label, sub }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setAiModel(id)}
                  className={`flex items-center gap-3 rounded-xl px-4 py-3 border transition-all text-left ${
                    aiModel === id
                      ? "bg-[#F47C20] border-[#F47C20] text-white shadow-sm"
                      : "bg-white border-[#d8d5d0] text-[#4a4540] hover:border-[#F47C20] hover:text-[#F47C20]"
                  }`}
                >
                  <span className="flex flex-col">
                    <span className="text-sm font-semibold leading-tight">{label}</span>
                    <span className={`text-[11px] font-mono mt-0.5 ${aiModel === id ? "text-orange-100" : "text-[#9b9590]"}`}>
                      {sub}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* 6. Description */}
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

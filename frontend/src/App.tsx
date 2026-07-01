import { useState, useCallback } from 'react';
import type {
  Script,
  Scene,
  Character,
  DecisionPoint,
  Page,
  ViewMode,
  ModelChoice,
  VideoType,
} from './types/script';
import { fetchInitialScript } from './lib/api';
import { buildGenerateRequest } from './data/catalog';

// ── State ──────────────────────────────────────────────────────────────────

export default function App() {
  const [script, setScript] = useState<Script | null>(null);
  const [deleteUndoStack, setDeleteUndoStack] = useState<Script[]>([]);

  const [busy, setBusy] = useState(false);
  const [genStep, setGenStep] = useState(0);
  const [genError, setGenError] = useState<string | null>(null);

  const [zoom, setZoom] = useState(70);
  const [viewMode, setViewMode] = useState<ViewMode>('full');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [currentPage, setCurrentPage] = useState<Page>('script');

  const [editingSceneIdx, setEditingSceneIdx] = useState<number | null>(null);
  const [editingCharacterIdx, setEditingCharacterIdx] = useState<number | null>(null);

  const [selected, setSelected] = useState<Set<string>>(
    new Set(['clinicalnursing:03:3.1']),
  );
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('All');

  const [model, setModel] = useState<ModelChoice>('anthropic');
  const [videoType, setVideoType] = useState<VideoType>('scenario');
  const [userQuery, setUserQuery] = useState('');

  // ── Source-selection mutations ──────────────────────────────────────────

  const toggleSec = useCallback((id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  const removeSec = useCallback((id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, []);

  const toggleChap = useCallback((bookId: string, chapN: string, secNs: string[]) => {
    const ids = secNs.map(n => `${bookId}:${chapN}:${n}`);
    setSelected(prev => {
      const next = new Set(prev);
      const allOn = ids.every(id => next.has(id));
      ids.forEach(id => (allOn ? next.delete(id) : next.add(id)));
      return next;
    });
  }, []);

  // ── Script mutations ────────────────────────────────────────────────────

  const updateScriptField = useCallback(
    <K extends keyof Script>(key: K, value: Script[K]) => {
      setScript(curr => (curr ? { ...curr, [key]: value } : curr));
    },
    [],
  );

  const saveSceneEdit = useCallback((idx: number, draft: Scene) => {
    setScript(curr =>
      curr ? { ...curr, scenes: curr.scenes.map((s, i) => (i === idx ? draft : s)) } : curr,
    );
    setEditingSceneIdx(null);
  }, []);

  const deleteScene = useCallback(
    (idx: number) => {
      if (!script) return;
      setDeleteUndoStack(prev => [...prev, script]);
      setScript(curr =>
        curr ? { ...curr, scenes: curr.scenes.filter((_, i) => i !== idx) } : curr,
      );
      if (editingSceneIdx === idx) setEditingSceneIdx(null);
    },
    [script, editingSceneIdx],
  );

  const undoDelete = useCallback(() => {
    setDeleteUndoStack(prev => {
      if (prev.length === 0) return prev;
      setScript(prev[prev.length - 1]);
      return prev.slice(0, -1);
    });
  }, []);

  const moveScene = useCallback((fromIdx: number, toIdx: number) => {
    setScript(curr => {
      if (!curr) return curr;
      const scenes = [...curr.scenes];
      [scenes[fromIdx], scenes[toIdx]] = [scenes[toIdx], scenes[fromIdx]];
      return { ...curr, scenes };
    });
  }, []);

  const saveCharacterEdit = useCallback((idx: number, draft: Character) => {
    setScript(curr =>
      curr
        ? { ...curr, characters: curr.characters.map((c, i) => (i === idx ? draft : c)) }
        : curr,
    );
    setEditingCharacterIdx(null);
  }, []);

  const updateDecisionPoint = useCallback((idx: number, dp: DecisionPoint) => {
    setScript(curr =>
      curr
        ? { ...curr, decision_points: curr.decision_points.map((d, i) => (i === idx ? dp : d)) }
        : curr,
    );
  }, []);

  const addDecisionPoint = useCallback((sceneIdx: number) => {
    setScript(curr => {
      if (!curr) return curr;
      const dps = curr.decision_points ?? [];
      const newId = dps.length > 0 ? Math.max(...dps.map(d => d.decision_point_id)) + 1 : 1;
      const scene = curr.scenes[sceneIdx];
      const newDP: DecisionPoint = {
        decision_point_id: newId,
        question_text: 'What should the nurse do next?',
        associated_introduction_scene_id: scene.scene_id,
        choices: [
          { choice_id: 'A', text: 'Choice A', is_correct: true,  routes_to_scene: null, misconception: '' },
          { choice_id: 'B', text: 'Choice B', is_correct: false, routes_to_scene: null, misconception: '' },
          { choice_id: 'C', text: 'Choice C', is_correct: false, routes_to_scene: null, misconception: '' },
        ],
      };
      const updatedScenes = curr.scenes.map((s, i) =>
        i === sceneIdx
          ? { ...s, routes_to: { type: 'true_choice' as const, decision_point_id: newId } }
          : s,
      );
      return { ...curr, scenes: updatedScenes, decision_points: [...dps, newDP] };
    });
  }, []);

  // ── Generation ──────────────────────────────────────────────────────────

  const runGenerate = useCallback(async () => {
    const req = buildGenerateRequest({ selected, model, videoType, userQuery: userQuery.trim() });
    if (!req) {
      setGenError('Pick at least one section from a known textbook.');
      return;
    }
    setGenError(null);
    setBusy(true);
    setGenStep(0);
    setScript(null);
    setDeleteUndoStack([]);
    setEditingSceneIdx(null);
    setEditingCharacterIdx(null);

    const stepper = setInterval(() => {
      setGenStep(s => Math.min(s + 1, 3));
    }, 900);

    try {
      const result = await fetchInitialScript(req);
      clearInterval(stepper);
      setGenStep(4);
      setScript(result);
    } catch (err) {
      clearInterval(stepper);
      setGenError(err instanceof Error ? err.message : 'Generation failed');
    } finally {
      setBusy(false);
    }
  }, [selected, model, videoType, userQuery]);

  // ── Derived display values ──────────────────────────────────────────────

  const sceneCount = script?.scenes.length ?? 0;
  const totalSecs = script?.total_duration_seconds ?? 0;
  const runtimeLabel = totalSecs
    ? `${Math.floor(totalSecs / 60)}m ${totalSecs % 60}s`
    : '—';

  const statusClass =
    busy   ? 'bg-[#fde7d8] text-[#a04412]' :
    script ? 'bg-[#eef7df] text-[#4d6e1d]' :
             'bg-[var(--os-bg-3)] text-[var(--os-ink-2)]';

  const statusDotClass =
    busy   ? 'bg-[var(--os-orange)] [animation:pulse_1.2s_ease-in-out_infinite]' :
    script ? 'bg-[var(--os-green)] [box-shadow:0_0_0_3px_rgba(156,203,59,.2)]' :
             'bg-[var(--os-ink-3)]';

  const statusLabel = busy ? 'Generating' : script ? 'Draft ready' : 'Idle';

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="grid grid-rows-[auto_1fr] h-screen">

      {/* ── Topbar ─────────────────────────────────────────────────────── */}
      <header
        className="flex items-center justify-between px-[18px] bg-white border-b border-[var(--os-line)] z-[5]"
        style={{ zoom: 0.78 }}
      >
        {/* Brand */}
        <div className="flex items-center gap-[14px]">
          <div className="flex flex-col gap-[3px]" aria-hidden>
            <span className="block h-[3px] rounded-sm w-[22px] ml-[6px]  bg-[var(--os-green)]" />
            <span className="block h-[3px] rounded-sm w-[28px]           bg-[var(--os-orange)]" />
            <span className="block h-[3px] rounded-sm w-[24px] ml-[3px]  bg-[var(--os-gray)]" />
            <span className="block h-[3px] rounded-sm w-[20px] ml-[8px]  bg-[var(--os-yellow)]" />
            <span className="block h-[3px] rounded-sm w-[26px] ml-[1px]  bg-[var(--os-navy)]" />
          </div>
          <div className="font-black text-[15px] text-[var(--os-navy)] tracking-[-0.01em]">
            open<em className="not-italic font-light">stax</em>
          </div>
          <div className="w-px h-6 bg-[var(--os-line)]" />
          <div className="text-[12px] text-[var(--os-ink-2)] font-medium tracking-[0.01em]">
            <b className="text-[var(--os-ink)] font-bold">Scenario Studio</b> · Internal
          </div>
        </div>

        {/* Breadcrumb + avatar */}
        <div className="flex items-center gap-2 text-[12px] text-[var(--os-ink-2)]">
          <div className="flex items-center gap-2">
            <span
              className="w-1.5 h-1.5 rounded-full bg-[var(--os-green)]"
              style={{ boxShadow: '0 0 0 3px rgba(156,203,59,.22)' }}
            />
            <span>
              Project · <b className="text-[var(--os-ink)] font-bold">
                {script?.title ?? 'Untitled scenario'}
              </b>
            </span>
          </div>
          <div
            className="w-[30px] h-[30px] rounded-full text-white text-[11px] font-bold flex items-center justify-center tracking-[0.02em]"
            style={{ background: 'linear-gradient(135deg,#002569 0%,#1a4dbf 100%)' }}
          >
            MR
          </div>
        </div>
      </header>

      {/* ── Page area ──────────────────────────────────────────────────── */}
      <div className="min-h-0 overflow-hidden">

        {currentPage === 'assets' && script && (
          <div className="h-full flex items-center justify-center bg-[var(--os-bg-2)] text-[var(--os-ink-3)] text-sm">
            AssetsPage — coming soon
          </div>
        )}

        {currentPage === 'videos' && script && (
          <div className="h-full flex items-center justify-center bg-[var(--os-bg-2)] text-[var(--os-ink-3)] text-sm">
            VideoPage — coming soon
          </div>
        )}

        {/* ── Script canvas: sidebar + stage ─────────────────────────── */}
        <div
          className={[
            'grid min-h-0 h-full',
            'transition-[grid-template-columns] duration-[220ms] ease-in-out',
            currentPage !== 'script' ? 'hidden' : '',
          ].join(' ')}
          style={{ gridTemplateColumns: sidebarOpen ? '300px 1fr' : '0px 1fr' }}
        >

          {/* Sidebar wrap */}
          <div
            className={[
              'flex flex-col min-h-0 overflow-hidden bg-white',
              sidebarOpen ? 'border-r border-[var(--os-line)]' : '',
            ].join(' ')}
            style={{ zoom: 0.82 }}
          >
            {/* Sidebar + GeneratePanel will mount here */}
            <div className="flex-1 flex items-center justify-center text-xs text-[var(--os-ink-3)]">
              Sidebar
            </div>
            <div className="border-t border-[var(--os-line)] px-[18px] py-[14px] shrink-0 text-xs text-[var(--os-ink-3)]">
              GeneratePanel
            </div>
          </div>

          {/* Stage */}
          <div className="relative min-h-0 flex flex-col overflow-hidden">

            {/* Stage bar */}
            <div
              className="flex items-center justify-between px-6 py-3 bg-white border-b border-[var(--os-line)] z-[2] shrink-0"
              style={{ zoom: 0.82 }}
            >
              <div className="flex items-center gap-[14px]">
                <button
                  className="flex items-center justify-center w-6 h-6 rounded-md border border-[var(--os-line)] bg-white text-[11px] text-[var(--os-ink-2)] hover:bg-[var(--os-bg-3)] hover:text-[var(--os-ink)]"
                  onClick={() => setSidebarOpen(o => !o)}
                  title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
                >
                  {sidebarOpen ? '‹' : '›'}
                </button>
                <h2 className="text-[15px] font-bold text-[var(--os-ink)] m-0">
                  Storyboard canvas{' '}
                  <em className="not-italic text-[var(--os-ink-3)] font-normal ml-1.5">
                    {script ? `${sceneCount} scenes · ${runtimeLabel}` : 'no script yet'}
                  </em>
                </h2>
                <div className={`text-[11.5px] flex items-center gap-1.5 px-[9px] py-[3px] rounded-full font-semibold ${statusClass}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${statusDotClass}`} />
                  {statusLabel}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {deleteUndoStack.length > 0 && (
                  <button
                    className="inline-flex items-center gap-1.5 px-[10px] py-[6px] rounded-md text-[12px] font-semibold text-[var(--os-ink-2)] border border-[var(--os-line)] hover:bg-[var(--os-bg-3)] hover:text-[var(--os-ink)]"
                    onClick={undoDelete}
                  >
                    ↩ Undo delete
                  </button>
                )}
                {/* StageBar controls (view mode, zoom, export) — separate component */}
                <span className="text-[11px] text-[var(--os-ink-3)] font-medium">
                  View · Zoom
                </span>
              </div>
            </div>

            {/* Canvas */}
            <div className="flex-1 min-h-0 relative overflow-auto canvas-bg">
              <div
                className="p-[40px_52px_200px] min-w-[3200px] origin-top-left transition-transform duration-200"
                style={{ transform: `scale(${zoom / 100})` }}
              >
                {!script && (
                  <div className="flex items-center justify-center h-64 text-[var(--os-ink-3)] text-sm italic">
                    Generate a script to get started
                  </div>
                )}
              </div>
            </div>

          </div>{/* /stage */}
        </div>{/* /script canvas grid */}
      </div>{/* /page area */}

    </div>
  );
}

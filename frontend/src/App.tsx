import { useState, useCallback, useRef } from 'react';
import type {
  Script,
  Scene,
  Character,
  DecisionPoint,
  Page,
  ViewMode,
  ModelChoice,
  VideoType,
  AssetImages,
  AssetsStep,
} from './types/script';
import {
  fetchInitialScript,
  generateBackgroundImage,
  generateCharacterImages,
  generateOpeningFrames,
  retryBackgroundImage,
  retryCharacterImage,
  retryOpeningFrame,
} from './lib/api';
import { buildGenerateRequest } from './data/catalog';
import Sidebar from './components/layout/Sidebar';
import GeneratePanel from './components/layout/GeneratePanel';
import StageBar from './components/canvas/StageBar';
import Canvas from './components/canvas/Canvas';
import GenOverlay from './components/canvas/GenOverlay';
import AssetsPage from './components/assets/AssetsPage';
import VideoPage from './components/video/VideoPage';

export default function App() {
  const [script, setScript] = useState<Script | null>(null);
  const [deleteUndoStack, setDeleteUndoStack] = useState<Script[]>([]);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [assetImages, setAssetImages] = useState<AssetImages>({ bgPath: null, charPaths: {}, framePaths: {} });
  const [assetsStep, setAssetsStep] = useState<AssetsStep>('idle');
  const [assetsError, setAssetsError] = useState<string | null>(null);

  const [busy, setBusy] = useState(false);
  const [genStep, setGenStep] = useState(0);
  const [genError, setGenError] = useState<string | null>(null);

  const [zoom, setZoom] = useState(70);
  const [viewMode, setViewMode] = useState<ViewMode>('full');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(300);
  const sidebarWidthRef = useRef(300);
  const gridRef = useRef<HTMLDivElement>(null);
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

  // ── Sidebar resize ─────────────────────────────────────────────────────

  function startDrag(e: React.MouseEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startW = sidebarWidthRef.current;
    const grid = gridRef.current;

    // Kill the CSS transition so every mousemove applies instantly
    if (grid) grid.style.transition = 'none';
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    function onMove(ev: MouseEvent) {
      const w = Math.max(200, Math.min(600, startW + ev.clientX - startX));
      sidebarWidthRef.current = w;
      // Write directly to the DOM — no React re-render lag
      if (grid) grid.style.gridTemplateColumns = `${w}px 10px 1fr`;
    }

    function onUp() {
      // Restore transition and sync React state
      if (grid) grid.style.transition = '';
      setSidebarWidth(sidebarWidthRef.current);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

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

  const deleteDecisionPoint = useCallback((dpIdx: number) => {
    if (!script) return;
    setDeleteUndoStack(prev => [...prev, script]);
    setScript(curr => {
      if (!curr) return curr;
      const dps = curr.decision_points ?? [];
      const dp = dps[dpIdx];
      if (!dp) return curr;
      const branchIds = new Set(
        dp.choices.map(c => c.routes_to_scene).filter((x): x is number => x != null),
      );
      const updatedScenes = curr.scenes
        .filter(s => !branchIds.has(s.scene_id))
        .map(s => {
          if (s.scene_id === dp.associated_introduction_scene_id) {
            const { routes_to: _, ...rest } = s;
            return rest as Scene;
          }
          return s;
        });
      return { ...curr, scenes: updatedScenes, decision_points: dps.filter((_, i) => i !== dpIdx) };
    });
  }, [script]);

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
    setRequestId(null);
    setAssetImages({ bgPath: null, charPaths: {}, framePaths: {} });
    setAssetsStep('idle');
    setAssetsError(null);
    setDeleteUndoStack([]);
    setEditingSceneIdx(null);
    setEditingCharacterIdx(null);

    const stepper = setInterval(() => {
      setGenStep(s => Math.min(s + 1, 3));
    }, 900);

    try {
      const { script: result, requestId: rid } = await fetchInitialScript(req);
      clearInterval(stepper);
      setGenStep(4);
      setScript(result);
      setRequestId(rid);
    } catch (err) {
      clearInterval(stepper);
      setGenError(err instanceof Error ? err.message : 'Generation failed');
    } finally {
      setBusy(false);
    }
  }, [selected, model, videoType, userQuery]);

  // ── Asset image generation ─────────────────────────────────────────────

  const generateAssets = useCallback(async () => {
    if (!script || !requestId) return;
    setAssetsStep('generating');
    setAssetsError(null);
    try {
      // Background and character generation are independent — run in parallel
      const [bgPath, charPaths] = await Promise.all([
        generateBackgroundImage(script, requestId),
        generateCharacterImages(script, requestId),
      ]);
      setAssetImages(prev => ({ ...prev, bgPath, charPaths }));
      // Opening frames require both background and character images
      const framePaths = await generateOpeningFrames(script, requestId, bgPath, charPaths);
      setAssetImages({ bgPath, charPaths, framePaths });
      setAssetsStep('done');
    } catch (err) {
      setAssetsError(err instanceof Error ? err.message : 'Asset generation failed');
      setAssetsStep('error');
    }
  }, [script, requestId]);

  const retryBg = useCallback(async () => {
    if (!script || !requestId) return;
    const bgPath = await retryBackgroundImage(script, requestId);
    setAssetImages(prev => ({ ...prev, bgPath }));
  }, [script, requestId]);

  const retryChar = useCallback(async (characterId: string) => {
    if (!script || !requestId) return;
    const path = await retryCharacterImage(script, requestId, characterId);
    setAssetImages(prev => ({ ...prev, charPaths: { ...prev.charPaths, [characterId]: path } }));
  }, [script, requestId]);

  const retryFrame = useCallback(async (sceneId: string) => {
    if (!script || !requestId || !assetImages.bgPath) return;
    const path = await retryOpeningFrame(script, requestId, assetImages.bgPath, assetImages.charPaths, sceneId);
    setAssetImages(prev => ({ ...prev, framePaths: { ...prev.framePaths, [sceneId]: path } }));
  }, [script, requestId, assetImages]);

  // ── Derived values ──────────────────────────────────────────────────────

  const sceneCount = script?.scenes.length ?? 0;
  const totalSecs = script?.total_duration_seconds ?? 0;
  const runtimeLabel = totalSecs ? `${Math.floor(totalSecs / 60)}m ${totalSecs % 60}s` : '—';

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="grid grid-rows-[auto_1fr] h-screen">

      {/* ── Topbar ─────────────────────────────────────────────────────── */}
      <header
        className="flex items-center justify-between px-[18px] bg-white border-b border-[var(--os-line)] z-[5]"
        style={{ zoom: 1.3 }}
      >
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
        <div className="flex items-center gap-2 text-[12px] text-[var(--os-ink-2)]">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--os-green)]" style={{ boxShadow: '0 0 0 3px rgba(156,203,59,.22)' }} />
            <span>Project · <b className="text-[var(--os-ink)] font-bold">{script?.title ?? 'Untitled scenario'}</b></span>
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
          <div className="h-full flex flex-col overflow-auto">
            <AssetsPage
              script={script}
              requestId={requestId}
              assetImages={assetImages}
              assetsStep={assetsStep}
              assetsError={assetsError}
              onGenerateAssets={generateAssets}
              onRetryBackground={retryBg}
              onRetryCharacter={retryChar}
              onRetryFrame={retryFrame}
              onBack={() => setCurrentPage('script')}
              onViewVideos={() => setCurrentPage('videos')}
            />
          </div>
        )}

        {currentPage === 'videos' && script && (
          <div className="h-full flex flex-col overflow-auto">
            <VideoPage
              script={script}
              requestId={requestId}
              onBack={() => setCurrentPage('assets')}
            />
          </div>
        )}

        {/* ── Script canvas: sidebar + stage ─────────────────────────── */}
        <div
          ref={gridRef}
          className={[
            'grid min-h-0 h-full',
            'transition-[grid-template-columns] duration-[220ms] ease-in-out',
            currentPage !== 'script' ? 'hidden' : '',
          ].join(' ')}
          style={{ gridTemplateColumns: sidebarOpen ? `${sidebarWidth}px 10px 1fr` : '0px 0px 1fr' }}
        >

          {/* Sidebar wrap */}
          <div
            className="flex flex-col min-h-0 overflow-hidden bg-white"
            style={{ zoom: 0.95 }}
          >
            <Sidebar
              selected={selected}
              toggleSec={toggleSec}
              toggleChap={toggleChap}
              search={search}
              setSearch={setSearch}
              filter={filter}
              setFilter={setFilter}
            />
            <GeneratePanel
              selected={selected}
              removeSec={removeSec}
              onGenerate={runGenerate}
              busy={busy}
              hasScript={!!script}
              model={model}
              setModel={setModel}
              videoType={videoType}
              setVideoType={setVideoType}
              userQuery={userQuery}
              setUserQuery={setUserQuery}
              genError={genError}
            />
          </div>

          {/* Resize handle */}
          <div className="resize-handle" onMouseDown={startDrag} />

          {/* Stage */}
          <div className="relative min-h-0 flex flex-col overflow-hidden">
            <StageBar
              script={script}
              busy={busy}
              sceneCount={sceneCount}
              runtimeLabel={runtimeLabel}
              sidebarOpen={sidebarOpen}
              setSidebarOpen={setSidebarOpen}
              deleteUndoStack={deleteUndoStack}
              undoDelete={undoDelete}
              zoom={zoom}
              setZoom={setZoom}
              viewMode={viewMode}
              setViewMode={setViewMode}
              videoType={videoType}
              setCurrentPage={setCurrentPage}
            />

            {/* Canvas */}
            <div className="flex-1 min-h-0 relative overflow-auto canvas-bg">
              {!script && !busy && (
                <div className="empty">
                  <div className="empty-card">
                    <div className="empty-illust"><div /><div /><div /></div>
                    <h2>Your script will appear here as a storyboard</h2>
                    <p>Pick a section in the library on the left, describe the scenario, then hit <b style={{ color: 'var(--os-orange)' }}>Generate script</b>. The AI grounds the script in the chosen OpenStax content.</p>
                  </div>
                </div>
              )}
              <div
                className="p-[40px_52px_200px] min-w-[3200px] origin-top-left transition-transform duration-200"
                style={{ transform: `scale(${zoom / 100})` }}
              >
                {script && (
                  <Canvas
                    script={script}
                    selected={selected}
                    sceneCount={sceneCount}
                    runtimeLabel={runtimeLabel}
                    viewMode={viewMode}
                    density="comfy"
                    editingSceneIdx={editingSceneIdx}
                    setEditingSceneIdx={setEditingSceneIdx}
                    editingCharacterIdx={editingCharacterIdx}
                    setEditingCharacterIdx={setEditingCharacterIdx}
                    saveSceneEdit={saveSceneEdit}
                    deleteScene={deleteScene}
                    moveScene={moveScene}
                    saveCharacterEdit={saveCharacterEdit}
                    updateDecisionPoint={updateDecisionPoint}
                    addDecisionPoint={addDecisionPoint}
                    deleteDecisionPoint={deleteDecisionPoint}
                    updateScriptField={updateScriptField}
                  />
                )}
              </div>
              {busy && <GenOverlay step={genStep} />}
            </div>

          </div>
        </div>
      </div>

    </div>
  );
}

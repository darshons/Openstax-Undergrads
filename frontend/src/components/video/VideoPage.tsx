import { useEffect, useRef, useState } from 'react';
import type { AssetImages, ScenarioBackend, Script, Scene, Choice } from '../../types/script';
import {
  generateManimVideos, getManimStatus,
  generateScenarioVideos, getScenarioStatus,
  publishScenario,
  videoUrl as toVideoUrl,
} from '../../lib/api';

function fmtDur(s: number) {
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

function VideoArrowD({ label, colorClass, height }: { label?: string; colorClass?: string; height?: number }) {
  const h = height ?? 44;
  const arrowY = h - 10;
  return (
    <div className={`video-arrow-d${colorClass ? ` ${colorClass}` : ''}`}>
      <svg width="18" height={h} viewBox={`0 0 18 ${h}`} fill="none">
        <line x1="9" y1="0" x2="9" y2={arrowY} stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        <polygon points={`3,${arrowY - 6} 9,${h} 15,${arrowY - 6}`} fill="currentColor" />
      </svg>
      {label && <span className="video-arrow-label">{label}</span>}
    </div>
  );
}

function VideoClipCard({ scene, selected, onClick, branch, choice, videoUrl }: {
  scene: Scene;
  selected: boolean;
  onClick: () => void;
  branch?: boolean;
  choice?: Choice;
  videoUrl?: string;
}) {
  const dur = scene.duration_seconds || 30;
  const type = (scene.scene_type || 'scene').replace(/_/g, ' ');
  return (
    <div
      className={`video-clip-card${selected ? ' video-clip-selected' : ''}${branch ? ' video-clip-branch' : ''}`}
      onClick={onClick}
    >
      <div className="video-clip-thumb">
        {videoUrl ? (
          <video src={videoUrl} className="video-clip-video" muted playsInline preload="metadata" />
        ) : (
          <div className="video-clip-play">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3" /></svg>
          </div>
        )}
        <span className="video-clip-scene-badge">Scene {scene.scene_id}</span>
        <span className="video-clip-dur">{fmtDur(dur)}</span>
        {choice && (
          <div className={`video-clip-answer-icon ${choice.is_correct ? 'correct' : 'incorrect'}`}>
            {choice.is_correct ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#27ae60" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c0392b" strokeWidth="3" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            )}
          </div>
        )}
      </div>
      <div className="video-clip-foot">
        <div className="video-clip-type">{choice ? `${choice.choice_id} · ${type}` : type}</div>
        <div className="video-clip-text">{scene.narration_text || scene.description || ''}</div>
      </div>
    </div>
  );
}

function PublishControl({ onPublish }: { onPublish: (name: string) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [status, setStatus] = useState<'idle' | 'publishing' | 'done' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setStatus('publishing');
    setError(null);
    try {
      await onPublish(trimmed);
      setStatus('done');
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  if (!open) {
    return (
      <button className="assets-back" onClick={() => setOpen(true)} style={{ gap: 6 }}>
        Upload ↑
      </button>
    );
  }

  return (
    <div className="video-publish-bar">
      {status === 'done' ? (
        <span className="video-publish-done">Published as "{name.trim()}"</span>
      ) : (
        <>
          <input
            className="video-publish-input"
            value={name}
            disabled={status === 'publishing'}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') submit(); }}
            placeholder="Project name"
            autoFocus
          />
          <button className="assets-back" disabled={status === 'publishing' || !name.trim()} onClick={submit}>
            {status === 'publishing' ? 'Uploading…' : 'Publish'}
          </button>
          <button className="assets-back" disabled={status === 'publishing'} onClick={() => setOpen(false)}>
            Cancel
          </button>
          {error && <span className="video-publish-error">{error}</span>}
        </>
      )}
    </div>
  );
}

interface VideoPageProps {
  script: Script;
  requestId: string | null;
  scenarioBackend: ScenarioBackend;
  assetImages: AssetImages;
  onBack: () => void;
  onStudentPreview?: () => void;
}

type GenState = 'idle' | 'running' | 'done' | 'partial' | 'error';

export default function VideoPage({ script, requestId, scenarioBackend, assetImages, onBack, onStudentPreview }: VideoPageProps) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [sceneVideos, setSceneVideos] = useState<Record<number, string>>({});
  const [sceneVideoPaths, setSceneVideoPaths] = useState<Record<number, string>>({});
  const [genState, setGenState] = useState<GenState>('idle');
  const [genStatus, setGenStatus] = useState<string>('');
  const [genError, setGenError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);
  const scenes = script.scenes ?? [];
  const dps = script.decision_points ?? [];

  // Poll the pipeline while a run is active, merging completed clips into
  // sceneVideos so scene cards light up progressively.
  useEffect(() => {
    if (genState !== 'running' || !requestId) return;
    let cancelled = false;
    const wantsManim = scenes.some(sc => sc.render_mode === 'manim');
    const wantsScenario = scenes.some(sc => sc.render_mode !== 'manim');

    // A terminal state for the run as a whole means every renderer it started
    // has finished; the run is only clean if none of them reported failures.
    const TERMINAL = ['done', 'partial', 'error', 'completed_with_errors', 'failed'];

    const tick = async () => {
      try {
        const [manim, scenario] = await Promise.all([
          wantsManim ? getManimStatus(requestId) : Promise.resolve(null),
          wantsScenario ? getScenarioStatus(requestId) : Promise.resolve(null),
        ]);
        if (cancelled) return;

        const active = [manim, scenario].filter(Boolean) as NonNullable<typeof manim>[];
        setGenStatus(active.map(st => st.state).join(' · '));

        setSceneVideos(prev => {
          const next = { ...prev };
          for (const st of active) {
            for (const [id, path] of Object.entries(st.completed_scenes || {})) {
              next[Number(id)] = toVideoUrl(path);
            }
          }
          return next;
        });
        setSceneVideoPaths(prev => {
          const next = { ...prev };
          for (const st of active) {
            for (const [id, path] of Object.entries(st.completed_scenes || {})) {
              next[Number(id)] = path;
            }
          }
          return next;
        });

        if (!active.every(st => TERMINAL.includes(st.state))) return;

        const failed = active.flatMap(st => Object.keys(st.failed_scenes || {}));
        const completed = active.flatMap(st => Object.keys(st.completed_scenes || {}));
        const hardError = active.find(st => st.state === 'error' || st.state === 'failed');

        if (failed.length === 0 && !hardError) {
          setGenState('done');
        } else if (completed.length > 0) {
          // Some scenes rendered and some didn't. Play what exists, but name the
          // gaps -- a silent "done" here looks like a complete video.
          setGenState('partial');
          setGenError(
            `${failed.length} of ${failed.length + completed.length} scenes failed to render ` +
            `(scene ${failed.join(', ')}). The rest are playable.`,
          );
        } else {
          setGenState('error');
          setGenError(hardError?.error || 'Generation failed');
        }
      } catch (e) {
        if (!cancelled) { setGenState('error'); setGenError(String(e)); }
      }
    };
    tick();
    pollRef.current = window.setInterval(tick, 5000);
    return () => {
      cancelled = true;
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [genState, requestId]);

  const handleGenerate = async () => {
    if (!requestId) { setGenError('No active scenario request'); setGenState('error'); return; }
    setGenError(null);
    setGenState('running');
    setGenStatus('starting');

    // A script can now mix renderers, so start whichever ones it actually
    // needs. Both write scene_id -> path, so the poller merges them.
    const wantsManim = scenes.some(sc => sc.render_mode === 'manim');
    const wantsScenario = scenes.some(sc => sc.render_mode !== 'manim');

    try {
      const jobs: Promise<unknown>[] = [];
      if (wantsManim) jobs.push(generateManimVideos(script, requestId));
      if (wantsScenario) {
        jobs.push(generateScenarioVideos(script, requestId, scenarioBackend, {
          backgroundImagePath: assetImages.bgPath,
          characterImageFileMapping: assetImages.charPaths,
        }));
      }
      if (jobs.length === 0) {
        setGenState('error');
        setGenError('This script has no scenes to render.');
        return;
      }
      await Promise.all(jobs);
    } catch (e) {
      setGenState('error');
      setGenError(e instanceof Error ? e.message : String(e));
    }
  };


  const branchIds = new Set(
    dps.flatMap(dp => dp.choices.map(c => c.routes_to_scene).filter((x): x is number => x != null)),
  );
  const trunkScenes = scenes.filter(s => !branchIds.has(s.scene_id));

  const dpMap = new Map(dps.map(dp => [dp.decision_point_id, dp]));
  const dpByScene: Record<number, typeof dps[0]> = {};
  scenes.forEach(s => {
    if (s.routes_to && 'decision_point_id' in s.routes_to && s.routes_to.decision_point_id != null) {
      const dp = dpMap.get(s.routes_to.decision_point_id);
      if (dp) dpByScene[s.scene_id] = dp;
    }
  });

  const totalSec = scenes.reduce((sum, s) => sum + (s.duration_seconds ?? 30), 0);
  const selectedScene = scenes.find(s => s.scene_id === selectedId);

  return (
    <div className="video-page">
      <div className="assets-topbar">
        <button className="assets-back" onClick={onBack}>← Back to Assets</button>
        <div className="assets-topbar-title">
          <h2>Video Review</h2>
          <p>{script.title || 'Untitled scenario'}</p>
        </div>
        <div className="video-topbar-actions">
          <button
            className="assets-back"
            onClick={handleGenerate}
            disabled={genState === 'running'}
            title={requestId ? 'Generate Manim videos for every scene' : 'Generate a script first'}
          >
            {genState === 'running'
              ? `Generating… ${genStatus}`
              : genState === 'done' || genState === 'partial'
                ? 'Regenerate videos'
                : 'Generate videos'}
          </button>
          {onStudentPreview && (
            <button className="assets-back" onClick={onStudentPreview} style={{ gap: 6 }}>
              Student Preview →
            </button>
          )}
          <PublishControl onPublish={name => publishScenario(name, script, sceneVideoPaths)} />
        </div>
      </div>

      {genState === 'error' && genError && (
        <div className="video-gen-error" style={{ padding: '8px 16px', color: '#c0392b' }}>
          Video generation error: {genError}
        </div>
      )}

      {genState === 'partial' && genError && (
        <div className="video-gen-warning" style={{ padding: '8px 16px', color: '#b7791f' }}>
          {genError}
        </div>
      )}

      <div className="video-body">
        <div className="video-hero">
          <div className="video-player-lg" onClick={() => setSelectedId(null)}>
            {selectedScene && sceneVideos[selectedScene.scene_id] ? (
              <video
                key={sceneVideos[selectedScene.scene_id]}
                src={sceneVideos[selectedScene.scene_id]}
                className="video-player-video"
                controls
                autoPlay
                onClick={e => e.stopPropagation()}
              />
            ) : (
              <>
                {selectedScene ? (
                  <span className="video-scene-label-overlay">
                    Scene {selectedScene.scene_id} · {(selectedScene.scene_type || 'scene').replace(/_/g, ' ')}
                  </span>
                ) : (
                  <span className="video-combined-label">Combined · {scenes.length} scenes</span>
                )}
                <div className="video-play-circle">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3" /></svg>
                </div>
              </>
            )}
          </div>
          <div className="video-hero-foot">
            <div className="video-hero-title">
              {selectedScene
                ? (selectedScene.narration_text || selectedScene.description || `Scene ${selectedScene.scene_id}`)
                : (script.title || 'Untitled scenario')}
            </div>
            <div className="video-hero-stats">
              <span>{fmtDur(totalSec)} estimated total</span>
              <span className="vdot" />
              <span>{scenes.length} scene{scenes.length !== 1 ? 's' : ''}</span>
              <span className="vdot" />
              <span>{dps.length} decision point{dps.length !== 1 ? 's' : ''}</span>
            </div>
          </div>
        </div>

        <section>
          <div className="asset-section-hd">
            <span className="asset-section-title">Scene Clips</span>
            <span className="asset-section-count">{scenes.length} clips</span>
            <div className="asset-section-divider" />
          </div>

          <div className="video-timeline">
            {trunkScenes.map((scene, i) => {
              const dp = dpByScene[scene.scene_id];
              const branches = dp
                ? dp.choices
                    .filter(c => c.routes_to_scene)
                    .map(c => ({ scene: scenes.find(s => s.scene_id === c.routes_to_scene), choice: c }))
                    .filter((b): b is { scene: Scene; choice: typeof dp.choices[0] } => b.scene != null)
                : [];
              return (
                <div key={scene.scene_id} className="video-segment">
                  {i > 0 && <VideoArrowD height={40} />}
                  <VideoClipCard
                    scene={scene}
                    selected={selectedId === scene.scene_id}
                    onClick={() => setSelectedId(scene.scene_id)}
                    videoUrl={sceneVideos[scene.scene_id]}
                  />
                  {dp && (
                    <>
                      <VideoArrowD height={40} />
                      <div className="video-dp-group">
                        <div className="video-dp-label-row">
                          <span className="video-dp-tag">Decision Point {dp.decision_point_id}</span>
                          <span className="video-dp-q">{dp.question_text}</span>
                        </div>
                        <VideoArrowD height={40} />
                        {branches.length > 0 && (
                          <div className="video-branches-row">
                            {branches.map(({ scene: bs, choice }) => {
                              const rt = bs.routes_to;
                              const isRetry = rt && 'decision_point_id' in rt;
                              const isContinue = rt && 'scene_id' in rt;
                              return (
                                <div key={bs.scene_id} className="video-branch-item">
                                  <VideoClipCard
                                    scene={bs}
                                    choice={choice}
                                    branch
                                    selected={selectedId === bs.scene_id}
                                    onClick={() => setSelectedId(bs.scene_id)}
                                    videoUrl={sceneVideos[bs.scene_id]}
                                  />
                                  {!choice.is_correct && isRetry && 'decision_point_id' in rt! && (
                                    <VideoArrowD
                                      label={`↩ retry · DP ${rt!.decision_point_id}`}
                                      colorClass="retry"
                                    />
                                  )}
                                  {choice.is_correct && isContinue && 'scene_id' in rt! && (
                                    <VideoArrowD
                                      label={`→ Scene ${rt!.scene_id}`}
                                      colorClass="continues"
                                    />
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </>
                  )}
                  {!dp && i < trunkScenes.length - 1 && <VideoArrowD height={40} />}
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}

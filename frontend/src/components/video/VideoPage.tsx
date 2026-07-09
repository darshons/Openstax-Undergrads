import { useState } from 'react';
import type { Script, Scene, Choice } from '../../types/script';

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

interface VideoPageProps {
  script: Script;
  onBack: () => void;
  onStudentPreview?: () => void;
}

export default function VideoPage({ script, onBack, onStudentPreview }: VideoPageProps) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [sceneVideos, setSceneVideos] = useState<Record<number, string>>({});
  const scenes = script.scenes ?? [];
  const dps = script.decision_points ?? [];


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
        <button className="assets-back" onClick={onStudentPreview} disabled={!onStudentPreview} style={{ gap: 6 }}>
          Student Preview →
        </button>
      </div>

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
                              const routeLabel = isRetry && 'decision_point_id' in rt
                                ? `↩ retry · DP ${rt.decision_point_id}`
                                : isContinue && 'scene_id' in rt ? `→ Scene ${rt.scene_id}` : null;
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

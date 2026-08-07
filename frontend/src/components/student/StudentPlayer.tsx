import { useState, useEffect, useMemo, useRef } from 'react';
import type { Script, Scene, DecisionPoint, Choice, AssetImages, DialogueLine } from '../../types/script';
import { imageUrl } from '../../lib/api';

function getDialogue(scene: Scene): DialogueLine[] {
  if (scene.audio?.dialogue?.length) return scene.audio.dialogue;
  if (scene.audio?.clips?.length) {
    return scene.audio.clips.map(c => ({ character_id: c.character_id, line: c.dialogue }));
  }
  return [];
}

type Phase = 'watching' | 'deciding' | 'feedback' | 'complete';

interface PlayerState {
  phase: Phase;
  sceneId: number;
  dpId: number | null;
  branchSceneId: number | null;
  selectedChoiceId: string | null;
  wasCorrect: boolean | null;
}

interface StudentPlayerProps {
  script: Script;
  assetImages: AssetImages;
  /** Keyed by filename (e.g. "scene_1.mp4") - matched to scenes by position, not scene_id. */
  videoLinks?: Record<string, string>;
  onExit: () => void;
}

export default function StudentPlayer({ script, assetImages, videoLinks, onExit }: StudentPlayerProps) {
  const scenes = script.scenes ?? [];
  const dps = script.decision_points ?? [];

  const sceneMap = useMemo(() => new Map(scenes.map(s => [s.scene_id, s])), [scenes]);
  const dpMap = useMemo(() => new Map(dps.map(dp => [dp.decision_point_id, dp])), [dps]);
  const charMap = useMemo(() => new Map((script.characters ?? []).map(c => [c.character_id, c])), [script.characters]);

  const branchIds = useMemo(() => new Set(
    dps.flatMap(dp => dp.choices.map(c => c.routes_to_scene).filter((x): x is number => x != null)),
  ), [dps]);

  const trunkScenes = useMemo(
    () => scenes.filter(s => !branchIds.has(s.scene_id)),
    [scenes, branchIds],
  );

  const firstScene = trunkScenes[0];

  const [state, setState] = useState<PlayerState>({
    phase: 'watching',
    sceneId: firstScene?.scene_id ?? 1,
    dpId: null,
    branchSceneId: null,
    selectedChoiceId: null,
    wasCorrect: null,
  });

  const displaySceneId = state.branchSceneId ?? state.sceneId;
  const currentScene: Scene | undefined = sceneMap.get(displaySceneId);
  const currentDP: DecisionPoint | undefined = state.dpId ? dpMap.get(state.dpId) : undefined;
  const selectedChoice: Choice | undefined = currentDP?.choices.find(c => c.choice_id === state.selectedChoiceId);

  const frameKey = String(displaySceneId);
  const frameSrc = assetImages.framePaths[frameKey]
    ? imageUrl(assetImages.framePaths[frameKey])
    : null;

  const sceneOrder = scenes.findIndex(s => s.scene_id === displaySceneId) + 1;
  const videoSrc = videoLinks?.[`scene_${sceneOrder}.mp4`];
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Each scene's clip loads paused - the student clicks to start it (the play
  // overlay / transport bar) rather than it starting on its own. `playing`
  // wouldn't otherwise reset here since a freshly mounted <video> never fires
  // a 'pause' event to correct it.
  useEffect(() => {
    if (!videoSrc) return;
    setPlaying(false);
    setCurrentTime(0);
  }, [videoSrc]);

  function rewatchVideo() {
    // The decision/feedback panel is a full-screen overlay - switch back to
    // 'watching' so it hides and the video underneath is actually visible.
    // Continuing afterward re-enters the same decision point (see
    // handleContinue), so nothing about the branching state needs to change.
    setState(s => ({ ...s, phase: 'watching' }));
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = 0;
    video.play().catch(() => {});
  }

  function togglePlay() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) video.play().catch(() => {});
    else video.pause();
  }

  function skip(seconds: number) {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.min(Math.max(video.currentTime + seconds, 0), video.duration || Infinity);
  }

  function seekTo(time: number) {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = time;
  }

  function fmtTime(s: number) {
    if (!Number.isFinite(s) || s < 0) return '0:00';
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${String(sec).padStart(2, '0')}`;
  }

  const currentTrunkIdx = trunkScenes.findIndex(s => s.scene_id === state.sceneId);

  function advanceToNextTrunkScene() {
    if (currentTrunkIdx < trunkScenes.length - 1) {
      const next = trunkScenes[currentTrunkIdx + 1];
      setState(s => ({
        ...s,
        phase: 'watching',
        sceneId: next.scene_id,
        dpId: null,
        branchSceneId: null,
        selectedChoiceId: null,
        wasCorrect: null,
      }));
    } else {
      setState(s => ({ ...s, phase: 'complete' }));
    }
  }

  function advanceFromTrunkScene() {
    const scene = sceneMap.get(state.sceneId);
    if (!scene?.routes_to) { setState(s => ({ ...s, phase: 'complete' })); return; }
    const rt = scene.routes_to;
    if ('decision_point_id' in rt) {
      setState(s => ({ ...s, phase: 'deciding', dpId: rt.decision_point_id, selectedChoiceId: null, wasCorrect: null }));
    } else {
      setState(s => ({ ...s, sceneId: rt.scene_id, phase: 'watching' }));
    }
  }

  function handleContinue() {
    videoRef.current?.pause();
    if (state.branchSceneId) {
      // Finished watching a branch scene
      if (state.wasCorrect) {
        advanceToNextTrunkScene();
      } else {
        // Retry the decision point
        setState(s => ({ ...s, phase: 'deciding', branchSceneId: null, selectedChoiceId: null, wasCorrect: null }));
      }
    } else {
      advanceFromTrunkScene();
    }
  }

  function handleChoice(choice: Choice) {
    setState(s => ({
      ...s,
      phase: 'feedback',
      selectedChoiceId: choice.choice_id,
      wasCorrect: choice.is_correct,
      branchSceneId: choice.routes_to_scene ?? null,
    }));
  }

  function advanceAfterFeedback() {
    if (state.wasCorrect) {
      if (state.branchSceneId) {
        // Correct branch scene to watch before advancing
        setState(s => ({ ...s, phase: 'watching', selectedChoiceId: null, wasCorrect: true }));
      } else {
        advanceToNextTrunkScene();
      }
    } else {
      if (state.branchSceneId) {
        // Incorrect branch scene to watch before retrying
        setState(s => ({ ...s, phase: 'watching', selectedChoiceId: null, wasCorrect: false }));
      } else {
        setState(s => ({ ...s, phase: 'deciding', selectedChoiceId: null, wasCorrect: null }));
      }
    }
  }

  if (!firstScene) {
    return (
      <div className="sp-root">
        <div className="sp-empty">No scenes in this script.</div>
      </div>
    );
  }

  const dimmed = state.phase === 'deciding' || state.phase === 'feedback';
  const onBranch = state.branchSceneId !== null;

  return (
    <div className="sp-root">
      {videoSrc
        ? (
          <video
            ref={videoRef}
            key={videoSrc}
            src={videoSrc}
            className="sp-bg-img sp-bg-video"
            playsInline
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onLoadedMetadata={e => setDuration(e.currentTarget.duration)}
            onTimeUpdate={e => setCurrentTime(e.currentTarget.currentTime)}
          />
        )
        : frameSrc
        ? <img key={frameSrc} src={frameSrc} alt="" className="sp-bg-img" />
        : <div className="sp-bg-fallback" />
      }
      <div className="sp-vignette" />
      {dimmed && <div className="sp-dim" />}
      {videoSrc && state.phase === 'watching' && !playing && (
        <button className="sp-play-overlay" onClick={togglePlay} aria-label="Play video">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3" /></svg>
        </button>
      )}

      {/* Video transport controls */}
      {videoSrc && state.phase === 'watching' && (
        <div className="sp-transport">
          <button className="sp-transport-btn" onClick={() => skip(-10)} aria-label="Back 10 seconds">−10s</button>
          <button className="sp-transport-btn sp-transport-play" onClick={togglePlay} aria-label={playing ? 'Pause' : 'Play'}>
            {playing ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1" /><rect x="14" y="4" width="4" height="16" rx="1" /></svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3" /></svg>
            )}
          </button>
          <button className="sp-transport-btn" onClick={() => skip(10)} aria-label="Forward 10 seconds">+10s</button>
          <span className="sp-transport-time">{fmtTime(currentTime)}</span>
          <input
            type="range"
            className="sp-transport-seek"
            min={0}
            max={duration || 0}
            step={0.1}
            value={currentTime}
            onChange={e => seekTo(Number(e.target.value))}
            aria-label="Seek"
          />
          <span className="sp-transport-time">{fmtTime(duration)}</span>
        </div>
      )}

      {/* Progress */}
      <div className="sp-progress">
        {trunkScenes.map((s, i) => (
          <div
            key={s.scene_id}
            className={`sp-dot${i < currentTrunkIdx ? ' done' : ''}${i === currentTrunkIdx ? ' active' : ''}`}
          />
        ))}
      </div>

      <button className="sp-exit" onClick={onExit}>Exit</button>

      {/* Scene tag - top left */}
      {state.phase === 'watching' && currentScene && (
        <div className="sp-scene-tag">
          <span className="sp-scene-tag-num">Scene {currentScene.scene_id}</span>
          {script.setting?.location && (
            <span className="sp-scene-tag-loc">{script.setting.location}</span>
          )}
          {onBranch && <span className="sp-scene-tag-review">Review</span>}
        </div>
      )}

      {/* Dialogue panel */}
      {state.phase === 'watching' && currentScene && !videoSrc && (() => {
        const lines = getDialogue(currentScene);
        const fallback = currentScene.narration_text || currentScene.scene_summary || currentScene.description;
        if (!lines.length && !fallback) return null;
        return (
          <div className="sp-dialogue">
            {lines.length > 0 ? lines.map((dl, i) => {
              const char = charMap.get(dl.character_id);
              const charPath = assetImages.charPaths[dl.character_id];
              const avatarSrc = charPath ? imageUrl(charPath) : null;
              const initial = (char?.name ?? dl.character_id).charAt(0).toUpperCase();
              return (
                <div key={i} className="sp-dline">
                  {avatarSrc
                    ? <img src={avatarSrc} alt="" className="sp-dline-avatar" />
                    : <div className="sp-dline-initial">{initial}</div>
                  }
                  <div className="sp-dline-body">
                    <div className="sp-dline-name">{char?.name ?? dl.character_id}</div>
                    <div className="sp-dline-text">&ldquo;{dl.line}&rdquo;</div>
                  </div>
                </div>
              );
            }) : (
              <p className="sp-dline-narration">{fallback}</p>
            )}
          </div>
        );
      })()}

      {/* Continue button */}
      {state.phase === 'watching' && (
        <button className="sp-continue" onClick={handleContinue}>
          {onBranch && !state.wasCorrect ? 'Try again' : 'Continue'}
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      )}

      {/* Decision / Feedback panel */}
      {(state.phase === 'deciding' || state.phase === 'feedback') && currentDP && (
        <div className="sp-panel">
          {videoSrc && (
            <button className="sp-rewatch" onClick={rewatchVideo}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              Rewatch video
            </button>
          )}
          <p className="sp-panel-q">{currentDP.question_text}</p>
          <div className="sp-choices">
            {currentDP.choices.map(choice => {
              const isSelected = choice.choice_id === state.selectedChoiceId;
              const resultClass = state.phase === 'feedback' && isSelected
                ? (state.wasCorrect ? ' sp-choice--correct' : ' sp-choice--wrong')
                : '';
              return (
                <button
                  key={choice.choice_id}
                  className={`sp-choice${resultClass}`}
                  disabled={state.phase === 'feedback'}
                  onClick={() => state.phase === 'deciding' && handleChoice(choice)}
                >
                  <span className="sp-choice-letter">{choice.choice_id}</span>
                  <span className="sp-choice-text">{choice.text}</span>
                  {state.phase === 'feedback' && isSelected && state.wasCorrect && (
                    <svg className="sp-choice-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  )}
                  {state.phase === 'feedback' && isSelected && !state.wasCorrect && (
                    <svg className="sp-choice-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  )}
                </button>
              );
            })}
          </div>
          {state.phase === 'feedback' && !state.wasCorrect && selectedChoice?.misconception && (
            <p className="sp-misconception">{selectedChoice.misconception}</p>
          )}
          {state.phase === 'feedback' && state.wasCorrect && (
            <p className="sp-correct-msg">Correct!</p>
          )}
          {state.phase === 'feedback' && (
            <button className="sp-ack-btn" onClick={advanceAfterFeedback}>
              {state.wasCorrect ? 'Continue' : 'I understand'}
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </button>
          )}
        </div>
      )}

      {/* Completion */}
      {state.phase === 'complete' && (
        <div className="sp-complete">
          <div className="sp-complete-inner">
            <div className="sp-complete-check">
              <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <h2 className="sp-complete-title">Scenario Complete</h2>
            {script.learning_goal && (
              <p className="sp-complete-goal">{script.learning_goal}</p>
            )}
            <button className="sp-complete-btn" onClick={onExit}>Return to Studio</button>
          </div>
        </div>
      )}
    </div>
  );
}

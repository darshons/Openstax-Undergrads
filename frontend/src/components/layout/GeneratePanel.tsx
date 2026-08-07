import type { ScenarioBackend, VideoType } from '../../types/script';
import { I } from '../shared/Icons';

interface GeneratePanelProps {
  selected: Set<string>;
  removeSec: (id: string) => void;
  onGenerate: () => void;
  busy: boolean;
  hasScript: boolean;
  videoType: VideoType;
  setVideoType: (v: VideoType) => void;
  scenarioBackend: ScenarioBackend;
  setScenarioBackend: (v: ScenarioBackend) => void;
  userQuery: string;
  setUserQuery: (q: string) => void;
  genError: string | null;
}

type Renderer = 'veo' | 'wan' | 'manim';

export default function GeneratePanel({
  selected, removeSec, onGenerate, busy, hasScript,
  videoType, setVideoType, scenarioBackend, setScenarioBackend,
  userQuery, setUserQuery, genError,
}: GeneratePanelProps) {
  const renderer: Renderer = videoType === 'manim' ? 'manim' : scenarioBackend === 'veo' ? 'veo' : 'wan';
  const setRenderer = (r: Renderer) => {
    if (r === 'manim') {
      setVideoType('manim');
      return;
    }
    setVideoType('scenario');
    setScenarioBackend(r === 'veo' ? 'veo' : 'local');
  };
  const pillsArr = Array.from(selected);
  const queryReady = userQuery.trim().length > 0;
  const canRun = selected.size > 0 && queryReady && !busy;

  return (
    <div className="sb-foot">
      <div className="ctx-tag">
        <span>Context · {selected.size} section{selected.size === 1 ? '' : 's'}</span>
        {selected.size > 0 && <span>{Math.min(99, selected.size * 4)}k tokens</span>}
      </div>

      {pillsArr.length === 0 ? (
        <div className="ctx-empty">Select sections from the library above</div>
      ) : (
        <div className="ctx-pills">
          {pillsArr.slice(0, 12).map(id => {
            const parts = id.split(':');
            const s = parts[2];
            return (
              <span key={id} className="ctx-pill">
                §{s}
                <button onClick={() => removeSec(id)} aria-label="Remove">×</button>
              </span>
            );
          })}
          {pillsArr.length > 12 && (
            <span className="ctx-pill" style={{ background: '#f3f5f8', color: '#5e6a71' }}>
              +{pillsArr.length - 12}
            </span>
          )}
        </div>
      )}

      <label className="gp-label">Scenario description</label>
      <textarea
        className="gp-textarea"
        value={userQuery}
        onChange={e => setUserQuery(e.target.value)}
        placeholder="What scenario should the script dramatize? e.g. A nursing student watches a patient's glucose metabolism in real time."
      />

      <label className="gp-label">Video type</label>
      <div className="gp-models">
        <button type="button" className={`gp-model ${renderer === 'veo' ? 'on' : ''}`} onClick={() => setRenderer('veo')}>
          <span style={{ display: 'block', fontSize: '1.1em', marginBottom: 2 }}>☁️</span>
          Veo
        </button>
        <button type="button" className={`gp-model ${renderer === 'wan' ? 'on' : ''}`} onClick={() => setRenderer('wan')}>
          <span style={{ display: 'block', fontSize: '1.1em', marginBottom: 2 }}>🎬</span>
          Wan
        </button>
        <button type="button" className={`gp-model ${renderer === 'manim' ? 'on' : ''}`} onClick={() => setRenderer('manim')}>
          <span style={{ display: 'block', fontSize: '1.1em', marginBottom: 2 }}>📊</span>
          Manim
        </button>
      </div>

      <button className="btn btn-primary btn-full" disabled={!canRun} onClick={onGenerate} style={{ marginTop: 12 }}>
        {busy
          ? <><span className="spin" />Generating…</>
          : <>{I.sparkle} {hasScript ? 'Generate new script' : 'Generate script'}</>}
      </button>

      {genError && <div className="gen-error">{genError}</div>}

      {hasScript && (
        <p style={{ fontSize: 11, color: 'var(--os-ink-3)', margin: '10px 0 0', lineHeight: 1.5, textAlign: 'center' }}>
          Tip — click the pencil on any scene, character, or choice to edit it manually.
        </p>
      )}
    </div>
  );
}

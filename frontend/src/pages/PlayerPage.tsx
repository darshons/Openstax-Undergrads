import { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import type { Script, AssetImages } from '../types/script';
import StudentPlayer from '../components/student/StudentPlayer';
import { loadScenario } from '../lib/savedScenario';
import { fetchScenario, fetchDummyScenario } from '../lib/api';
import { ANTHONY_SCRIPT, ANTHONY_ASSET_IMAGES, ANTHONY_VIDEO_LINKS } from '../data/anthonyScenario';

interface PreviewState {
  script: Script;
  assetImages: AssetImages;
  videoLinks?: Record<string, string>;
}

export default function PlayerPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { scenarioId } = useParams();

  // Router state covers the in-session "Student Preview" flow from Studio.
  const routerState = location.state as PreviewState | null;

  const [remote, setRemote] = useState<PreviewState | null>(null);
  const [loading, setLoading] = useState(!routerState);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (routerState || !scenarioId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    const request = scenarioId === '__dummy__'
      ? fetchDummyScenario()
      : scenarioId.toLowerCase() === 'anthony'
      ? Promise.resolve({ script: ANTHONY_SCRIPT, assetImages: ANTHONY_ASSET_IMAGES, videoLinks: ANTHONY_VIDEO_LINKS })
      : fetchScenario(scenarioId);
    request
      .then(data => { if (!cancelled) setRemote(data); })
      .catch(() => { if (!cancelled) setNotFound(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [scenarioId, routerState]);

  // If the real published scenario can't be found, fall back to whatever was
  // last locally saved from a Studio preview, so the flow stays testable even
  // before a scenario has actually been published for this name.
  const fallback = notFound ? loadScenario() : null;
  const state = routerState ?? remote ?? fallback;
  const usingFallback = !routerState && !remote && !!fallback;

  if (loading) {
    return (
      <div className="sp-root">
        <div className="sp-empty">Loading…</div>
      </div>
    );
  }

  if (!state?.script) {
    return (
      <div className="sp-root">
        <div className="sp-empty" style={{ flexDirection: 'column', gap: 16 }}>
          <span>{scenarioId ? `No scenario found for "${scenarioId}".` : 'No scenario loaded.'}</span>
          <button
            onClick={() => navigate('/player')}
            style={{ fontSize: 13, color: 'rgba(255,255,255,.5)', background: 'rgba(255,255,255,.06)', border: '1px solid rgba(255,255,255,.12)', borderRadius: 6, padding: '6px 14px', cursor: 'pointer' }}
          >
            Try another name
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      {usingFallback && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 100,
            textAlign: 'center',
            fontSize: 12,
            fontWeight: 600,
            padding: '6px 12px',
            background: '#f39c12',
            color: '#1a1400',
          }}
        >
          Local preview only — "{scenarioId}" hasn't been published yet, showing your last Studio preview instead
        </div>
      )}
      <StudentPlayer
        script={state.script}
        assetImages={state.assetImages ?? { bgPath: null, charPaths: {}, framePaths: {} }}
        videoLinks={state.videoLinks}
        onExit={() => navigate(-1 as never)}
      />
    </>
  );
}

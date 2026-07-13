import { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import type { Script, AssetImages } from '../types/script';
import StudentPlayer from '../components/student/StudentPlayer';
import { loadScenario } from '../lib/savedScenario';
import { fetchScenario } from '../lib/api';

interface PreviewState {
  script: Script;
  assetImages: AssetImages;
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
    fetchScenario(scenarioId)
      .then(data => { if (!cancelled) setRemote(data); })
      .catch(() => { if (!cancelled) setNotFound(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [scenarioId, routerState]);

  // The published-scenario endpoint isn't live yet; fall back to the
  // locally-saved scenario from Studio so the flow is testable end to end.
  const state = routerState ?? remote ?? (notFound ? loadScenario() : null);

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
    <StudentPlayer
      script={state.script}
      assetImages={state.assetImages ?? { bgPath: null, charPaths: {}, framePaths: {} }}
      onExit={() => navigate(-1 as never)}
    />
  );
}

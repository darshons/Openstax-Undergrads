import { useLocation, useNavigate } from 'react-router-dom';
import type { Script, AssetImages } from '../types/script';
import StudentPlayer from '../components/student/StudentPlayer';
import { loadScenario } from '../lib/savedScenario';

interface PreviewState {
  script: Script;
  assetImages: AssetImages;
}

export default function PlayerPage() {
  const location = useLocation();
  const navigate = useNavigate();

  // Router state covers the in-session "Student Preview" flow from Studio.
  // Falling back to the saved scenario lets the landing page's Student card
  // work on its own. When backend persistence is ready, fetch from
  // /api/scenario/:scenarioId instead of either of these.
  const state = (location.state as PreviewState | null) ?? loadScenario();

  if (!state?.script) {
    return (
      <div className="sp-root">
        <div className="sp-empty" style={{ flexDirection: 'column', gap: 16 }}>
          <span>No scenario loaded.</span>
          <button
            onClick={() => navigate('/')}
            style={{ fontSize: 13, color: 'rgba(255,255,255,.5)', background: 'rgba(255,255,255,.06)', border: '1px solid rgba(255,255,255,.12)', borderRadius: 6, padding: '6px 14px', cursor: 'pointer' }}
          >
            Go home
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

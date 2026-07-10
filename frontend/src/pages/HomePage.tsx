import { useNavigate } from 'react-router-dom';

export default function HomePage() {
  const navigate = useNavigate();

  return (
    <div className="hp-root">
      <div className="hp-inner">

        {/* Wordmark */}
        <div className="hp-brand">
          <div className="hp-brand-bars" aria-hidden>
            <span style={{ background: 'var(--os-green)',  width: 22, marginLeft: 6 }} />
            <span style={{ background: 'var(--os-orange)', width: 28 }} />
            <span style={{ background: 'var(--os-gray)',   width: 24, marginLeft: 3 }} />
            <span style={{ background: 'var(--os-yellow)', width: 20, marginLeft: 8 }} />
            <span style={{ background: 'var(--os-navy)',   width: 26, marginLeft: 1 }} />
          </div>
          <span className="hp-brand-name">
            open<em>stax</em>
          </span>
          <span className="hp-brand-product">Scenario Studio</span>
        </div>

        <h1 className="hp-headline">Who are you?</h1>
        <p className="hp-sub">Choose your role to get started.</p>

        <div className="hp-cards">

          {/* Creator card */}
          <button className="hp-card hp-card--creator" onClick={() => navigate('/studio')}>
            <div className="hp-card-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <path d="M3 9h18M9 21V9"/>
              </svg>
            </div>
            <div className="hp-card-body">
              <div className="hp-card-title">Creator</div>
              <div className="hp-card-desc">Build and edit clinical scenarios. Generate scripts, assets, and decision points for student use.</div>
            </div>
            <div className="hp-card-arrow">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </div>
          </button>

          {/* Student card */}
          <button className="hp-card hp-card--student" onClick={() => navigate('/player')}>
            <div className="hp-card-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="8" r="4"/>
                <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
              </svg>
            </div>
            <div className="hp-card-body">
              <div className="hp-card-title">Student</div>
              <div className="hp-card-desc">Experience a clinical scenario as an immersive, interactive video. Make decisions and get feedback.</div>
            </div>
            <div className="hp-card-arrow">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </div>
          </button>

        </div>

      </div>
    </div>
  );
}

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function JoinPage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');

  const go = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    navigate(`/player/${encodeURIComponent(trimmed)}`);
  };

  return (
    <div className="hp-root">
      <div className="hp-inner">

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

        <h1 className="hp-headline">Join a scenario</h1>
        <p className="hp-sub">Enter the project name your instructor gave you.</p>

        <div className="hp-join-form">
          <input
            className="hp-join-input"
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') go(); }}
            placeholder="Project name"
            autoFocus
          />
          <button className="hp-join-btn" onClick={go} disabled={!name.trim()}>
            Watch →
          </button>
        </div>

        <button className="hp-join-back" onClick={() => navigate('/')}>← Back</button>

      </div>
    </div>
  );
}

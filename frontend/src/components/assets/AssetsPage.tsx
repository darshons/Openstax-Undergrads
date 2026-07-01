import { useState, useEffect } from 'react';
import type { Script } from '../../types/script';
import { I } from '../shared/Icons';

interface AssetItem {
  id: string;
  label: string;
  role: string;
  src: string | null;
  category: string;
}

function AssetCard({ id: _id, label, role, src, category }: AssetItem) {
  const [note, setNote] = useState('');
  const [requested, setRequested] = useState<string | null>(null);
  const [lightbox, setLightbox] = useState(false);

  useEffect(() => {
    if (!lightbox) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setLightbox(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [lightbox]);

  return (
    <div className="asset-card">
      {lightbox && src && (
        <div className="asset-lightbox" onClick={() => setLightbox(false)}>
          <img src={src} alt={label} />
          <span className="asset-lightbox-label">{label}</span>
        </div>
      )}
      <div className="asset-img-wrap" onClick={() => src && setLightbox(true)}>
        {src ? (
          <img src={src} alt={label} />
        ) : (
          <div className="asset-img-placeholder">
            {I.image}
            <span className="asset-cat-badge">{category}</span>
          </div>
        )}
      </div>
      <div className="asset-card-info">
        <div className="asset-card-name">{label}</div>
        {role && <div className="asset-card-role">{role}</div>}
      </div>
      <div className="asset-card-form">
        {requested ? (
          <div className="asset-requested">
            <div className="asset-requested-badge">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Change requested
            </div>
            <div className="asset-requested-text">"{requested}"</div>
            <button className="asset-edit-link" onClick={() => { setNote(requested); setRequested(null); }}>Edit request</button>
          </div>
        ) : (
          <>
            <textarea
              className="asset-request-ta"
              rows={2}
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Describe changes to this image…"
              onKeyDown={e => { if (e.key === 'Enter' && e.metaKey && note.trim()) { setRequested(note.trim()); setNote(''); } }}
            />
            <button
              className="asset-request-btn"
              disabled={!note.trim()}
              onClick={() => { if (note.trim()) { setRequested(note.trim()); setNote(''); } }}
            >
              Request change
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function AssetSection({ title, items }: { title: string; items: AssetItem[] }) {
  return (
    <section>
      <div className="asset-section-hd">
        <span className="asset-section-title">{title}</span>
        <span className="asset-section-count">{items.length} image{items.length !== 1 ? 's' : ''}</span>
        <div className="asset-section-divider" />
      </div>
      <div className="asset-grid">
        {items.map(item => <AssetCard key={item.id} {...item} />)}
      </div>
    </section>
  );
}

interface AssetsPageProps {
  script: Script;
  onBack: () => void;
  onViewVideos: () => void;
}

export default function AssetsPage({ script, onBack, onViewVideos }: AssetsPageProps) {
  const characters: AssetItem[] = (script.characters ?? []).map(c => ({
    id: `char-${c.character_id}`,
    label: c.name || `Character ${c.character_id}`,
    role: c.role || c.character_id,
    src: null,
    category: 'character',
  }));

  const backgrounds: AssetItem[] = [
    { id: 'bg-1', label: 'Primary Setting',   role: 'Main scene background', src: null, category: 'background' },
    { id: 'bg-2', label: 'Secondary Setting', role: 'Alternate background',  src: null, category: 'background' },
  ];

  const sceneAssets: AssetItem[] = [
    { id: 'asset-1', label: 'Medical Equipment', role: 'Primary prop',   src: null, category: 'asset' },
    { id: 'asset-2', label: 'Patient Chart',     role: 'Document prop',  src: null, category: 'asset' },
    { id: 'asset-3', label: 'Clinical Tool',     role: 'Secondary prop', src: null, category: 'asset' },
  ];

  return (
    <div className="assets-page">
      <div className="assets-topbar">
        <button className="assets-back" onClick={onBack}>← Back to Script</button>
        <div className="assets-topbar-title">
          <h2>Video Assets</h2>
          <p>{script.title || 'Untitled scenario'}</p>
        </div>
        <div style={{ width: 140 }} />
      </div>
      <div className="assets-next-strip">
        <div className="assets-next-strip-l">
          <span className="assets-next-step-label">Next step</span>
          <span className="assets-next-step-desc">Assets confirmed — preview the generated video clips</span>
        </div>
        <button className="btn-assets" onClick={onViewVideos}>
          View Videos {I.arrowRight}
        </button>
      </div>
      <div className="assets-body">
        <AssetSection title="Characters" items={characters} />
        <AssetSection title="Backgrounds" items={backgrounds} />
        <AssetSection title="Scene Assets" items={sceneAssets} />
      </div>
    </div>
  );
}

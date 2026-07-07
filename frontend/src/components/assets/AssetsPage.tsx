import { useState, useEffect } from 'react';
import type { Script, AssetImages, AssetsStep } from '../../types/script';
import { imageUrl } from '../../lib/api';
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
  requestId: string | null;
  assetImages: AssetImages;
  assetsStep: AssetsStep;
  assetsError: string | null;
  onGenerateAssets: () => void;
  onBack: () => void;
  onViewVideos: () => void;
}

export default function AssetsPage({
  script,
  requestId,
  assetImages,
  assetsStep,
  assetsError,
  onGenerateAssets,
  onBack,
  onViewVideos,
}: AssetsPageProps) {
  const { bgPath, charPaths, framePaths } = assetImages;
  const generating = assetsStep === 'generating';

  const characters: AssetItem[] = (script.characters ?? []).map(c => ({
    id: `char-${c.character_id}`,
    label: c.name || `Character ${c.character_id}`,
    role: c.role || c.character_id,
    src: charPaths[c.character_id] ? imageUrl(charPaths[c.character_id]) : null,
    category: 'character',
  }));

  const backgrounds: AssetItem[] = [{
    id: 'bg-1',
    label: 'Primary Setting',
    role: script.setting?.location || 'Main scene background',
    src: bgPath ? imageUrl(bgPath) : null,
    category: 'background',
  }];

  const branchIds = new Set(
    (script.decision_points ?? []).flatMap(dp =>
      dp.choices.map(c => c.routes_to_scene).filter((x): x is number => x != null),
    ),
  );

  const frameItems: AssetItem[] = (script.scenes ?? [])
    .filter(s => !branchIds.has(s.scene_id))
    .map(s => ({
      id: `frame-${s.scene_id}`,
      label: `Scene ${s.scene_id} Opening Frame`,
      role: s.scene_summary || s.description || '',
      src: framePaths[String(s.scene_id)] ? imageUrl(framePaths[String(s.scene_id)]) : null,
      category: 'frame',
    }));

  const showCards = generating || assetsStep === 'done' || bgPath !== null;

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

      {assetsStep === 'idle' && (
        <div className="assets-next-strip">
          <div className="assets-next-strip-l">
            <span className="assets-next-step-label">Step 1 of 2</span>
            <span className="assets-next-step-desc">Generate AI reference images for characters, backgrounds, and scene frames</span>
          </div>
          <button className="btn-assets" onClick={onGenerateAssets} disabled={!requestId}>
            Generate Assets {I.sparkle}
          </button>
        </div>
      )}

      {generating && (
        <div className="assets-next-strip">
          <div className="assets-next-strip-l">
            <span className="assets-next-step-label">Generating…</span>
            <span className="assets-next-step-desc">
              {!bgPath && !Object.keys(charPaths).length
                ? 'Creating background and character reference images…'
                : 'Creating scene opening frames…'}
            </span>
          </div>
          <div style={{ padding: '0 24px', color: 'var(--os-ink-3)', fontSize: 13 }}>
            <span style={{ display: 'inline-block', animation: 'assets-pulse 1.4s ease-in-out infinite' }}>●</span>
            {' '}Working
          </div>
        </div>
      )}

      {assetsStep === 'error' && (
        <div className="assets-next-strip" style={{ background: '#fff5f5', borderColor: '#fcc' }}>
          <div className="assets-next-strip-l">
            <span className="assets-next-step-label" style={{ color: '#c0392b' }}>Generation failed</span>
            <span className="assets-next-step-desc">{assetsError}</span>
          </div>
          <button className="btn-assets" onClick={onGenerateAssets}>Retry</button>
        </div>
      )}

      {assetsStep === 'done' && (
        <div className="assets-next-strip">
          <div className="assets-next-strip-l">
            <span className="assets-next-step-label">Next step</span>
            <span className="assets-next-step-desc">Assets confirmed - preview the generated video clips</span>
          </div>
          <button className="btn-assets" onClick={onViewVideos}>
            View Videos {I.arrowRight}
          </button>
        </div>
      )}

      <div className="assets-body">
        {assetsStep === 'idle' && (
          <div className="empty" style={{ minHeight: 300 }}>
            <div className="empty-card">
              <div className="empty-illust"><div /><div /><div /></div>
              <h2>No assets generated yet</h2>
              <p>Click <b style={{ color: 'var(--os-orange)' }}>Generate Assets</b> above to create AI reference images for this scenario.</p>
            </div>
          </div>
        )}
        {showCards && (
          <>
            <AssetSection title="Characters" items={characters} />
            <AssetSection title="Background" items={backgrounds} />
            <AssetSection title="Scene Opening Frames" items={frameItems} />
          </>
        )}
      </div>
    </div>
  );
}

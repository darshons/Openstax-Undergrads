import { useState } from 'react';
import type { Script, AssetImages, AssetsStep } from '../../types/script';
import { imageUrl } from '../../lib/api';
import { I } from '../shared/Icons';

interface AssetItem {
  id: string;
  label: string;
  role: string;
  src: string | null;
  category: string;
  onRegenerate?: () => Promise<void>;
}

function AssetCard({ label, role, src, category, onRegenerate }: AssetItem) {
  const [lightbox, setLightbox] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [regenError, setRegenError] = useState<string | null>(null);

  const handleRegenerate = async () => {
    if (!onRegenerate) return;
    setRegenerating(true);
    setRegenError(null);
    try {
      await onRegenerate();
    } catch (err) {
      setRegenError(err instanceof Error ? err.message : 'Regeneration failed');
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div className="asset-card">
      {lightbox && src && (
        <div className="asset-lightbox" onClick={() => setLightbox(false)}>
          <img src={src} alt={label} />
          <span className="asset-lightbox-label">{label}</span>
        </div>
      )}
      <div className="asset-img-wrap" onClick={() => src && !regenerating && setLightbox(true)}>
        {regenerating ? (
          <div className="asset-img-placeholder">
            <span style={{ display: 'inline-block', animation: 'assets-pulse 1.4s ease-in-out infinite', fontSize: 22 }}>●</span>
            <span style={{ fontSize: 12, color: 'var(--os-ink-3)', marginTop: 6 }}>Regenerating…</span>
          </div>
        ) : src ? (
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
      {onRegenerate && (
        <div className="asset-card-form">
          {regenError && <div style={{ fontSize: 11, color: '#c0392b', marginBottom: 6 }}>{regenError}</div>}
          <button
            className="asset-request-btn"
            disabled={regenerating}
            onClick={handleRegenerate}
          >
            {regenerating ? 'Regenerating…' : 'Regenerate'}
          </button>
        </div>
      )}
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
  onRetryBackground: () => Promise<void>;
  onRetryCharacter: (characterId: string) => Promise<void>;
  onRetryFrame: (sceneId: string) => Promise<void>;
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
  onRetryBackground,
  onRetryCharacter,
  onRetryFrame,
  onBack,
  onViewVideos,
}: AssetsPageProps) {
  const { bgPath, charPaths, framePaths } = assetImages;
  const generating = assetsStep === 'generating';
  const hasAssets = assetsStep === 'done' || assetsStep === 'generating';

  const characters: AssetItem[] = (script.characters ?? []).map(c => ({
    id: `char-${c.character_id}`,
    label: c.name || `Character ${c.character_id}`,
    role: c.role || c.character_id,
    src: charPaths[c.character_id] ? imageUrl(charPaths[c.character_id]) : null,
    category: 'character',
    onRegenerate: hasAssets ? () => onRetryCharacter(c.character_id) : undefined,
  }));

  const backgrounds: AssetItem[] = [{
    id: 'bg-1',
    label: 'Primary Setting',
    role: script.setting?.location || 'Main scene background',
    src: bgPath ? imageUrl(bgPath) : null,
    category: 'background',
    onRegenerate: hasAssets ? onRetryBackground : undefined,
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
      onRegenerate: hasAssets ? () => onRetryFrame(String(s.scene_id)) : undefined,
    }));

  const showCards = hasAssets;

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

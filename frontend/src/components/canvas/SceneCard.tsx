import { useState, useEffect, Fragment } from 'react';
import type { Scene, Character, DecisionPoint, ViewMode } from '../../types/script';
import { I } from '../shared/Icons';
import { fmtDuration, characterName, SCENE_TYPES, ROUTE_TYPES } from '../../lib/utils';

interface SceneCardProps {
  s: Scene;
  characters: Character[];
  decisionPoints: DecisionPoint[];
  density: string;
  viewMode: ViewMode;
  isEditing: boolean;
  onStartEdit: () => void;
  onSaveEdit: (draft: Scene) => void;
  onCancelEdit: () => void;
  onDelete: () => void;
  onMoveLeft?: () => void;
  onMoveRight?: () => void;
  onAddDP?: () => void;
  addDPDisabled?: boolean;
}

export default function SceneCard({
  s, characters, decisionPoints, density, viewMode, isEditing,
  onStartEdit, onSaveEdit, onCancelEdit, onDelete, onMoveLeft, onMoveRight, onAddDP, addDPDisabled,
}: SceneCardProps) {
  const padding = density === 'compact' ? 16 : 20;
  const [draft, setDraft] = useState<Scene>(s);

  useEffect(() => { if (isEditing) setDraft(s); }, [isEditing, s]);

  const upd = <K extends keyof Scene>(k: K, v: Scene[K]) => setDraft(d => ({ ...d, [k]: v }));
  const updCamera = (k: string, v: string) =>
    setDraft(d => ({ ...d, camera: { ...(d.camera ?? {}), [k]: v } as Scene['camera'] }));
  const updAudio = (k: string, v: string) =>
    setDraft(d => ({ ...d, audio: { ...(d.audio ?? {}), [k]: v } as Scene['audio'] }));
  const updRoutes = (k: string, v: unknown) =>
    setDraft(d => ({ ...d, routes_to: { ...(d.routes_to ?? {}), [k]: v } as Scene['routes_to'] }));
  const updDialogueLine = (idx: number, k: string, v: string) =>
    setDraft(d => {
      const dialogue = (d.audio?.dialogue ?? []).map((row, i) => i === idx ? { ...row, [k]: v } : row);
      return { ...d, audio: { ...(d.audio ?? {}), dialogue } as Scene['audio'] };
    });
  const addDialogueLine = () =>
    setDraft(d => {
      const dialogue = [...(d.audio?.dialogue ?? []), { character_id: characters[0]?.character_id ?? '', line: '' }];
      return { ...d, audio: { ...(d.audio ?? {}), dialogue } as Scene['audio'] };
    });
  const removeDialogueLine = (idx: number) =>
    setDraft(d => {
      const dialogue = (d.audio?.dialogue ?? []).filter((_, i) => i !== idx);
      return { ...d, audio: { ...(d.audio ?? {}), dialogue } as Scene['audio'] };
    });

  if (isEditing) {
    return (
      <div style={{ position: 'relative' }}>
        <article className="scene editing" style={{ width: density === 'compact' ? 840 : 1040 }} onClick={e => e.stopPropagation()}>
          <div className="edit-banner">
            <span className="dot" />
            EDITING SCENE {String(s.scene_id).padStart(2, '0')} · MANUAL
          </div>
          <div className="scene-hd" style={{ padding: '8px 10px' }}>
            <div className="edit-tag-row">
              <span className="scene-num">SC <b>{String(s.scene_id).padStart(2, '0')}</b></span>
              <select value={draft.type || ''} onChange={e => upd('type', e.target.value as Scene['type'])}>
                {SCENE_TYPES.map(t => <option key={t} value={t}>{t.toUpperCase()}</option>)}
              </select>
              <input
                type="number"
                value={draft.duration_seconds ?? ''}
                onChange={e => upd('duration_seconds', e.target.value === '' ? 0 : Number(e.target.value))}
                placeholder="seconds"
                style={{ width: 80 }}
              />
            </div>
          </div>
          <div className="scene-body" style={{ padding, gap: 9 }}>
            <input className="edit-field edit-title" value={draft.scene_summary || ''} onChange={e => upd('scene_summary', e.target.value)} placeholder="Scene summary" />

            <div className="scene-block">
              <div className="scene-block-lbl">Setting</div>
              <textarea className="edit-field" value={draft.setting || ''} onChange={e => upd('setting', e.target.value)} style={{ minHeight: 64, fontSize: 16 }} />
            </div>

            <div className="scene-block">
              <div className="scene-block-lbl">Character actions</div>
              <textarea className="edit-field" value={draft.character_actions || ''} onChange={e => upd('character_actions', e.target.value)} style={{ minHeight: 64, fontSize: 16 }} />
            </div>

            <div className="scene-block">
              <div className="scene-block-lbl">Camera (angle · movement · lens)</div>
              <div className="edit-grid">
                <input className="edit-field" value={draft.camera?.angle || ''} onChange={e => updCamera('angle', e.target.value)} placeholder="angle" />
                <input className="edit-field" value={draft.camera?.movement || ''} onChange={e => updCamera('movement', e.target.value)} placeholder="movement" />
                <input className="edit-field" value={draft.camera?.lens_effect || ''} onChange={e => updCamera('lens_effect', e.target.value)} placeholder="lens" />
              </div>
            </div>

            <div className="scene-block">
              <div className="scene-block-lbl" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Dialogue</span>
                <button type="button" onClick={addDialogueLine} style={{ fontSize: 14, fontWeight: 600, color: 'var(--os-navy)', letterSpacing: '.03em' }}>+ ADD LINE</button>
              </div>
              {(draft.audio?.dialogue?.length ? draft.audio.dialogue : []).map((row, i) => (
                <div key={i} className="dialogue-row">
                  <select value={row.character_id || ''} onChange={e => updDialogueLine(i, 'character_id', e.target.value)}>
                    {characters.map(c => <option key={c.character_id} value={c.character_id}>{c.character_id} · {c.name}</option>)}
                  </select>
                  <textarea value={row.line || ''} onChange={e => updDialogueLine(i, 'line', e.target.value)} placeholder="dialogue line" />
                  <button type="button" onClick={() => removeDialogueLine(i)} title="Remove">×</button>
                </div>
              ))}
            </div>

            <div className="scene-block">
              <div className="scene-block-lbl">Audio (sound effects · ambience)</div>
              <input className="edit-field" value={draft.audio?.sound_effects || ''} onChange={e => updAudio('sound_effects', e.target.value)} placeholder="sound effects" style={{ marginBottom: 5 }} />
              <input className="edit-field" value={draft.audio?.ambience || ''} onChange={e => updAudio('ambience', e.target.value)} placeholder="ambience" />
            </div>

            <div className="scene-block">
              <div className="scene-block-lbl">Routes to (decision point · type)</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                <select
                  className="edit-field"
                  value={(draft.routes_to && 'decision_point_id' in draft.routes_to ? draft.routes_to.decision_point_id : '') ?? ''}
                  onChange={e => updRoutes('decision_point_id', e.target.value === '' ? null : Number(e.target.value))}
                >
                  <option value="">— none —</option>
                  {decisionPoints.map(dp => (
                    <option key={dp.decision_point_id} value={dp.decision_point_id}>DP {dp.decision_point_id}</option>
                  ))}
                </select>
                <select
                  className="edit-field"
                  value={draft.routes_to?.type || ''}
                  onChange={e => updRoutes('type', e.target.value)}
                >
                  <option value="">— type —</option>
                  {ROUTE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </div>
          </div>
          <div className="scene-foot" style={{ justifyContent: 'flex-end' }}>
            <div className="edit-actions">
              <button className="btn btn-ghost btn-sm" onClick={onCancelEdit}>Cancel</button>
              <button className="btn btn-navy btn-sm" onClick={() => onSaveEdit(draft)}>Save changes</button>
            </div>
          </div>
        </article>
      </div>
    );
  }

  const tagLabel = (s.type || 'scene').toUpperCase();
  const tagClass = (s.type || 'scene').toLowerCase();
  const dialogue = s.audio?.dialogue?.length ? s.audio.dialogue : [];
  const lineCount = dialogue.length;

  return (
    <div style={{ position: 'relative' }}>
      <article className="scene" style={{ width: density === 'compact' ? 800 : 980 }}>
        <div className="scene-hd">
          <span className="scene-num">
            SCENE <b>{String(s.scene_id).padStart(2, '0')}</b> · {fmtDuration(s.duration_seconds)} · {lineCount} line{lineCount === 1 ? '' : 's'}
            {s.routes_to && 'decision_point_id' in s.routes_to && s.routes_to.decision_point_id != null
              ? ` · → DP ${s.routes_to.decision_point_id}` : ''}
          </span>
          <span className={`scene-tag ${tagClass}`}>{tagLabel}</span>
        </div>
        <div className="scene-body" style={{ padding, gap: density === 'compact' ? 10 : 12 }}>
          <h3 className="scene-title">{s.scene_summary}</h3>

          {(!viewMode || viewMode === 'full') && (
            <div className="scene-cols">
              <div className="scene-col-main">
                <div className="scene-block narr">
                  <div className="scene-block-lbl">Dialogue</div>
                  {dialogue.length === 0 ? (
                    <p style={{ color: 'var(--os-ink-3)', fontStyle: 'normal' }}>(no dialogue)</p>
                  ) : dialogue.map((row, i) => (
                    <p key={i} style={{ margin: i > 0 ? '4px 0 0' : 0 }}>
                      <b style={{ fontStyle: 'normal', color: 'var(--os-navy)', marginRight: 6 }}>{characterName(characters, row.character_id)}:</b>
                      "{row.line}"
                    </p>
                  ))}
                </div>
              </div>
              <div className="scene-col-side">
                <div className="scene-block visual">
                  <div className="scene-block-lbl">Setting · Action</div>
                  <p>{s.setting}{s.character_actions ? ` — ${s.character_actions}` : ''}</p>
                </div>
                <div className="scene-block onscreen">
                  <div className="scene-block-lbl">Audio</div>
                  <p>
                    {s.audio?.sound_effects && <Fragment>FX: {s.audio.sound_effects}<br /></Fragment>}
                    {s.audio?.ambience && <Fragment>Ambient: {s.audio.ambience}</Fragment>}
                    {!s.audio?.sound_effects && !s.audio?.ambience && <span style={{ color: 'var(--os-ink-3)' }}>(none)</span>}
                  </p>
                </div>
              </div>
            </div>
          )}

          {viewMode === 'dialogue' && (
            <div className="scene-focused-view">
              {dialogue.length === 0 ? (
                <p className="scene-focused-empty">(no dialogue)</p>
              ) : dialogue.map((row, i) => (
                <p key={i} className="scene-focused-line">
                  <b className="scene-focused-speaker">{characterName(characters, row.character_id)}:</b>
                  "{row.line}"
                </p>
              ))}
            </div>
          )}

          {viewMode === 'action' && (
            <div className="scene-focused-view">
              {(s.setting || s.character_actions) ? (
                <p className="scene-focused-line">{s.setting}{s.character_actions ? ` — ${s.character_actions}` : ''}</p>
              ) : (
                <p className="scene-focused-empty">(no action details)</p>
              )}
            </div>
          )}

          {viewMode === 'camera' && (
            <div className="scene-focused-view">
              {s.camera ? (
                <p className="scene-focused-line">
                  {[s.camera.angle, s.camera.movement, s.camera.lens_effect].filter(Boolean).join(' · ')}
                </p>
              ) : (
                <p className="scene-focused-empty">(no camera details)</p>
              )}
            </div>
          )}
        </div>
        <div className="scene-foot">
          {onAddDP && (
            <button
              className={`btn-add-dp${addDPDisabled ? ' btn-add-dp-disabled' : ''}`}
              onClick={e => { e.stopPropagation(); if (!addDPDisabled) onAddDP(); }}
              title={addDPDisabled ? 'Scene already routes to a decision point' : 'Add a decision point after this scene'}
            >
              {I.plus} Add decision point
            </button>
          )}
          <div className="scene-foot-r">
            {onMoveLeft && <button className="icon-btn" title="Move left" onClick={e => { e.stopPropagation(); onMoveLeft!(); }}>{I.arrowL}</button>}
            {onMoveRight && <button className="icon-btn" title="Move right" onClick={e => { e.stopPropagation(); onMoveRight!(); }}>{I.arrowR}</button>}
            <button className="icon-btn" title="Edit scene" onClick={e => { e.stopPropagation(); onStartEdit(); }}>{I.edit}</button>
            <button className="icon-btn" title="Delete scene" style={{ color: '#c0392b' }} onClick={e => { e.stopPropagation(); onDelete(); }}>{I.trash}</button>
          </div>
        </div>
      </article>
    </div>
  );
}

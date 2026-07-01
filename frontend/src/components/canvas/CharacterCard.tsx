import { useState, useEffect } from 'react';
import type { Character } from '../../types/script';
import { I } from '../shared/Icons';

interface CharacterCardProps {
  c: Character;
  isEditing: boolean;
  onStartEdit: () => void;
  onSaveEdit: (draft: Character) => void;
  onCancelEdit: () => void;
}

export default function CharacterCard({ c, isEditing, onStartEdit, onSaveEdit, onCancelEdit }: CharacterCardProps) {
  const [draft, setDraft] = useState<Character>(c);
  useEffect(() => { if (isEditing) setDraft(c); }, [isEditing, c]);

  const upd = (k: keyof Character, v: string) => setDraft(d => ({ ...d, [k]: v }));
  const updApp = (k: string, v: string) =>
    setDraft(d => ({ ...d, appearance: { ...(d.appearance ?? {}), [k]: v } as Character['appearance'] }));

  if (isEditing) {
    return (
      <div className="char-card" style={{ borderColor: 'var(--os-navy)', boxShadow: '0 0 0 3px rgba(0,37,105,.12)' }}>
        <div className="char-id">CHAR {c.character_id}</div>
        <input value={draft.name || ''} onChange={e => upd('name', e.target.value)} placeholder="name" />
        <input value={draft.role || ''} onChange={e => upd('role', e.target.value)} placeholder="role" />
        <div className="char-appearance">
          <input value={draft.appearance?.skin_tone || ''} onChange={e => updApp('skin_tone', e.target.value)} placeholder="skin tone" />
          <input value={draft.appearance?.hair || ''} onChange={e => updApp('hair', e.target.value)} placeholder="hair" />
          <input value={draft.appearance?.build || ''} onChange={e => updApp('build', e.target.value)} placeholder="build" />
          <input value={draft.appearance?.uniform || ''} onChange={e => updApp('uniform', e.target.value)} placeholder="uniform" />
        </div>
        <input value={draft.appearance?.distinguishing_features || ''} onChange={e => updApp('distinguishing_features', e.target.value)} placeholder="distinguishing features" />
        <textarea value={draft.emotional_baseline || ''} onChange={e => upd('emotional_baseline', e.target.value)} placeholder="emotional baseline" style={{ minHeight: 42 }} />
        <div className="char-foot">
          <button className="btn btn-ghost btn-sm" onClick={onCancelEdit}>Cancel</button>
          <button className="btn btn-navy btn-sm" onClick={() => onSaveEdit(draft)}>Save</button>
        </div>
      </div>
    );
  }

  return (
    <div className="char-card">
      <div className="char-id">CHAR {c.character_id}</div>
      <h4 className="char-name">{c.name}</h4>
      <div className="char-role">{c.role}</div>
      {c.appearance?.uniform && <div className="char-detail"><b>Wears:</b> {c.appearance.uniform}</div>}
      {c.emotional_baseline && <div className="char-detail"><b>Mood:</b> {c.emotional_baseline}</div>}
      <div className="char-foot">
        <button className="icon-btn" title="Edit character" onClick={onStartEdit}>{I.edit}</button>
      </div>
    </div>
  );
}

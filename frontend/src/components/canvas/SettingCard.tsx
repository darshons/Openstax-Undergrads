import type { ScriptSetting } from '../../types/script';

interface SettingCardProps {
  setting: ScriptSetting | undefined;
  onChange: (s: Partial<ScriptSetting>) => void;
}

export default function SettingCard({ setting, onChange }: SettingCardProps) {
  const upd = (k: string, v: string) => onChange({ ...(setting ?? {}), [k]: v } as Partial<ScriptSetting>);
  const s = setting ?? {} as Partial<ScriptSetting>;

  return (
    <div className="setting-card">
      <div className="setting-id">Scene Setting &amp; Background</div>
      <input
        className="setting-name-input"
        value={s.location || ''}
        onChange={e => upd('location', e.target.value)}
        placeholder="Location name — e.g. Hospital Room 204, Lecture Hall B"
      />
      <textarea
        className="setting-desc"
        value={s.scene_description || ''}
        onChange={e => upd('scene_description', e.target.value)}
        placeholder="Describe the overall environment: layout, furniture, props, anything visible on screen…"
      />
      <div className="setting-grid">
        <div className="setting-field">
          <label>Lighting</label>
          <input value={s.light_source || ''} onChange={e => upd('light_source', e.target.value)} placeholder="e.g. fluorescent overhead, warm lamp" />
        </div>
        <div className="setting-field">
          <label>Time of day</label>
          <input value={s.time_of_day || ''} onChange={e => upd('time_of_day', e.target.value)} placeholder="e.g. morning, early afternoon" />
        </div>
        <div className="setting-field">
          <label>Atmosphere / mood</label>
          <input value={s.atmosphere || ''} onChange={e => upd('atmosphere', e.target.value)} placeholder="e.g. clinical but warm, tense" />
        </div>
      </div>
    </div>
  );
}

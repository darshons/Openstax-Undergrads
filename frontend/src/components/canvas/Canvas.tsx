import type { Script, Scene, Character, DecisionPoint, ViewMode } from '../../types/script';
import CharacterCard from './CharacterCard';
import SettingCard from './SettingCard';
import TreeView from './TreeView';

interface CanvasProps {
  script: Script;
  selected: Set<string>;
  sceneCount: number;
  runtimeLabel: string;
  viewMode: ViewMode;
  density: string;
  editingSceneIdx: number | null;
  setEditingSceneIdx: (i: number | null) => void;
  editingCharacterIdx: number | null;
  setEditingCharacterIdx: (i: number | null) => void;
  saveSceneEdit: (idx: number, draft: Scene) => void;
  deleteScene: (idx: number) => void;
  moveScene: (from: number, to: number) => void;
  saveCharacterEdit: (idx: number, draft: Character) => void;
  updateDecisionPoint: (idx: number, dp: DecisionPoint) => void;
  addDecisionPoint: (sceneIdx: number) => void;
  deleteDecisionPoint: (dpIdx: number) => void;
  updateScriptField: <K extends keyof Script>(k: K, v: Script[K]) => void;
}

export default function Canvas({
  script, selected, sceneCount, runtimeLabel, viewMode, density,
  editingSceneIdx, setEditingSceneIdx,
  editingCharacterIdx, setEditingCharacterIdx,
  saveSceneEdit, deleteScene, moveScene, saveCharacterEdit,
  updateDecisionPoint, addDecisionPoint, deleteDecisionPoint, updateScriptField,
}: CanvasProps) {
  return (
    <>
      <div className="overview">
        <input
          className="overview-title"
          value={script.title || ''}
          onChange={e => updateScriptField('title', e.target.value)}
          placeholder="Script title"
        />
        <div className="overview-meta">
          <span><b>{sceneCount}</b> scenes</span>
          <span><b>{(script.characters ?? []).length}</b> characters</span>
          <span><b>{(script.decision_points ?? []).length}</b> decision points</span>
          <span><b>{runtimeLabel}</b> est. runtime</span>
          <span>Grounded in <b>{selected.size}</b> section{selected.size === 1 ? '' : 's'}</span>
        </div>
        <div className="overview-fields">
          <div className="overview-field">
            <label>Learning goal</label>
            <textarea value={script.learning_goal || ''} onChange={e => updateScriptField('learning_goal', e.target.value)} />
          </div>
          <div className="overview-field">
            <label>Target audience</label>
            <textarea value={script.target_audience || ''} onChange={e => updateScriptField('target_audience', e.target.value)} />
          </div>
          <div className="overview-field" style={{ gridColumn: '1 / -1' }}>
            <label>Visual style</label>
            <textarea value={script.visual_style || ''} onChange={e => updateScriptField('visual_style', e.target.value)} />
          </div>
        </div>
      </div>

      <div className="section-hd">
        <h2>Characters &amp; Setting <em>{(script.characters ?? []).length} character{(script.characters ?? []).length === 1 ? '' : 's'}</em></h2>
      </div>
      <div className="strip">
        <SettingCard
          setting={script.setting}
          onChange={s => updateScriptField('setting', s as Script['setting'])}
        />
        {(script.characters ?? []).map((c, i) => (
          <CharacterCard
            key={c.character_id || i}
            c={c}
            isEditing={editingCharacterIdx === i}
            onStartEdit={() => setEditingCharacterIdx(i)}
            onCancelEdit={() => setEditingCharacterIdx(null)}
            onSaveEdit={draft => saveCharacterEdit(i, draft)}
          />
        ))}
        {(script.characters ?? []).length === 0 && (
          <div style={{ padding: 14, color: 'var(--os-ink-3)', fontSize: 14, fontStyle: 'italic' }}>No characters defined.</div>
        )}
      </div>

      <div className="section-hd">
        <h2>Script flow <em>
          {sceneCount} scene{sceneCount === 1 ? '' : 's'}
          {(script.decision_points ?? []).length > 0
            ? ` · ${script.decision_points.length} decision point${script.decision_points.length === 1 ? '' : 's'}`
            : ''}
        </em></h2>
      </div>
      <TreeView
        script={script}
        density={density}
        viewMode={viewMode}
        editingSceneIdx={editingSceneIdx}
        setEditingSceneIdx={setEditingSceneIdx}
        saveSceneEdit={saveSceneEdit}
        deleteScene={deleteScene}
        moveScene={moveScene}
        updateDecisionPoint={updateDecisionPoint}
        addDecisionPoint={addDecisionPoint}
        deleteDecisionPoint={deleteDecisionPoint}
      />
    </>
  );
}

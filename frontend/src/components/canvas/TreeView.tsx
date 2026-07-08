import { useState, Fragment } from 'react';
import type { Script, Scene, DecisionPoint, Choice, ViewMode } from '../../types/script';
import { I } from '../shared/Icons';
import SceneCard from './SceneCard';

interface Segment {
  kind: 'trunk';
  scenes: Scene[];
}
interface BranchSegment {
  kind: 'branch';
  dp: DecisionPoint;
  branches: { choice: Choice; scene: Scene | null }[];
}
type AnySegment = Segment | BranchSegment;

function buildTreeSegments(scenes: Scene[], decisionPoints: DecisionPoint[]): AnySegment[] {
  if (!scenes || scenes.length === 0) return [];
  const dps = decisionPoints ?? [];
  const dpMap = new Map(dps.map(dp => [dp.decision_point_id, dp]));
  const sceneMap = new Map(scenes.map(s => [s.scene_id, s]));

  const branchSceneIds = new Set(
    dps.flatMap(dp => (dp.choices ?? []).map(c => c.routes_to_scene).filter((x): x is number => x != null)),
  );
  const trunk = scenes.filter(s => !branchSceneIds.has(s.scene_id));

  const dpIntroCount: Record<number, number> = {};
  for (const s of trunk) {
    const id = s.routes_to && 'decision_point_id' in s.routes_to ? s.routes_to.decision_point_id : null;
    if (id != null) dpIntroCount[id] = (dpIntroCount[id] ?? 0) + 1;
  }

  const visited = new Set<number>();
  const addedDps = new Set<number>();
  const dpIntroSeen: Record<number, number> = {};
  const rawSegs: ({ kind: 'scene'; scene: Scene } | BranchSegment)[] = [];

  for (const scene of trunk) {
    if (visited.has(scene.scene_id)) continue;
    rawSegs.push({ kind: 'scene', scene });
    visited.add(scene.scene_id);

    const dpId = scene.routes_to && 'decision_point_id' in scene.routes_to ? scene.routes_to.decision_point_id : null;
    if (dpId != null && !addedDps.has(dpId)) {
      dpIntroSeen[dpId] = (dpIntroSeen[dpId] ?? 0) + 1;
      if (dpIntroSeen[dpId] >= (dpIntroCount[dpId] ?? 1)) {
        const dp = dpMap.get(dpId);
        if (dp) {
          addedDps.add(dpId);
          const branches = (dp.choices ?? []).map(c => ({
            choice: c,
            scene: c.routes_to_scene != null ? (sceneMap.get(c.routes_to_scene) ?? null) : null,
          }));
          branches.forEach(b => { if (b.scene) visited.add(b.scene.scene_id); });
          rawSegs.push({ kind: 'branch', dp, branches });
        }
      }
    }
  }

  for (const scene of scenes) {
    if (!visited.has(scene.scene_id)) rawSegs.push({ kind: 'scene', scene });
  }

  const segments: AnySegment[] = [];
  let trunkGroup: Segment | null = null;
  for (const seg of rawSegs) {
    if (seg.kind === 'scene') {
      if (!trunkGroup) { trunkGroup = { kind: 'trunk', scenes: [] }; segments.push(trunkGroup); }
      trunkGroup.scenes.push(seg.scene);
    } else {
      trunkGroup = null;
      segments.push(seg);
    }
  }
  return segments;
}

function DPInlineEdit({ value, onSave, onCancel, placeholder }: { value: string; onSave: (v: string) => void; onCancel: () => void; placeholder?: string }) {
  const [draft, setDraft] = useState(value);
  return (
    <div className="dp-inline-edit">
      <textarea
        className="dp-inline-ta"
        value={draft}
        onChange={e => setDraft(e.target.value)}
        placeholder={placeholder}
        autoFocus
        rows={2}
        onKeyDown={e => { if (e.key === 'Enter' && e.metaKey) onSave(draft.trim()); if (e.key === 'Escape') onCancel(); }}
      />
      <div className="dp-inline-actions">
        <button className="btn btn-ghost btn-sm" onClick={onCancel}>Cancel</button>
        <button className="btn btn-navy btn-sm" onClick={() => onSave(draft.trim())}>Save</button>
      </div>
    </div>
  );
}

interface TreeViewProps {
  script: Script;
  density: string;
  viewMode: ViewMode;
  editingSceneIdx: number | null;
  setEditingSceneIdx: (i: number | null) => void;
  saveSceneEdit: (idx: number, draft: Scene) => void;
  deleteScene: (idx: number) => void;
  moveScene: (from: number, to: number) => void;
  updateDecisionPoint: (idx: number, dp: DecisionPoint) => void;
  addDecisionPoint: (sceneIdx: number) => void;
  deleteDecisionPoint: (dpIdx: number) => void;
}

export default function TreeView({
  script, density, viewMode, editingSceneIdx, setEditingSceneIdx,
  saveSceneEdit, deleteScene, moveScene, updateDecisionPoint, addDecisionPoint, deleteDecisionPoint,
}: TreeViewProps) {
  const scenes = script.scenes ?? [];
  const dps = script.decision_points ?? [];
  const characters = script.characters ?? [];
  const sceneIdxMap = new Map(scenes.map((s, i) => [s.scene_id, i]));
  const segments = buildTreeSegments(scenes, dps);
  const [editingChoice, setEditingChoice] = useState<{ dpId: number; idx: number } | null>(null);
  const [editingMisconception, setEditingMisconception] = useState<{ dpId: number; idx: number } | null>(null);
  const [editingDPQ, setEditingDPQ] = useState<number | null>(null);

  const getDpIdx = (dpId: number) => dps.findIndex(d => d.decision_point_id === dpId);

  const updateDP = (dpId: number, patch: Partial<DecisionPoint>) => {
    const dpIdx = getDpIdx(dpId);
    if (dpIdx < 0) return;
    updateDecisionPoint(dpIdx, { ...dps[dpIdx], ...patch });
  };

  const setCorrectChoice = (dpId: number, choiceIdx: number) => {
    const dpIdx = getDpIdx(dpId);
    if (dpIdx < 0) return;
    updateDecisionPoint(dpIdx, { ...dps[dpIdx], choices: dps[dpIdx].choices.map((c, i) => ({ ...c, is_correct: i === choiceIdx })) });
  };

  const saveChoiceText = (dpId: number, choiceIdx: number, text: string) => {
    const dpIdx = getDpIdx(dpId);
    if (dpIdx < 0) return;
    updateDecisionPoint(dpIdx, { ...dps[dpIdx], choices: dps[dpIdx].choices.map((c, i) => i === choiceIdx ? { ...c, text } : c) });
    setEditingChoice(null);
  };

  const saveMisconception = (dpId: number, choiceIdx: number, text: string) => {
    const dpIdx = getDpIdx(dpId);
    if (dpIdx < 0) return;
    updateDecisionPoint(dpIdx, { ...dps[dpIdx], choices: dps[dpIdx].choices.map((c, i) => i === choiceIdx ? { ...c, misconception: text } : c) });
    setEditingMisconception(null);
  };

  const addChoice = (dpId: number) => {
    const dpIdx = getDpIdx(dpId);
    if (dpIdx < 0) return;
    const dp = dps[dpIdx];
    const used = new Set(dp.choices.map(c => c.choice_id));
    const nextId = ['A','B','C','D','E','F'].find(id => !used.has(id)) ?? String(dp.choices.length + 1);
    updateDecisionPoint(dpIdx, {
      ...dp,
      choices: [...dp.choices, { choice_id: nextId, text: 'New choice', is_correct: false, routes_to_scene: null, misconception: '' }],
    });
  };

  const deleteChoice = (dpId: number, choiceIdx: number) => {
    const dpIdx = getDpIdx(dpId);
    if (dpIdx < 0) return;
    updateDecisionPoint(dpIdx, { ...dps[dpIdx], choices: dps[dpIdx].choices.filter((_, i) => i !== choiceIdx) });
  };

  const saveQuestionText = (dpId: number, text: string) => {
    updateDP(dpId, { question_text: text });
    setEditingDPQ(null);
  };

  return (
    <div className="tree-view">
      {segments.map((seg, si) => {
        if (seg.kind === 'trunk') {
          return (
            <div key={`trunk-${si}`} className="tree-node">
              {si > 0 && <div className="tree-vline" />}
              <div className="ribbon" style={{ flexWrap: 'wrap', justifyContent: 'center', paddingBottom: 0 }}>
                {seg.scenes.map((s, i) => {
                  const idx = sceneIdxMap.get(s.scene_id) ?? -1;
                  const prevIdx = i > 0 ? (sceneIdxMap.get(seg.scenes[i - 1].scene_id) ?? -1) : -1;
                  const nextIdx = i < seg.scenes.length - 1 ? (sceneIdxMap.get(seg.scenes[i + 1].scene_id) ?? -1) : -1;
                  return (
                    <Fragment key={s.scene_id ?? i}>
                      {i > 0 && <div className="connector">{I.arrow}</div>}
                      <SceneCard
                        s={s} characters={characters} decisionPoints={dps}
                        density={density} viewMode={viewMode}
                        isEditing={editingSceneIdx === idx}
                        onStartEdit={() => setEditingSceneIdx(idx)}
                        onCancelEdit={() => setEditingSceneIdx(null)}
                        onSaveEdit={draft => saveSceneEdit(idx, draft)}
                        onDelete={() => deleteScene(idx)}
                        onMoveLeft={prevIdx >= 0 ? () => moveScene(idx, prevIdx) : undefined}
                        onMoveRight={nextIdx >= 0 ? () => moveScene(idx, nextIdx) : undefined}
                        onAddDP={() => addDecisionPoint(idx)}
                        addDPDisabled={s.routes_to != null && 'decision_point_id' in s.routes_to && s.routes_to.decision_point_id != null}
                      />
                    </Fragment>
                  );
                })}
              </div>
            </div>
          );
        }

        if (seg.kind === 'branch') {
          return (
            <div key={`dp-${seg.dp.decision_point_id}`} className="tree-branch-frame">
              <div className="tree-vline" />
              <div className="tree-dp-node">
                <div className="tree-dp-badge">
                  Decision Point {seg.dp.decision_point_id}
                  <button
                    className="icon-btn"
                    style={{ marginLeft: 'auto', color: '#fff', opacity: 0.6 }}
                    title="Delete this decision point and its branch scenes"
                    onClick={() => deleteDecisionPoint(getDpIdx(seg.dp.decision_point_id))}
                  >
                    {I.trash}
                  </button>
                </div>
                {editingDPQ === seg.dp.decision_point_id ? (
                  <DPInlineEdit
                    value={seg.dp.question_text}
                    onSave={text => saveQuestionText(seg.dp.decision_point_id, text)}
                    onCancel={() => setEditingDPQ(null)}
                    placeholder="Question text"
                  />
                ) : (
                  <div className="tree-dp-question" onClick={() => setEditingDPQ(seg.dp.decision_point_id)} title="Click to edit question">
                    {seg.dp.question_text}
                    <span className="dp-edit-hint">{I.edit}</span>
                  </div>
                )}
              </div>
              <div className="tree-branch-row">
                {seg.branches.map((b, bi) => {
                  const i = b.scene ? (sceneIdxMap.get(b.scene.scene_id) ?? -1) : -1;
                  const isEditingThisChoice = editingChoice?.dpId === seg.dp.decision_point_id && editingChoice?.idx === bi;
                  const isEditingThisMisconception = editingMisconception?.dpId === seg.dp.decision_point_id && editingMisconception?.idx === bi;
                  return (
                    <div key={b.choice.choice_id ?? bi} className="tree-branch-col">
                      <div className="tree-vline-sm" />
                      <div className={`choice-pill ${b.choice.is_correct ? 'correct-pill' : 'wrong-pill'}`}>
                        <div className="choice-pill-hd">
                          <span className="choice-id-label">{b.choice.choice_id}</span>
                          {b.choice.is_correct ? (
                            <span className="correct-badge">✓ Correct</span>
                          ) : (
                            <button className="mark-correct-btn" onClick={() => setCorrectChoice(seg.dp.decision_point_id, bi)} title="Mark as correct answer">
                              Mark correct
                            </button>
                          )}
                          <button className="icon-btn" style={{ width: 22, height: 22, marginLeft: 'auto' }} title="Edit choice text" onClick={() => setEditingChoice({ dpId: seg.dp.decision_point_id, idx: bi })}>
                            {I.edit}
                          </button>
                          <button className="icon-btn" style={{ width: 22, height: 22, color: 'var(--os-ink-3)' }} title="Delete choice" onClick={() => deleteChoice(seg.dp.decision_point_id, bi)}>
                            {I.trash}
                          </button>
                        </div>
                        {isEditingThisChoice ? (
                          <DPInlineEdit
                            value={b.choice.text}
                            onSave={text => saveChoiceText(seg.dp.decision_point_id, bi, text)}
                            onCancel={() => setEditingChoice(null)}
                            placeholder="Choice text"
                          />
                        ) : (
                          <span className="choice-text">{b.choice.text}</span>
                        )}
                        <div className="choice-misconception-row">
                          {isEditingThisMisconception ? (
                            <DPInlineEdit
                              value={b.choice.misconception ?? ''}
                              onSave={text => saveMisconception(seg.dp.decision_point_id, bi, text)}
                              onCancel={() => setEditingMisconception(null)}
                              placeholder="Why this is wrong (misconception)…"
                            />
                          ) : (
                            <div
                              className="choice-misconception"
                              onClick={() => setEditingMisconception({ dpId: seg.dp.decision_point_id, idx: bi })}
                              title="Click to edit misconception"
                            >
                              {b.choice.misconception
                                ? <><span className="choice-misconception-label">Misconception:</span> {b.choice.misconception}</>
                                : <span className="choice-misconception-empty">+ Add misconception</span>}
                            </div>
                          )}
                        </div>
                      </div>
                      {b.scene ? (
                        <>
                          <div className="tree-vline-sm" />
                          <div className="tree-branch-scene-wrap">
                            <SceneCard
                              s={b.scene} characters={characters} decisionPoints={dps}
                              density="compact" viewMode={viewMode}
                              isEditing={editingSceneIdx === i}
                              onStartEdit={() => setEditingSceneIdx(i)}
                              onCancelEdit={() => setEditingSceneIdx(null)}
                              onSaveEdit={draft => saveSceneEdit(i, draft)}
                              onDelete={() => deleteScene(i)}
                            />
                          </div>
                          {b.choice.is_correct
                            ? <div className="continues-badge">↓ continues</div>
                            : <div className="retry-badge">↺ returns to decision point</div>}
                        </>
                      ) : (
                        <div style={{ fontSize: 11, color: 'var(--os-ink-3)', fontStyle: 'italic', padding: '10px 0' }}>no scene linked</div>
                      )}
                    </div>
                  );
                })}
                <div className="add-choice-col">
                  <div className="tree-vline-sm" />
                  <button className="add-choice-btn" onClick={() => addChoice(seg.dp.decision_point_id)}>
                    {I.plus} Add choice
                  </button>
                </div>
              </div>
            </div>
          );
        }

        return null;
      })}
    </div>
  );
}

import { useState, useRef, useEffect } from 'react';
import type { Script, ViewMode, Page, VideoType } from '../../types/script';
import { I } from '../shared/Icons';

function exportJSON(script: Script) {
  const blob = new Blob([JSON.stringify(script, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'scenario_script.json'; a.click();
  URL.revokeObjectURL(url);
}

function exportMarkdown(script: Script) {
  const lines: string[] = [];
  lines.push(`# ${script.title || 'Untitled Script'}\n`);
  lines.push(`**Scenes:** ${(script.scenes ?? []).length} · **Characters:** ${(script.characters ?? []).length} · **Decision Points:** ${(script.decision_points ?? []).length}\n`);
  lines.push('---\n');
  (script.scenes ?? []).forEach((s, i) => {
    lines.push(`## Scene ${i + 1}: ${s.scene_summary || s.scene_id}`);
    if (s.setting) lines.push(`\n*Setting:* ${s.setting}`);
    lines.push('');
    (s.audio?.dialogue ?? []).forEach(dl => {
      lines.push(`**${dl.character_id}:** ${dl.line}`);
    });
    if (s.routes_to && 'decision_point_id' in s.routes_to && s.routes_to.decision_point_id != null) {
      lines.push(`\n*→ Routes to Decision Point ${s.routes_to.decision_point_id}*`);
    }
    lines.push('\n---\n');
  });
  if ((script.decision_points ?? []).length > 0) {
    lines.push('## Decision Points\n');
    script.decision_points.forEach(dp => {
      lines.push(`### DP ${dp.decision_point_id}: ${dp.question_text}`);
      (dp.choices ?? []).forEach(c => {
        lines.push(`- ${c.is_correct ? '✓' : '✗'} **${c.choice_id}:** ${c.text}`);
      });
      lines.push('');
    });
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'scenario_script.md'; a.click();
  URL.revokeObjectURL(url);
}

function ExportMenu({ script }: { script: Script | null }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div className="export-wrap" ref={ref}>
      <button className="btn btn-ghost btn-sm" disabled={!script} onClick={() => setOpen(o => !o)}>
        Export ▾
      </button>
      {open && script && (
        <div className="export-menu">
          <button onClick={() => { exportJSON(script); setOpen(false); }}>
            <span className="exp-icon">{'{}'}</span> JSON
          </button>
          <button onClick={() => { exportMarkdown(script); setOpen(false); }}>
            <span className="exp-icon">＃</span> Markdown
          </button>
        </div>
      )}
    </div>
  );
}

interface StageBarProps {
  script: Script | null;
  busy: boolean;
  sceneCount: number;
  runtimeLabel: string;
  sidebarOpen: boolean;
  setSidebarOpen: (fn: (o: boolean) => boolean) => void;
  deleteUndoStack: Script[];
  undoDelete: () => void;
  zoom: number;
  setZoom: (fn: (z: number) => number) => void;
  viewMode: ViewMode;
  setViewMode: (v: ViewMode) => void;
  videoType: VideoType;
  setCurrentPage: (p: Page) => void;
}

export default function StageBar({
  script, busy, sceneCount, runtimeLabel,
  sidebarOpen, setSidebarOpen,
  deleteUndoStack, undoDelete,
  zoom, setZoom, viewMode, setViewMode,
  videoType, setCurrentPage,
}: StageBarProps) {
  return (
    <>
      <div className="stage-bar">
        <div className="stage-bar-l">
          <button className="sidebar-toggle" onClick={() => setSidebarOpen(o => !o)} title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}>
            {sidebarOpen ? '‹' : '›'}
          </button>
          <h2 className="stage-title">
            Storyboard canvas <em>{script ? `${sceneCount} scenes · ${runtimeLabel}` : 'no script yet'}</em>
          </h2>
          <div className={`stage-status ${busy ? 'busy' : script ? 'ready' : ''}`}>
            <span className="dot" />
            {busy ? 'Generating' : script ? 'Draft ready' : 'Idle'}
          </div>
        </div>
        <div className="stage-bar-r">
          <button
            className="btn btn-ghost btn-sm"
            onClick={undoDelete}
            disabled={deleteUndoStack.length === 0}
            title={deleteUndoStack.length > 0 ? `Undo last delete (${deleteUndoStack.length} available)` : 'Nothing to undo'}
          >
            ↩ Undo{deleteUndoStack.length > 0 ? ` (${deleteUndoStack.length})` : ''}
          </button>
          <div className="view-mode-ctl">
            <span className="view-mode-lbl">View:</span>
            <select className="view-mode-select" value={viewMode} onChange={e => setViewMode(e.target.value as ViewMode)}>
              <option value="full">Full script</option>
              <option value="dialogue">Dialogue</option>
              <option value="action">Action</option>
              <option value="camera">Camera</option>
            </select>
          </div>
          <div className="zoom-ctl">
            <button onClick={() => setZoom(z => Math.max(50, z - 10))}>−</button>
            <span className="zv">{zoom}%</span>
            <button onClick={() => setZoom(z => Math.min(150, z + 10))}>+</button>
          </div>
          <ExportMenu script={script} />
        </div>
      </div>

      {script && (
        <div className="assets-next-strip">
          <div className="assets-next-strip-l">
            <span className="assets-next-step-label">Next step</span>
            <span className="assets-next-step-desc">
              {videoType === 'manim'
                ? 'Script is ready — preview the generated Manim animations'
                : 'Script is ready — review and customize the video assets'}
            </span>
          </div>
          <button className="btn-assets" onClick={() => setCurrentPage(videoType === 'manim' ? 'videos' : 'assets')}>
            {videoType === 'manim' ? 'View Videos' : 'View Assets'} {I.arrowRight}
          </button>
        </div>
      )}
    </>
  );
}

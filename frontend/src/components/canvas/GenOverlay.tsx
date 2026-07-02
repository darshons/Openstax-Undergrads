import { I } from '../shared/Icons';

const STEPS = [
  'Reading selected sections',
  'Extracting key concepts',
  'Drafting scene-by-scene script',
  'Adding citations and on-screen text',
];

export default function GenOverlay({ step }: { step: number }) {
  return (
    <div className="gen-overlay">
      <div className="gen-card">
        <h3>Generating script…</h3>
        <p>Grounding scenes in the chapters you selected</p>
        <div className="gen-steps">
          {STEPS.map((s, i) => (
            <div key={i} className={`gen-step ${i < step ? 'done' : i === step ? 'active' : ''}`}>
              <span className="gen-step-i">{I.check}</span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

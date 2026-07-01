import { useState } from 'react';
import { CATALOG } from '../../data/catalog';
import { I } from '../shared/Icons';

interface SidebarProps {
  selected: Set<string>;
  toggleSec: (id: string) => void;
  toggleChap: (bookId: string, chapN: string, secNs: string[]) => void;
  search: string;
  setSearch: (s: string) => void;
  filter: string;
  setFilter: (f: string) => void;
}

const SUBJECTS = ['All', 'Biology', 'Chemistry', 'Physics', 'Economics', 'Psychology'];

export default function Sidebar({ selected, toggleSec, toggleChap, search, setSearch, filter, setFilter }: SidebarProps) {
  const [openBooks, setOpenBooks] = useState<Record<string, boolean>>({ biology2e: true });
  const [openChaps, setOpenChaps] = useState<Record<string, boolean>>({ 'biology2e:09': true });

  const matches = (s: string) => !search || s.toLowerCase().includes(search.toLowerCase());

  return (
    <aside style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
      <div className="sb-head">
        <h2 className="sb-title">Source library</h2>
        <h3 className="sb-h1">Pick chapters &amp; sections to ground the script</h3>
        <label className="sb-search">
          {I.search}
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search books, chapters, sections…" />
        </label>
      </div>
      <div className="sb-filters">
        {SUBJECTS.map(s => (
          <button key={s} className={`sb-chip ${filter === s ? 'on' : ''}`} onClick={() => setFilter(s)}>{s}</button>
        ))}
      </div>

      <div className="sb-list">
        {CATALOG.map(book => {
          const open = openBooks[book.id];
          const chapters = book.chapters;
          const selCount = chapters.reduce(
            (acc, c) => acc + c.secs.filter(s => selected.has(`${book.id}:${c.n}:${s.n}`)).length,
            0,
          );
          return (
            <div key={book.id} className="book">
              <div
                className={`book-row ${open ? 'open' : ''}`}
                onClick={() => setOpenBooks(o => ({ ...o, [book.id]: !o[book.id] }))}
              >
                <div className="book-spine" style={{ background: book.color }} />
                <div className="book-meta">
                  <div className="book-title">{book.title}</div>
                  <div className="book-sub">{book.sub}</div>
                </div>
                <div className={`book-count ${selCount > 0 ? 'has' : ''}`}>
                  {selCount > 0 ? selCount : chapters.reduce((a, c) => a + c.secs.length, 0)}
                </div>
                <div className="book-caret">{I.caret}</div>
              </div>

              {open && (
                <div className="chapters">
                  {chapters.map(c => {
                    const key = `${book.id}:${c.n}`;
                    const chapOpen = openChaps[key];
                    const chapSel = c.secs.filter(s => selected.has(`${key}:${s.n}`)).length;
                    return (
                      <div key={c.n} className="chap">
                        <div
                          className={`chap-row ${chapOpen ? 'open' : ''}`}
                          onClick={() => setOpenChaps(o => ({ ...o, [key]: !o[key] }))}
                        >
                          <span
                            className={`chap-sel ${chapSel === c.secs.length ? 'all' : chapSel > 0 ? 'some' : ''}`}
                            onClick={e => {
                              e.stopPropagation();
                              toggleChap(book.id, c.n, c.secs.map(s => s.n));
                            }}
                          >
                            {chapSel > 0 && (
                              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="20 6 9 17 4 12"/>
                              </svg>
                            )}
                          </span>
                          <span className="chap-num">CH {c.n}</span>
                          <span className="chap-name">{c.name}</span>
                          <span className="chap-caret">{I.caret}</span>
                        </div>
                        {chapOpen && (
                          <div className="sections">
                            {c.secs.filter(s => matches(s.t)).map(s => {
                              const id = `${key}:${s.n}`;
                              const on = selected.has(id);
                              return (
                                <div key={s.n} className={`sec-row ${on ? 'on' : ''}`} onClick={() => toggleSec(id)}>
                                  <span className="sec-check">{I.check}</span>
                                  <span className="sec-num">§{s.n}</span>
                                  <span className="sec-name">{s.t}</span>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
}

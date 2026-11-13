import React, { useEffect, useState } from 'react';
import { ArrowLeft, Camera } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

// The photos come from Wikimedia Commons under free licenses; the data pack asks every app that shows them to show
// these credits too. The list is read from the pack's own images/ATTRIBUTIONS.md, which the backend serves.
const LINK = /\[([^\]]+)\]\(([^)]+)\)/;

function Cell({ text }) {
  const m = LINK.exec(text);
  if (!m) return <>{text.replaceAll('`', '')}</>;
  return <a href={m[2]} target="_blank" rel="noreferrer" className="text-[#006ce4] hover:underline">{m[1]}</a>;
}

function parse(markdown) {
  return markdown.split('\n')
    .filter((l) => l.startsWith('| `images/'))
    .map((l) => l.split('|').slice(1, -1).map((c) => c.trim()))
    .filter((cells) => cells.length >= 5);
}

export default function CreditsPage() {
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true });

  useEffect(() => {
    let cancelled = false;
    fetch('/images/ATTRIBUTIONS.md')
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error('missing'))))
      .then((t) => { if (!cancelled) setState({ rows: parse(t) }); })
      .catch(() => { if (!cancelled) setState({ error: true }); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-5">
      <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-xs font-bold text-[#006ce4] hover:underline">
        <ArrowLeft className="w-4 h-4" /> Back
      </button>
      <div>
        <h2 className="flex items-center gap-2 text-xl font-extrabold text-[#003580]"><Camera className="w-5 h-5 text-[#febb02]" /> Photo credits</h2>
        <p className="text-xs text-slate-600 mt-1">
          All photos come from Wikimedia Commons and are public domain or Creative Commons licensed. Attraction photos show the real place;
          hotel photos are generic room photos, because the hotels in our data are fictional.
        </p>
      </div>
      {state.loading && <p className="text-xs text-slate-500">Loading credits…</p>}
      {state.error && <p className="text-xs text-[#d4111e] font-bold">The credits list could not be loaded.</p>}
      {state.rows && (
        <div className="bg-white border border-slate-300 rounded-xl shadow-sm overflow-x-auto">
          <table className="w-full text-xs" data-testid="credits-table">
            <thead className="bg-[#003580] text-white text-left">
              <tr><th className="px-3 py-2">Used for</th><th className="px-3 py-2">Source</th><th className="px-3 py-2">Author</th><th className="px-3 py-2">License</th></tr>
            </thead>
            <tbody>
              {state.rows.map((r) => (
                <tr key={r[0]} className="border-t border-slate-100 align-top">
                  <td className="px-3 py-2 font-semibold text-slate-800">{r[1]}</td>
                  <td className="px-3 py-2"><Cell text={r[2]} /></td>
                  <td className="px-3 py-2 text-slate-600">{r[3]}</td>
                  <td className="px-3 py-2"><Cell text={r[4]} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

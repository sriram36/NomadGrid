import React, { useEffect, useState } from 'react';
import { Camera } from 'lucide-react';

// Photo credits: the app shows photos, so it shows who took them (the list ships with the catalog images).
function parseCredits(markdown) {
  const rows = [];
  for (const line of markdown.split('\n')) {
    if (!line.startsWith('| `images/')) continue;
    const cells = line.split('|').map((c) => c.trim());
    const link = (text) => {
      const m = /\[(.*?)\]\((.*?)\)/.exec(text);
      return m ? { label: m[1], href: m[2] } : { label: text, href: null };
    };
    rows.push({
      file: cells[1].replaceAll('`', ''),
      usedFor: cells[2],
      source: link(cells[3]),
      author: cells[4],
      license: link(cells[5]),
    });
  }
  return rows;
}

export default function CreditsPage() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch('/images/ATTRIBUTIONS.md')
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error('missing'))))
      .then((t) => setRows(parseCredits(t)))
      .catch(() => setError(true));
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-4">
      <div className="bg-white rounded-xl border border-slate-300 p-6">
        <div className="flex items-center gap-2">
          <Camera className="w-5 h-5 text-[#006ce4]" />
          <h2 className="text-xl font-extrabold text-[#003580]">Photo credits</h2>
        </div>
        <p className="text-xs text-slate-600 mt-1">
          All photos come from Wikimedia Commons under free licences. Attraction photos show the real place; the hotels
          in this app are fictional, so several share one generic room photo.
        </p>
      </div>

      {error && <p className="text-sm text-[#d4111e] font-bold">The credits list could not be loaded.</p>}
      {!error && rows === null && <p className="text-sm text-slate-500">Loading credits…</p>}
      {rows && (
        <div className="bg-white rounded-xl border border-slate-300 overflow-x-auto" data-testid="credits-table">
          <table className="w-full text-xs">
            <thead className="bg-[#f2f6fa] text-left text-[11px] uppercase tracking-wider text-slate-600">
              <tr><th className="p-3">Used for</th><th className="p-3">Source</th><th className="p-3">Author</th><th className="p-3">License</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.file} className="border-t border-slate-100 align-top">
                  <td className="p-3 font-semibold text-slate-800">{r.usedFor}</td>
                  <td className="p-3">{r.source.href ? <a href={r.source.href} target="_blank" rel="noreferrer" className="text-[#006ce4] hover:underline">{r.source.label}</a> : r.source.label}</td>
                  <td className="p-3 text-slate-700">{r.author}</td>
                  <td className="p-3">{r.license.href ? <a href={r.license.href} target="_blank" rel="noreferrer" className="text-[#006ce4] hover:underline">{r.license.label}</a> : r.license.label}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import { X, BookOpen, Utensils, Footprints, Info } from 'lucide-react';
import { getCityCompanion, DINING_DISCLAIMER } from '../data/cityCompanionData';
import { formatINR } from '../lib/format';

// S2 + S3: a read-only slide-over with the city's practical tips and nearby dining.
// It only reads static data, so opening it never changes the itinerary, the total or the export.
export default function CityGuideDrawer({ city, area, onClose }) {
  const [tab, setTab] = useState('guide');
  const guide = city ? getCityCompanion(city) : null;

  useEffect(() => {
    if (!city) return undefined;
    setTab('guide');
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [city, onClose]);

  if (!city) return null;

  // Dining in the hotel's own area comes first.
  const dining = [...(guide?.dining || [])].sort((a, b) => Number(b.area === area) - Number(a.area === area));

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={`${city} city guide`}>
      <button type="button" aria-label="Close city guide" onClick={onClose} className="absolute inset-0 bg-slate-900/50" />

      <aside className="relative w-full max-w-md h-full bg-white shadow-xl flex flex-col" data-testid="city-guide">
        <header className="bg-[#003580] text-white px-5 py-4 flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-black uppercase tracking-wider text-[#febb02]">Pocket city guide</p>
            <h2 className="text-lg font-black tracking-tight">{city}</h2>
            {guide && <p className="text-xs text-white/80 mt-0.5">{guide.tagline}</p>}
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1 rounded hover:bg-white/10">
            <X className="size-5" />
          </button>
        </header>

        <div className="flex border-b border-slate-200 text-xs font-bold">
          {[
            { key: 'guide', label: 'Tips', icon: BookOpen },
            { key: 'dining', label: 'Nearby dining', icon: Utensils },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              aria-pressed={tab === key}
              className={`flex-1 py-3 flex items-center justify-center gap-1.5 border-b-2 transition-colors ${
                tab === key ? 'border-[#006ce4] text-[#006ce4]' : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Icon className="size-4" /> {label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-3">
          {!guide && <p className="text-sm text-slate-600">We do not have a guide for {city} yet.</p>}

          {guide && tab === 'guide' && guide.tips.map((t) => (
            <div key={t.topic} className="rounded-lg border border-slate-200 bg-[#f2f6fa] p-3.5">
              <p className="text-[11px] font-black uppercase tracking-wider text-[#003580]">{t.topic}</p>
              <p className="text-xs text-slate-700 mt-1 leading-relaxed">{t.text}</p>
            </div>
          ))}

          {guide && tab === 'dining' && (
            <>
              <div className="flex items-start gap-2 rounded-lg border border-[#febb02] bg-[#fff9e6] p-3 text-[11px] font-bold text-slate-800" data-testid="dining-disclaimer">
                <Info className="size-4 shrink-0 text-[#b45309]" />
                <span>{DINING_DISCLAIMER}</span>
              </div>
              {area && <p className="text-[11px] text-slate-500">Spots in {area}, where your hotel is, are listed first.</p>}
              {dining.map((d) => {
                const near = d.area === area;
                return (
                  <div key={d.name} className="rounded-lg border border-slate-200 p-3.5 shadow-xs">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-extrabold text-[#003580]">{d.name}</p>
                        <p className="text-[11px] text-slate-500">{d.cuisine} · {d.area}</p>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-sm font-black text-slate-900 tabular-nums">~{formatINR(d.costInr)}</p>
                        <p className="text-[10px] text-slate-500">per person</p>
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      {d.tags.map((tag) => (
                        <span key={tag} className="px-1.5 py-0.5 rounded bg-emerald-50 text-[#008009] border border-emerald-200 text-[10px] font-bold">{tag}</span>
                      ))}
                      <span className="flex items-center gap-1 text-[10px] font-semibold text-slate-600 ml-auto">
                        <Footprints className="size-3" />
                        {near ? `${d.walkMin} min walk from your hotel` : `${d.walkMin} min walk in ${d.area}; a short ride from your hotel`}
                      </span>
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

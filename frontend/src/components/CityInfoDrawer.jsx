import { useEffect, useState } from 'react';
import { X, BookOpen, Utensils, Train, HeartHandshake, Camera, Info } from 'lucide-react';
import { api, NetworkError } from '../api/client';

// S2 / S3: a read-only drawer for a hotel stay: the pocket city guide, or nearby dining.
// Both are separate static content on the server: they never change the package or its price.
const SECTIONS = [
  ['getting_around', 'Getting around', Train],
  ['etiquette', 'Etiquette', HeartHandshake],
  ['sightseeing_tips', 'Sightseeing tips', Camera],
  ['good_to_know', 'Good to know', Info],
];

function Guide({ guide }) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-600 font-medium">{guide.tagline}</p>
      {SECTIONS.map(([key, title, Icon]) => guide[key]?.length ? (
        <div key={key}>
          <h4 className="flex items-center gap-1.5 text-xs font-extrabold text-[#003580] mb-1"><Icon className="w-3.5 h-3.5 text-[#006ce4]" /> {title}</h4>
          <ul className="list-disc pl-5 space-y-1 text-xs text-slate-700">
            {guide[key].map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </div>
      ) : null)}
      <p className="text-[10px] text-slate-400">{guide.source}</p>
    </div>
  );
}

function Dining({ stay, disclaimer }) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-600 font-medium">Near {stay.hotel} · {stay.area}, {stay.city}</p>
      <ul className="space-y-2.5" data-testid="dining-list">
        {stay.restaurants.map((r) => (
          <li key={r.name} className="p-3 rounded-lg border border-slate-300 bg-white text-xs">
            <div className="flex items-start justify-between gap-2">
              <span className="font-extrabold text-[#003580]">{r.name}</span>
              <span className="font-black text-slate-900 tabular-nums shrink-0">{r.price_label}</span>
            </div>
            <div className="text-slate-500 text-[11px] mt-0.5">{r.cuisine}</div>
            <div className="text-slate-600 text-[11px] mt-1">{r.note}</div>
            {r.dietary_tags?.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1.5">
                {r.dietary_tags.map((t) => (
                  <span key={t} className="px-1.5 py-0.5 rounded bg-emerald-50 text-[#008009] border border-emerald-200 text-[10px] font-bold">
                    {t.replaceAll('_', ' ').toLowerCase()}
                  </span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
      <p className="p-2.5 rounded bg-[#fff9e6] border border-[#febb02] text-[11px] text-slate-700 font-semibold" data-testid="dining-disclaimer">
        {disclaimer}
      </p>
    </div>
  );
}

export default function CityInfoDrawer({ info, packageId, onClose }) {
  const [state, setState] = useState({ loading: true });

  useEffect(() => {
    if (!info) return undefined;
    let cancelled = false;
    setState({ loading: true });
    (async () => {
      try {
        if (info.kind === 'guide') {
          const { status, data } = await api.cityGuide(info.city);
          if (!cancelled) setState(status === 200 ? { guide: data } : { error: data?.error?.message || 'No guide for this city yet.' });
        } else {
          const { status, data } = await api.dining(packageId);
          const stay = status === 200 ? (data.stays || []).find((s) => s.item_id === info.itemId) : null;
          if (!cancelled) setState(stay ? { stay, disclaimer: data.disclaimer } : { error: 'No dining suggestions for this hotel yet.' });
        }
      } catch (e) {
        if (!cancelled) setState({ error: e instanceof NetworkError ? e.message : 'We could not load this right now.' });
      }
    })();
    return () => { cancelled = true; };
  }, [info, packageId]);

  if (!info) return null;
  const Icon = info.kind === 'guide' ? BookOpen : Utensils;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-[#003580]/40 backdrop-blur-xs" role="dialog" aria-modal="true"
      aria-label={info.kind === 'guide' ? `Pocket guide: ${info.city}` : `Nearby dining: ${info.city}`} onClick={onClose}>
      <aside className="w-full max-w-md h-full bg-[#f2f6fa] shadow-2xl overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 bg-[#003580] text-white">
          <h3 className="flex items-center gap-2 text-sm font-extrabold">
            <Icon className="w-4 h-4 text-[#febb02]" />
            {info.kind === 'guide' ? `Pocket guide · ${info.city}` : `Nearby dining · ${info.city}`}
          </h3>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded hover:bg-white/10"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-5">
          {state.loading && <div className="py-10 flex justify-center"><div className="w-8 h-8 border-4 border-[#003580] border-t-[#febb02] rounded-full animate-spin" /></div>}
          {state.error && <p className="text-xs text-[#d4111e] font-bold">{state.error}</p>}
          {state.guide && <Guide guide={state.guide} />}
          {state.stay && <Dining stay={state.stay} disclaimer={state.disclaimer} />}
        </div>
      </aside>
    </div>
  );
}

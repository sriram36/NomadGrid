import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Wallet, Star } from 'lucide-react';
import { api } from '../api/client';
import { formatINR } from '../lib/format';
import { useApp } from '../context/AppContext';

// Variants already fetched for a request, so switching between them does not ask the backend again.
const cache = new Map();

const CARDS = [
  { key: 'recommended', title: 'Recommended', icon: Sparkles, pick: (v) => v.recommended },
  { key: 'cheapest', title: 'Cheapest', icon: Wallet, pick: (v) => v.variants?.cheapest },
  { key: 'best', title: 'Best', icon: Star, pick: (v) => v.variants?.best_rated },
];

// A package from a plain search is labelled DEFAULT: it is the same holiday as the Recommended one.
const CARD_OF_VARIANT = { DEFAULT: 'recommended', RECOMMENDED: 'recommended', CHEAPEST: 'cheapest', BEST_RATED: 'best' };

const visitCount = (p) => (p.items || []).filter((i) => i.type === 'attraction').length;

function highlight(key, p) {
  const sights = visitCount(p);
  if (key === 'cheapest') return `Lowest total · ${sights} sights`;
  if (key === 'best') return `${p.metrics.avg_hotel_stars}★ hotels · ${sights} sights`;
  return 'Balanced price, flights and hotel';
}

// S4: pick Recommended, Cheapest or Best with one click. Each is a complete, rule-checked package from the backend.
export default function VariantBar({ pkg }) {
  const navigate = useNavigate();
  const { variants: fromCompare } = useApp();
  const request = pkg.request;
  const key = useMemo(() => (request ? JSON.stringify(request) : ''), [request]);
  const [data, setData] = useState(() => cache.get(key) || null);

  useEffect(() => {
    if (!key) return undefined;
    if (cache.has(key)) { setData(cache.get(key)); return undefined; }
    // Packages opened from the compare screen already carry their siblings.
    const ids = fromCompare ? [fromCompare.recommended, ...Object.values(fromCompare.variants || {})].filter(Boolean).map((p) => p.package_id) : [];
    if (fromCompare && ids.includes(pkg.package_id)) {
      cache.set(key, fromCompare);
      setData(fromCompare);
      return undefined;
    }
    let cancelled = false;
    api.variants(request).then(({ status, data: body }) => {
      if (cancelled) return;
      if (status === 200 && body?.outcome === 'VARIANTS') { cache.set(key, body); setData(body); }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [key, pkg.package_id]);

  if (!data) return null;
  const cards = CARDS.map((c) => ({ ...c, p: c.pick(data) })).filter((c) => c.p);
  if (cards.length < 2) return null;

  const active = cards.find((c) => c.p.package_id === pkg.package_id) || cards.find((c) => c.key === CARD_OF_VARIANT[pkg.variant]);

  return (
    <section aria-label="Choose a package variant" data-testid="variant-bar">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {cards.map(({ key: k, title, icon: Icon, p }) => {
          const isActive = active?.key === k;
          return (
            <button
              key={k}
              type="button"
              data-testid={`variant-card-${k}`}
              aria-pressed={isActive}
              onClick={() => { if (!isActive) navigate(`/packages/${p.package_id}`); }}
              className={`text-left rounded-xl border-2 p-4 bg-white shadow-xs transition-colors ${
                isActive ? 'border-[#006ce4] bg-[#006ce4]/5' : 'border-slate-300 hover:border-[#003580]'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 text-sm font-extrabold text-[#003580]">
                  <Icon className="size-4 text-[#006ce4]" /> {title}
                </span>
                {isActive && <span className="text-[10px] font-black uppercase tracking-wider text-white bg-[#006ce4] px-1.5 py-0.5 rounded">Viewing</span>}
              </div>
              <div className="mt-2 text-xl font-black text-[#003580] tabular-nums">{formatINR(p.pricing.total_inr)}</div>
              <div className="text-[11px] text-slate-600 font-semibold">{p.metrics.avg_hotel_stars}★ average hotel · {p.city_plan.map((c) => c.city).join(' → ')}</div>
              <div className="mt-1 text-[11px] text-slate-500">{highlight(k, p)}</div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

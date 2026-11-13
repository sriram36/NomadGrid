import React from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Wallet, Timer, Star, Sparkles } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { formatINR, hoursMinutes } from '../lib/format';

const CARDS = [
  { key: 'recommended', title: 'Recommended', blurb: 'The best holiday we can build near your budget.', icon: Sparkles },
  { key: 'cheapest', title: 'Cheapest', blurb: 'The lowest total price.', icon: Wallet },
  { key: 'fastest', title: 'Fastest', blurb: 'The least time in flights and between cities.', icon: Timer },
  { key: 'best_rated', title: 'Best rated', blurb: 'The highest hotel stars within your budget.', icon: Star },
];

// G4: the traveler compares the packages and picks one.
export default function ComparePage() {
  const navigate = useNavigate();
  const { variants } = useApp();
  if (!variants) return <Navigate to="/" replace />;

  const pick = (key) => (key === 'recommended' ? variants.recommended : variants.variants?.[key]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <button onClick={() => navigate('/', { state: { edit: true } })} className="flex items-center gap-2 text-xs font-bold text-[#006ce4] hover:underline">
        <ArrowLeft className="w-4 h-4" /> Edit the trip
      </button>
      <div>
        <h2 className="text-xl font-extrabold text-[#003580]">Pick the holiday that suits you</h2>
        <p className="text-xs text-slate-600 mt-1">Every one is complete, follows every rule and fits your budget. Open one to change anything.</p>
        {(variants.notes || []).map((n, i) => <p key={i} className="text-[11px] text-slate-500 mt-1">• {n}</p>)}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {CARDS.map(({ key, title, blurb, icon: Icon }) => {
          const p = pick(key);
          if (!p) return null;
          return (
            <div key={key} className="bg-white rounded-xl border border-slate-300 p-5 flex flex-col justify-between hover:border-[#003580] transition-colors" data-testid={`variant-${key}`}>
              <div>
                <div className="flex items-center gap-2 text-sm font-extrabold text-[#003580]"><Icon className="w-4 h-4 text-[#006ce4]" /> {title}</div>
                <p className="text-[11px] text-slate-500 mt-0.5">{blurb}</p>
                <div className="mt-3 text-xs font-bold text-slate-800">
                  {p.city_plan.map((c) => `${c.city} (${c.nights}N)`).join(' → ')}
                </div>
                <dl className="mt-2 text-[11px] text-slate-600 space-y-0.5">
                  <div className="flex justify-between"><dt>Hotels</dt><dd className="font-bold">{p.metrics.avg_hotel_stars}★ average</dd></div>
                  <div className="flex justify-between"><dt>Travel time</dt><dd className="font-bold">{hoursMinutes(p.metrics.transit_minutes)}</dd></div>
                </dl>
              </div>
              <div className="mt-4">
                <div className="text-xl font-black text-[#003580] tabular-nums">{formatINR(p.pricing.total_inr)}</div>
                <div className="text-[11px] font-bold text-[#008009]">{formatINR(p.pricing.remaining_inr)} left in budget</div>
                <button onClick={() => navigate(`/packages/${p.package_id}`)}
                  className="mt-3 w-full px-3.5 py-2 text-xs font-bold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded flex items-center justify-center gap-1">
                  View and customise <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

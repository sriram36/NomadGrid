import React, { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ShieldAlert, Wallet, ArrowLeft, ArrowRight, TrendingUp } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { formatINR } from '../lib/format';

// A request that is valid but impossible, or that cannot fit the budget. Never shows a package that breaks a rule.
export default function OutcomePage() {
  const navigate = useNavigate();
  const { outcome, submitTrip } = useApp();
  const [busy, setBusy] = useState(false);

  if (!outcome) return <Navigate to="/" replace />;

  const editTrip = () => navigate('/', { state: { edit: true } });

  if (outcome.kind === 'NO_PACKAGE') {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-6">
        <button onClick={editTrip} className="flex items-center gap-2 text-xs font-bold text-[#006ce4] hover:underline">
          <ArrowLeft className="w-4 h-4" /> Back to Search
        </button>
        <div className="bg-red-50 border-2 border-[#d4111e] rounded-xl p-6 text-[#d4111e] shadow-sm" role="alert" data-testid="no-package">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-red-100 rounded-lg shrink-0"><ShieldAlert className="w-6 h-6" /></div>
            <div>
              <h3 className="text-sm font-black text-[#d4111e]">No Valid Package Possible for This Request</h3>
              <p className="text-sm text-slate-800 mt-1 leading-relaxed font-medium">{outcome.message}</p>
              <button onClick={editTrip}
                className="mt-4 px-4 py-2 text-xs font-bold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded transition-colors">
                Modify Search
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // OVER_BUDGET
  const raise = outcome.raise_budget;
  const raiseBudget = async () => {
    setBusy(true);
    try {
      const res = await submitTrip({ ...outcome.request, budget: raise.budget_inr });
      if (res.kind === 'PACKAGE') navigate(`/packages/${res.id}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-6">
      <button onClick={editTrip} className="flex items-center gap-2 text-xs font-bold text-[#006ce4] hover:underline">
        <ArrowLeft className="w-4 h-4" /> Edit the trip
      </button>

      <div className="bg-[#fff9e6] border-2 border-[#febb02] rounded-xl p-6 shadow-sm" role="alert" data-testid="over-budget">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-[#febb02] rounded-lg text-[#003580] shrink-0"><Wallet className="w-6 h-6" /></div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-2 py-0.5 rounded bg-[#003580] text-white text-[10px] font-black uppercase tracking-wider">
                Insufficient Budget Notice
              </span>
              <h3 className="text-sm font-black text-[#003580]">This trip doesn't fit your budget as planned</h3>
            </div>
            <p className="text-sm text-slate-800 mt-1 leading-relaxed">{outcome.message}</p>
            <p className="text-xs text-slate-600 mt-2">
              Cheapest possible: <strong className="text-[#003580]">{formatINR(outcome.cheapest_total_inr)}</strong> · over by{' '}
              <strong className="text-[#d4111e]">{formatINR(outcome.over_by_inr)}</strong>
            </p>
          </div>
        </div>
      </div>

      {outcome.alternatives?.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-extrabold text-[#003580]">What does fit your budget</h4>
          <p className="text-xs text-slate-600">Each of these is a complete holiday that follows every rule and stays within {formatINR(outcome.request.budget_inr)}.</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {outcome.alternatives.map((alt) => (
              <div key={alt.id} className="bg-white rounded-xl border border-slate-300 p-5 flex flex-col justify-between hover:border-[#003580] transition-colors" data-testid="alternative">
                <div>
                  <div className="text-sm font-extrabold text-[#003580]">{alt.label}</div>
                  <ul className="mt-2 text-xs text-slate-600 space-y-0.5 list-disc pl-4">
                    {alt.changes.map((c, i) => <li key={i}>{c.field.replaceAll('_', ' ')}: {String(c.from)} → {String(c.to)}</li>)}
                  </ul>
                </div>
                <div className="mt-4 flex items-end justify-between">
                  <div>
                    <div className="text-lg font-black text-[#003580] tabular-nums">{formatINR(alt.total_inr)}</div>
                    <div className="text-[11px] font-bold text-[#008009]">{formatINR(alt.remaining_inr)} left</div>
                  </div>
                  <button onClick={() => navigate(`/packages/${alt.package_id}`)}
                    className="px-3.5 py-2 text-xs font-bold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded flex items-center gap-1">
                    Open this holiday <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {outcome.alternatives?.length === 0 && (
        <p className="text-xs text-slate-600 bg-white border border-slate-300 rounded-xl p-4">
          Even with fewer cities, fewer nights or other dates, nothing fits {formatINR(outcome.request.budget_inr)} for these travellers.
        </p>
      )}

      <div className="bg-white rounded-xl border-2 border-[#006ce4] p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <TrendingUp className="w-5 h-5 text-[#006ce4] shrink-0 mt-0.5" />
          <div>
            <div className="text-sm font-extrabold text-[#003580]">Or keep your trip and raise the budget</div>
            <div className="text-xs text-slate-600">{raise.label}</div>
          </div>
        </div>
        <button onClick={raiseBudget} disabled={busy}
          className="px-4 py-2.5 text-xs font-black text-white bg-[#006ce4] hover:bg-[#0057b8] rounded disabled:opacity-60 whitespace-nowrap">
          {busy ? 'Building…' : `Increase budget to ${formatINR(raise.budget_inr)}`}
        </button>
      </div>
    </div>
  );
}

import React, { useMemo, useState } from 'react';
import { Lightbulb, ChevronDown, ChevronUp, Check } from 'lucide-react';
import { buildPlanInsights } from '../lib/planInsights';

// "Why this plan": the backend's own reasons, plus a rule and trade-off check worked out from this package.
export default function WhyThisPlan({ tripPackage, interests }) {
  const [open, setOpen] = useState(true);
  const reasons = tripPackage.rationale?.reasons || [];
  const insights = useMemo(() => buildPlanInsights(tripPackage, interests), [tripPackage, interests]);
  if (!reasons.length && !insights.length) return null;

  return (
    <div className="bg-white border border-slate-300 rounded-xl shadow-sm" data-testid="why-panel">
      <button onClick={() => setOpen((v) => !v)} aria-expanded={open} className="w-full flex items-center justify-between px-4 py-3 text-left">
        <span className="flex items-center gap-2 text-sm font-extrabold text-[#003580]">
          <Lightbulb className="size-4 text-[#febb02]" /> Why this plan
        </span>
        {open ? <ChevronUp className="size-4 text-slate-500" /> : <ChevronDown className="size-4 text-slate-500" />}
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4">
          {reasons.length > 0 && (
            <ul className="space-y-1.5 text-xs text-slate-700 list-disc pl-5">
              {reasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          )}

          {insights.length > 0 && (
            <div className="rounded-lg bg-[#f2f6fa] border border-slate-200 p-3.5 space-y-3" data-testid="plan-insights">
              <p className="text-[11px] font-black uppercase tracking-wider text-[#003580]">Rule and trade-off check</p>
              {insights.map((section) => (
                <div key={section.title}>
                  <p className="text-[11px] font-bold text-slate-800 mb-1">{section.title}</p>
                  <ul className="space-y-1">
                    {section.lines.map((line, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-xs text-slate-700">
                        <Check className="size-3.5 mt-0.5 shrink-0 text-[#008009]" strokeWidth={3} />
                        <span>{line}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

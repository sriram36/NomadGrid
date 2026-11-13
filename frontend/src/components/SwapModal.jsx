import React, { useEffect, useState } from 'react';
import { X, RefreshCw, AlertCircle, ShieldAlert, Star, Wallet, Undo2 } from 'lucide-react';
import { api, NetworkError } from '../api/client';
import { formatINR, signedINR, hoursMinutes } from '../lib/format';

const TITLES = {
  flight: 'Change Flight (Rule Re-Validation)',
  hotel: 'Change Room / Hotel (Booking.com Rules)',
  add_attraction: 'Add Sightseeing (Schedule Check)',
  city_plan: 'Change City Plan (Rule Re-Validation)',
};

// Choices the traveler can actually take come first; the unavailable ones (with their reason) go last.
const ordered = (list) => [...(list || [])].sort((a, b) => (Number(b.current) - Number(a.current)) || (Number(b.available) - Number(a.available)));

function DeltaBadge({ delta, current }) {
  if (current) return <span className="text-[10px] font-extrabold text-[#003580] bg-[#febb02]/40 px-1.5 py-0.5 rounded">Current</span>;
  if (delta === null || delta === undefined) return null;
  const cls = delta > 0 ? 'text-[#d4111e]' : delta < 0 ? 'text-[#008009]' : 'text-slate-400';
  return <div className={`text-[10px] font-bold tabular-nums ${cls}`}>{signedINR(delta)}</div>;
}

function Unavailable({ option }) {
  if (option.available) {
    if (!option.fits_budget) {
      return (
        <div className="mt-2 text-[11px] text-[#b45309] font-bold flex items-center gap-1">
          <Wallet className="w-3 h-3 shrink-0" />
          <span>Needs +{formatINR(option.budget_needed_inr)} more budget</span>
        </div>
      );
    }
    return null;
  }
  return (
    <div className="mt-2 text-[11px] text-[#d4111e] font-bold flex items-start gap-1">
      <AlertCircle className="w-3 h-3 shrink-0 mt-0.5" />
      <span>{option.reason_unavailable || 'Not available.'}</span>
    </div>
  );
}

export default function SwapModal({ isOpen, onClose, modalType, targetItem, targetDate, tripPackage, onApply }) {
  const [loaded, setLoaded] = useState(null);       // { key, list }: options are only shown for the dialog they were loaded for
  const [loadError, setLoadError] = useState(null);
  const [pending, setPending] = useState(null);       // { op, result } when a change needs the traveler's decision
  const [busy, setBusy] = useState(false);
  const [startChoice, setStartChoice] = useState({});

  const packageId = tripPackage?.package_id;
  const viewKey = [modalType, packageId, targetItem?.item_id ?? '', targetItem?.city ?? '', targetDate ?? ''].join('|');
  const options = loaded && loaded.key === viewKey ? loaded.list : null;

  useEffect(() => {
    if (!isOpen || !packageId) return undefined;
    let cancelled = false;
    setLoaded(null);
    setLoadError(null);
    setPending(null);
    setStartChoice({});
    const load = async () => {
      try {
        let res;
        if (modalType === 'flight') res = await api.flightOptions(packageId, targetItem?.details?.isArrival ? 'ARRIVAL' : 'RETURN');
        else if (modalType === 'hotel') res = await api.hotelOptions(packageId, targetItem.city);
        else if (modalType === 'add_attraction') res = await api.attractionOptions(packageId, targetDate);
        else if (modalType === 'city_plan') res = await api.cityPlanOptions(packageId);
        if (cancelled || !res) return;
        if (res.status !== 200) setLoadError(res.data?.error?.message || 'We could not load the options.');
        else setLoaded({ key: viewKey, list: res.data.options || [] });
      } catch (e) {
        if (!cancelled) setLoadError(e instanceof NetworkError ? e.message : 'We could not load the options.');
      }
    };
    load();
    return () => { cancelled = true; };
  }, [isOpen, packageId, modalType, targetItem, targetDate, viewKey]);

  if (!isOpen || !tripPackage) return null;

  const choose = async (op) => {
    setBusy(true);
    try {
      const result = await onApply(op);
      if (!result) return;
      if (result.result === 'APPLIED') onClose();
      else setPending({ op, result });
    } finally {
      setBusy(false);
    }
  };

  const optionFlights = () => ordered(options).map((o) => (
    <li key={o.flight_id} className={`p-3.5 rounded-lg border text-xs ${o.available ? 'border-slate-300 bg-white hover:border-[#006ce4]' : 'border-slate-200 bg-slate-50 opacity-80'}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-extrabold text-[#003580]">{o.airline} {o.flight_number}</span>
            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-[10px] font-bold">{o.from} → {o.to}</span>
            <span className="text-[11px] text-slate-500">{o.stops === 0 ? 'Direct' : '1 stop'} · {hoursMinutes(o.duration_minutes)}</span>
          </div>
          <div className="mt-1.5 text-slate-600 text-[11px]">
            <span className="font-mono tabular-nums font-bold text-slate-800">{o.departure.replace('T', ' ')} → {o.arrival.replace('T', ' ')}</span>
            <span className="ml-3">Seats left: <strong>{o.seats_left}</strong></span>
          </div>
          <Unavailable option={o} />
        </div>
        <div className="text-right shrink-0">
          <div className="font-black text-[#003580] tabular-nums">{formatINR(o.price_inr)}</div>
          <DeltaBadge delta={o.price_delta_inr} current={o.current} />
          {!o.current && (
            <button type="button" disabled={!o.available || busy}
              onClick={() => choose({ op: 'CHANGE_FLIGHT', leg: targetItem.details.isArrival ? 'ARRIVAL' : 'RETURN', flight_id: o.flight_id })}
              className={`mt-2 px-3 py-1 text-xs font-bold rounded ${o.available ? 'bg-[#006ce4] hover:bg-[#0057b8] text-white' : 'bg-slate-200 text-slate-400 cursor-not-allowed'}`}>
              Select
            </button>
          )}
        </div>
      </div>
    </li>
  ));

  const optionHotels = () => ordered(options).map((o) => (
    <li key={`${o.hotel_id}-${o.room_id}`} className={`p-3.5 rounded-lg border text-xs ${o.available ? 'border-slate-300 bg-white hover:border-[#006ce4]' : 'border-slate-200 bg-slate-50 opacity-80'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex gap-3">
          {o.image && <img src={o.image} alt="" loading="lazy" className="w-20 h-16 rounded object-cover shrink-0" onError={(e) => { e.currentTarget.style.display = 'none'; }} />}
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-extrabold text-[#003580]">{o.name}</span>
              <span className="flex items-center gap-0.5 text-[#b45309] font-bold text-[11px]"><Star className="w-3 h-3 fill-current" />{o.stars}</span>
              <span className="px-1.5 py-0.5 rounded bg-[#003580] text-white text-[10px] font-extrabold">{o.rating}</span>
              <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px] font-semibold">{o.area}</span>
            </div>
            <div className="mt-1 text-slate-700 text-[11px]">
              {o.room_name} × <strong>{o.rooms_needed}</strong>{o.family_friendly ? ' · family friendly' : ''}
            </div>
            <Unavailable option={o} />
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="font-black text-[#003580] tabular-nums">{formatINR(o.price_inr)}</div>
          <DeltaBadge delta={o.price_delta_inr} current={o.current} />
          {!o.current && (
            <button type="button" disabled={!o.available || busy}
              onClick={() => choose({ op: 'CHANGE_HOTEL', city: targetItem.city, hotel_id: o.hotel_id, room_id: o.room_id })}
              className={`mt-2 px-3 py-1 text-xs font-bold rounded ${o.available ? 'bg-[#006ce4] hover:bg-[#0057b8] text-white' : 'bg-slate-200 text-slate-400 cursor-not-allowed'}`}>
              Select
            </button>
          )}
        </div>
      </div>
    </li>
  ));

  const optionAttractions = () => (options || []).map((o) => {
    const start = startChoice[o.attraction_id] || o.start_choices[0];
    return (
      <li key={o.attraction_id} className="p-3.5 rounded-lg border text-xs border-slate-300 bg-white hover:border-[#008009]">
        <div className="flex items-start justify-between gap-3">
          <div className="flex gap-3">
            {o.image && <img src={o.image} alt="" loading="lazy" className="w-20 h-16 rounded object-cover shrink-0" onError={(e) => { e.currentTarget.style.display = 'none'; }} />}
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-extrabold text-[#003580]">{o.name}</span>
                <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-[#008009] border border-emerald-200 text-[10px] font-bold">{o.category.replaceAll('_', ' ')}</span>
                {o.child_friendly && <span className="text-[10px] font-bold text-slate-500">child friendly</span>}
                {o.matches_interests && <span className="px-1.5 py-0.5 rounded bg-[#febb02]/30 text-[#003580] text-[10px] font-extrabold">Matches your interests</span>}
              </div>
              <div className="mt-1 text-slate-500 text-[11px]">Visit: {o.duration_minutes} min</div>
              <label className="mt-1.5 flex items-center gap-2 text-[11px] text-slate-700 font-semibold">
                Start at
                <select value={start} onChange={(e) => setStartChoice((p) => ({ ...p, [o.attraction_id]: e.target.value }))}
                  aria-label={`Start time for ${o.name}`}
                  className="px-1.5 py-0.5 border border-slate-300 rounded font-mono text-[11px] bg-white">
                  {o.start_choices.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>
              <Unavailable option={o} />
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className="font-black text-[#003580] tabular-nums">{o.price_inr === 0 ? 'Free' : formatINR(o.price_inr)}</div>
            <button type="button" disabled={busy}
              onClick={() => choose({ op: 'ADD_ATTRACTION', attraction_id: o.attraction_id, date: targetDate, start })}
              className="mt-2 px-3 py-1 text-xs font-bold rounded bg-[#008009] hover:bg-emerald-700 text-white">
              Add
            </button>
          </div>
        </div>
      </li>
    );
  });

  const optionCityPlans = () => (options || []).map((o, idx) => (
    <li key={idx} className={`p-3.5 rounded-lg border text-xs ${o.current ? 'border-[#febb02] bg-[#fff9e6]' : 'border-slate-300 bg-white hover:border-[#006ce4]'}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 flex-wrap font-extrabold text-[#003580]">
            {o.plan.map((p) => `${p.city} · ${p.nights} nights`).join('  →  ')}
            {o.preferred && <span className="px-1.5 py-0.5 rounded bg-[#008009]/10 text-[#008009] text-[10px] font-bold">Suits {tripPackage.nights} nights</span>}
          </div>
          <div className="mt-1 text-slate-600 text-[11px]">
            Travel time {hoursMinutes(o.transit_minutes)} · hotels average {o.avg_hotel_stars}★
          </div>
          {o.warnings.filter((w) => !w.startsWith('OVER_BUDGET')).map((w, i) => (
            <div key={i} className="mt-1 text-[11px] text-[#b45309] font-semibold">{w.replace(/^[A-Z_]+: /, '')}</div>
          ))}
          {!o.fits_budget && (
            <div className="mt-1 text-[11px] text-[#b45309] font-bold flex items-center gap-1">
              <Wallet className="w-3 h-3" /> Needs +{formatINR(o.budget_needed_inr)} more budget
            </div>
          )}
        </div>
        <div className="text-right shrink-0">
          <div className="font-black text-[#003580] tabular-nums">{formatINR(o.total_inr)}</div>
          <DeltaBadge delta={o.price_delta_inr} current={o.current} />
          {!o.current && (
            <button type="button" disabled={busy}
              onClick={() => choose({ op: 'CHANGE_CITY_PLAN', plan: o.plan })}
              className="mt-2 px-3 py-1 text-xs font-bold rounded bg-[#006ce4] hover:bg-[#0057b8] text-white">
              Use this plan
            </button>
          )}
        </div>
      </div>
    </li>
  ));

  const renderBanner = () => {
    if (!pending) return null;
    const { op, result } = pending;
    if (result.result === 'BUDGET_EXCEEDED') {
      return (
        <div className="mb-4 p-3 rounded bg-[#fff9e6] border-2 border-[#febb02] text-xs text-slate-800" role="alert">
          <p className="font-black text-[#003580] flex items-center gap-1.5"><Wallet className="w-4 h-4" /> This would go over your budget</p>
          <p className="mt-1">{result.message}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" disabled={busy} onClick={() => choose({ ...op, raise_budget: true })}
              className="px-3 py-1.5 font-bold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded">
              Raise my budget to {formatINR(result.new_total_inr)} and apply
            </button>
            <button type="button" onClick={() => setPending(null)} className="px-3 py-1.5 font-bold text-slate-700 bg-white border border-slate-300 rounded">
              Keep my budget
            </button>
          </div>
        </div>
      );
    }
    if (result.result === 'PINNED_CONFLICT') {
      return (
        <div className="mb-4 p-3 rounded bg-[#fff9e6] border-2 border-[#febb02] text-xs text-slate-800" role="alert">
          <p className="font-black text-[#003580] flex items-center gap-1.5"><Star className="w-4 h-4" /> This would undo a choice you made</p>
          <p className="mt-1">{result.reason}</p>
          {result.suggestion && <p className="mt-0.5 text-slate-600">{result.suggestion}</p>}
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" onClick={() => setPending(null)} className="px-3 py-1.5 font-bold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded flex items-center gap-1">
              <Undo2 className="w-3.5 h-3.5" /> Keep my current plan
            </button>
            <button type="button" disabled={busy} onClick={() => choose({ ...op, remove_pinned_conflicts: true })}
              className="px-3 py-1.5 font-bold text-slate-800 bg-white border border-slate-300 rounded">
              Apply anyway and let those go
            </button>
          </div>
        </div>
      );
    }
    return (
      <div className="mb-4 p-3 rounded bg-red-50 border border-[#d4111e] text-[#d4111e] text-xs font-semibold flex items-start gap-2" role="alert">
        <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
        <div>
          <p className="font-bold">Edit Refused (Booking Rule Conflict):</p>
          <p>{result.reason || result.message}</p>
          {result.suggestion && <p className="text-slate-700 font-medium mt-0.5">{result.suggestion}</p>}
        </div>
      </div>
    );
  };

  const renderCurrent = () => {
    if (modalType === 'flight') {
      return (
        <div className="bg-[#f2f6fa] p-3.5 rounded-lg border border-slate-300 text-xs mb-4">
          <span className="font-bold text-slate-500 uppercase text-[10px] tracking-wider block mb-1">Current Flight Selection</span>
          <div className="flex items-center justify-between font-extrabold text-[#003580]">
            <span>{targetItem.name}</span><span className="text-slate-900 tabular-nums">{formatINR(targetItem.price_inr)}</span>
          </div>
        </div>
      );
    }
    if (modalType === 'hotel') {
      return (
        <div className="bg-[#f2f6fa] p-3.5 rounded-lg border border-slate-300 text-xs mb-4">
          <span className="font-bold text-slate-500 uppercase text-[10px] tracking-wider block mb-1">Current Hotel in {targetItem.city}</span>
          <div className="flex items-center justify-between font-extrabold text-[#003580]">
            <span>{targetItem.name}</span><span className="text-slate-900 tabular-nums">{formatINR(targetItem.price_inr)}</span>
          </div>
        </div>
      );
    }
    if (modalType === 'add_attraction') {
      return (
        <div className="bg-[#f2f6fa] p-3 rounded-lg border border-slate-300 text-xs mb-4">
          <span className="text-slate-700 font-bold">Adding Sightseeing for Date: <strong className="text-[#003580]">{targetDate}</strong></span>
          <p className="text-[11px] text-slate-500 mt-0.5">Verified for opening days, operating hours, and zero overlap with existing activities.</p>
        </div>
      );
    }
    return (
      <div className="bg-[#f2f6fa] p-3 rounded-lg border border-slate-300 text-xs mb-4">
        <span className="text-slate-700 font-bold">Every valid way to split your {tripPackage.nights} nights between cities</span>
        <p className="text-[11px] text-slate-500 mt-0.5">Prices are what the whole holiday would cost. Things you chose yourself are kept where they still fit.</p>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 bg-[#003580]/50 backdrop-blur-xs flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={TITLES[modalType]}>
      <div className="bg-white rounded-xl shadow-2xl border border-slate-300 max-w-xl w-full p-6">
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded bg-[#006ce4]/10 text-[#006ce4]"><RefreshCw className="w-4 h-4" /></span>
            <h3 className="text-base font-extrabold text-[#003580]">{TITLES[modalType]}</h3>
          </div>
          <button onClick={onClose} aria-label="Close" className="p-1 text-slate-400 hover:text-slate-700 rounded transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {renderBanner()}
        {renderCurrent()}

        {loadError && <p className="text-xs text-[#d4111e] font-bold py-4 text-center">{loadError}</p>}
        {!loadError && options === null && (
          <div className="py-8 flex justify-center"><div className="w-8 h-8 border-4 border-[#003580] border-t-[#febb02] rounded-full animate-spin" /></div>
        )}
        {options !== null && options.length === 0 && (
          <p className="text-xs text-slate-500 italic py-4 text-center">Nothing else is available here.</p>
        )}
        {options !== null && options.length > 0 && (
          <ul className="space-y-2.5 max-h-[50vh] overflow-y-auto pr-1" data-testid="options-list">
            {modalType === 'flight' && optionFlights()}
            {modalType === 'hotel' && optionHotels()}
            {modalType === 'add_attraction' && optionAttractions()}
            {modalType === 'city_plan' && optionCityPlans()}
          </ul>
        )}

        <div className="mt-6 pt-4 border-t border-slate-200 flex justify-end">
          <button type="button" onClick={onClose}
            className="px-4 py-2 text-xs font-bold text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded transition-colors flex items-center gap-1">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

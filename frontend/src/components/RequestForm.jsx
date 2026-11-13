import React, { useEffect, useState } from 'react';
import {
  Sparkles, Calendar, MapPin, Users, DollarSign, AlertCircle, Compass, Plane, ShieldCheck, Tag, Check, Search,
  Wand2, Layers,
} from 'lucide-react';
import { api, NetworkError } from '../api/client';
import { sampleTrips } from '../lib/samples';
import { formatINR } from '../lib/format';
import { useApp } from '../context/AppContext';

const EMPTY = {
  departureCity: '', destinationCountry: '', startDate: '', nights: '', adults: '',
  childrenCount: 0, childrenAges: [], budget: '',
};

// The backend's field names -> this form's keys (so the backend's own message shows next to the right input).
const FIELD_KEY = {
  departure_city: 'departureCity', country: 'destinationCountry', start_date: 'startDate', nights: 'nights',
  adults: 'adults', child_ages: 'childrenAges', budget_inr: 'budget',
};

function fromRequest(r) {
  const ages = r.child_ages || [];
  return {
    departureCity: r.departure_city || '', destinationCountry: r.country || '', startDate: r.start_date || '',
    nights: r.nights ?? '', adults: r.adults ?? '', childrenCount: ages.length, childrenAges: [...ages],
    budget: r.budget_inr ?? '',
  };
}

function Field({ label, icon: Icon, error, hint, children, className = '' }) {
  return (
    <div className={className}>
      <label className="block text-xs font-bold text-slate-700 mb-1 flex items-center gap-1">
        <Icon className="w-3.5 h-3.5 text-[#006ce4]" />
        {label}
      </label>
      {children}
      {error ? (
        <p className="mt-1 text-[11px] text-[#d4111e] font-bold flex items-center gap-1" role="alert">
          <AlertCircle className="w-3 h-3 shrink-0" />
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1 text-[10px] text-slate-500 font-medium">{hint}</p>
      ) : null}
    </div>
  );
}

const inputClass = (error) =>
  `w-full px-3 py-2 text-xs font-semibold text-slate-800 rounded border-2 focus:outline-hidden transition-all bg-white ${
    error ? 'border-[#d4111e] bg-red-50/20' : 'border-slate-300 focus:border-[#006ce4]'
  }`;

export default function RequestForm({ onSubmit, initialData = null, isLoading = false }) {
  const { meta } = useApp();
  const [formData, setFormData] = useState(initialData ? fromRequest(initialData) : EMPTY);
  const [errors, setErrors] = useState({});
  const [quickText, setQuickText] = useState('');
  const [quick, setQuick] = useState(null);       // result of reading the sentence
  const [quickBusy, setQuickBusy] = useState(false);

  useEffect(() => { if (initialData) setFormData(fromRequest(initialData)); }, [initialData]);

  const set = (key, value) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: null }));
  };

  const handleChildrenCountChange = (count) => {
    const num = Math.max(0, parseInt(count, 10) || 0);
    const ages = [...formData.childrenAges];
    while (ages.length < num) ages.push(6);
    ages.length = num;
    setFormData((prev) => ({ ...prev, childrenCount: num, childrenAges: ages }));
    if (errors.childrenAges) setErrors((prev) => ({ ...prev, childrenAges: null }));
  };

  const handleChildAgeChange = (index, age) => {
    const ages = [...formData.childrenAges];
    ages[index] = age === '' ? '' : parseInt(age, 10);
    setFormData((prev) => ({ ...prev, childrenAges: ages }));
    if (errors.childrenAges) setErrors((prev) => ({ ...prev, childrenAges: null }));
  };

  const fillSample = (s) => {
    setFormData({
      departureCity: s.departureCity, destinationCountry: s.destinationCountry, startDate: s.startDate,
      nights: s.nights, adults: s.adults, childrenCount: s.children.length, childrenAges: [...s.children],
      budget: s.budget,
    });
    setErrors({});
  };

  // S1: read a sentence with the backend's fixed rules and fill the form from it.
  const readSentence = async () => {
    if (!quickText.trim()) return;
    setQuickBusy(true);
    try {
      const { status, data } = await api.parseRequest(quickText);
      if (status !== 200) {
        setQuick({ error: data?.error?.fields?.[0]?.message || data?.error?.message || 'Please type a short request.' });
        return;
      }
      setQuick(data);
      const f = data.fields || {};
      setFormData((prev) => ({
        departureCity: f.departure_city ?? prev.departureCity,
        destinationCountry: f.country ?? prev.destinationCountry,
        startDate: f.start_date ?? prev.startDate,
        nights: f.nights ?? prev.nights,
        adults: f.adults ?? prev.adults,
        childrenCount: f.child_ages ? f.child_ages.length : prev.childrenCount,
        childrenAges: f.child_ages ?? prev.childrenAges,
        budget: f.budget_inr ?? prev.budget,
      }));
      setErrors({});
    } catch (e) {
      setQuick({ error: e instanceof NetworkError ? e.message : 'Could not read that request.' });
    } finally {
      setQuickBusy(false);
    }
  };

  const submit = async (mode) => {
    // Only "is it filled in?" is checked here; every real rule is answered by the backend, in its own words.
    const missing = {};
    if (!formData.departureCity) missing.departureCity = 'Please choose where you are flying from.';
    if (!formData.destinationCountry) missing.destinationCountry = 'Please choose a destination country.';
    if (!formData.startDate) missing.startDate = 'Please pick the first day of your holiday.';
    if (formData.nights === '' || formData.nights === null) missing.nights = 'Please enter the number of nights.';
    if (formData.adults === '' || formData.adults === null) missing.adults = 'Please enter the number of adults.';
    if (formData.budget === '' || formData.budget === null) missing.budget = 'Please enter your total budget in rupees.';
    if (Object.keys(missing).length) { setErrors(missing); return; }

    const request = {
      departure_city: formData.departureCity,
      country: formData.destinationCountry,
      start_date: formData.startDate,
      nights: Number(formData.nights),
      adults: Number(formData.adults),
      child_ages: formData.childrenAges.map((a) => (a === '' ? null : Number(a))),
      budget_inr: Number(formData.budget),
    };
    const result = await onSubmit(request, mode);
    if (result?.kind === 'INVALID') {
      const mapped = {};
      for (const [field, message] of Object.entries(result.fields || {})) mapped[FIELD_KEY[field] || field] = message;
      setErrors(mapped);
    }
  };

  const rules = meta?.rules;
  const departureCities = meta?.departure_cities || [];
  const countries = meta?.countries || [];

  return (
    <div className="space-y-4">

      {/* Hero banner */}
      <div className="bg-[#003580] text-white rounded-2xl p-6 sm:p-8 shadow-md">
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">Find your next holiday package</h1>
        <p className="text-sm text-white/90 mt-1 max-w-2xl">
          Tell us the trip and your budget — we choose the cities and build flights, hotels, transfers and attractions
          that fit, then you can change anything.
        </p>
        <div className="flex items-center gap-2 mt-4 flex-wrap">
          <span className="text-xs font-bold text-[#febb02] flex items-center gap-1 mr-1">
            <Tag className="w-3.5 h-3.5" />
            Try an example:
          </span>
          <button type="button" onClick={() => fillSample(sampleTrips.standardSample)}
            className="px-3 py-1 text-xs font-bold bg-[#febb02] text-[#003580] hover:bg-[#e5a700] rounded transition-colors flex items-center gap-1 shadow-sm">
            <Sparkles className="w-3.5 h-3.5 text-[#003580]" />
            Menon family (Japan, 6 nights)
          </button>
          <button type="button" onClick={() => fillSample(sampleTrips.overBudgetSample)}
            className="px-3 py-1 text-xs font-bold bg-white/20 hover:bg-white/30 text-white rounded border border-white/40 transition-colors">
            Budget too small
          </button>
          <button type="button" onClick={() => fillSample(sampleTrips.impossibleTripSample)}
            className="px-3 py-1 text-xs font-bold bg-white/20 hover:bg-white/30 text-white rounded border border-white/40 transition-colors">
            Dates we can't do
          </button>
        </div>
      </div>

      {/* S1: type it in plain words */}
      <div className="bg-white rounded-2xl border border-slate-300 shadow-sm p-5">
        <div className="flex items-center gap-2 mb-2">
          <Wand2 className="w-4 h-4 text-[#006ce4]" />
          <h2 className="text-sm font-extrabold text-[#003580]">Or just type your trip</h2>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={quickText}
            onChange={(e) => setQuickText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); readSentence(); } }}
            placeholder="e.g. Japan 10 Apr 6 nights 2 adults 1 child 6 from Bengaluru 3.5 lakh"
            aria-label="Describe your trip in plain words"
            className="flex-1 px-3 py-2 text-xs font-semibold rounded border-2 border-slate-300 focus:border-[#006ce4] focus:outline-hidden"
          />
          <button type="button" onClick={readSentence} disabled={quickBusy || !quickText.trim()}
            className="px-4 py-2 text-xs font-bold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded disabled:opacity-50">
            {quickBusy ? 'Reading…' : 'Fill the form'}
          </button>
        </div>
        {quick && (
          <div className="mt-2 space-y-1 text-[11px]" data-testid="quick-feedback">
            {quick.error && <p className="text-[#d4111e] font-bold">{quick.error}</p>}
            {!quick.error && quick.missing?.length === 0 && quick.ready && (
              <p className="text-[#008009] font-bold flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Understood everything — check the form below, then search.</p>
            )}
            {!quick.error && quick.missing?.length > 0 && (
              <p className="text-[#b45309] font-bold">Still needed: {quick.missing.join(', ').replaceAll('_', ' ')}.</p>
            )}
            {(quick.notes || []).map((n, i) => <p key={i} className="text-slate-600">• {n}</p>)}
          </div>
        )}
      </div>

      {/* The 7-field form */}
      <div className="bg-white rounded-2xl border-4 border-[#febb02] shadow-xl p-5 sm:p-7">
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-100">
          <h2 className="text-base font-extrabold text-[#003580] flex items-center gap-2">
            <Compass className="w-5 h-5 text-[#006ce4]" />
            Your trip
          </h2>
          <span className="text-xs font-bold text-[#008009] flex items-center gap-1 bg-[#008009]/10 px-2 py-0.5 rounded">
            <Check className="w-3.5 h-3.5" />
            Every rule checked for you
          </span>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); submit('single'); }} noValidate>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

            <Field label="Flying from" icon={MapPin} error={errors.departureCity}>
              <select value={formData.departureCity} onChange={(e) => set('departureCity', e.target.value)}
                aria-label="Flying from" className={inputClass(errors.departureCity)}>
                <option value="">Where are you flying from?</option>
                {departureCities.map((c) => (
                  <option key={c.city} value={c.city}>{c.city} ({c.airport})</option>
                ))}
              </select>
            </Field>

            <Field label="Going to" icon={Plane} error={errors.destinationCountry}>
              <select value={formData.destinationCountry} onChange={(e) => set('destinationCountry', e.target.value)}
                aria-label="Going to" className={inputClass(errors.destinationCountry)}>
                <option value="">Where are you going?</option>
                {countries.map((c) => (
                  <option key={c.name} value={c.name}>{c.name} ({c.cities.join(', ')})</option>
                ))}
              </select>
            </Field>

            <Field label="First day there (landing day)" icon={Calendar} error={errors.startDate}
              hint={rules ? `Our flights and rooms cover ${rules.first_night} to ${rules.last_departure}.` : undefined}>
              <input type="date" value={formData.startDate} onChange={(e) => set('startDate', e.target.value)}
                aria-label="First day there" className={inputClass(errors.startDate)} />
            </Field>

            <Field label={`Nights${rules ? ` (${rules.min_nights} to ${rules.max_nights})` : ''}`} icon={Calendar} error={errors.nights}>
              <input type="number" placeholder="e.g. 6" value={formData.nights} onChange={(e) => set('nights', e.target.value)}
                aria-label="Nights" className={inputClass(errors.nights)} />
            </Field>

            <Field label="Adults (18+)" icon={Users} error={errors.adults}>
              <input type="number" min="1" placeholder="e.g. 2" value={formData.adults} onChange={(e) => set('adults', e.target.value)}
                aria-label="Adults" className={inputClass(errors.adults)} />
            </Field>

            <Field label="Children (0–17)" icon={Users} error={errors.childrenAges}
              hint={formData.childrenCount > 0 ? `Enter each child's age below` : 'No children'}>
              <input type="number" min="0" placeholder="0" value={formData.childrenCount}
                onChange={(e) => handleChildrenCountChange(e.target.value)} aria-label="Children"
                className={inputClass(errors.childrenAges)} />
            </Field>

            <div className="sm:col-span-2 lg:col-span-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field label="Total budget for everything (₹)" icon={DollarSign} error={errors.budget}
                  hint={formData.budget ? `Your budget: ${formatINR(formData.budget)}` : undefined}>
                  <div className="relative">
                    <span className="absolute left-3 top-2 text-xs font-extrabold text-slate-500">₹</span>
                    <input type="number" step="1000" placeholder="e.g. 350000" value={formData.budget}
                      onChange={(e) => set('budget', e.target.value)} aria-label="Total budget"
                      className={`${inputClass(errors.budget)} pl-7 tabular-nums`} />
                  </div>
                </Field>

                {formData.childrenCount > 0 && (
                  <div className="bg-[#f2f6fa] p-3 rounded-lg border border-slate-300">
                    <label className="block text-[11px] font-bold uppercase tracking-wider text-[#003580] mb-2">
                      Children's ages
                    </label>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {formData.childrenAges.map((age, idx) => (
                        <div key={idx}>
                          <label className="block text-[10px] font-bold text-slate-600 mb-0.5">Child {idx + 1}</label>
                          <input type="number" value={age} onChange={(e) => handleChildAgeChange(idx, e.target.value)}
                            aria-label={`Child ${idx + 1} age`}
                            className="w-full px-2 py-1 text-xs font-bold bg-white rounded border border-slate-300 focus:border-[#006ce4] focus:outline-hidden tabular-nums" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="mt-6 pt-5 border-t border-slate-200 flex flex-col lg:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
              <ShieldCheck className="w-4 h-4 text-[#008009]" />
              <span>Your budget comes first — we only show packages that fit it.</span>
            </div>
            <div className="flex flex-col sm:flex-row gap-2 w-full lg:w-auto">
              <button type="button" disabled={isLoading} onClick={() => submit('compare')}
                className="px-6 py-3 text-sm font-extrabold text-[#006ce4] bg-white border-2 border-[#006ce4] hover:bg-[#006ce4]/10 rounded-md transition-all flex items-center justify-center gap-2 disabled:opacity-50">
                <Layers className="w-4 h-4" />
                Compare cheapest · fastest · best rated
              </button>
              <button type="submit" disabled={isLoading}
                className="px-10 py-3 text-sm font-extrabold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded-md shadow-md transition-all flex items-center justify-center gap-2 disabled:opacity-50">
                {isLoading ? (
                  <span className="flex items-center gap-2"><Compass className="w-4 h-4 animate-spin" /> Building your holiday…</span>
                ) : (
                  <span className="flex items-center gap-2"><Search className="w-4 h-4" /> Build my holiday</span>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

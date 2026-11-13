import React, { useState } from 'react';
import { Sparkles, Calendar, MapPin, Users, DollarSign, AlertCircle, Compass, Plane, ShieldCheck, Tag, Check, Search, Wand2, Layers } from 'lucide-react';
import { sampleTrips } from '../lib/samples';
import { formatINR } from '../lib/format';
import { api, NetworkError } from '../api/client';
import { useApp } from '../context/AppContext';

// Used only if the backend cannot be reached to tell us the real choices (these are the catalog's own).
const FALLBACK_CITIES = [{ city: 'Bengaluru', airport: 'BLR' }, { city: 'Mumbai', airport: 'BOM' }, { city: 'Delhi', airport: 'DEL' }, { city: 'Chennai', airport: 'MAA' }];
const FALLBACK_COUNTRIES = [{ name: 'Japan', cities: ['Tokyo', 'Kyoto', 'Osaka'] }, { name: 'United Arab Emirates', cities: ['Dubai', 'Abu Dhabi'] }];

// The backend's field names -> this form's keys, so its own message shows next to the right input.
const FIELD_KEY = { departure_city: 'departureCity', country: 'destinationCountry', start_date: 'startDate', nights: 'nights', adults: 'adults', child_ages: 'child_0', budget_inr: 'budget' };

const fromRequest = (r) => ({
  departureCity: r.departureCity || '', destinationCountry: r.destinationCountry || '', startDate: r.startDate || '',
  nights: r.nights ?? '', adults: r.adults ?? '', childrenCount: (r.children || []).length, childrenAges: [...(r.children || [])],
  budget: r.budget ?? ''
});

export default function RequestForm({
  onSubmit,
  initialData = null,
  isLoading = false
}) {
  const { meta } = useApp();
  const departureCities = meta?.departure_cities || FALLBACK_CITIES;
  const countries = meta?.countries || FALLBACK_COUNTRIES;

  // 7 traveler fields - starts empty by default (or with the previous trip when editing it)
  const [formData, setFormData] = useState(initialData ? fromRequest(initialData) : {
    departureCity: '',
    destinationCountry: '',
    startDate: '',
    nights: '',
    adults: '',
    childrenCount: 0,
    childrenAges: [],
    budget: ''
  });

  const [errors, setErrors] = useState({});
  const [quickText, setQuickText] = useState('');
  const [quick, setQuick] = useState(null);
  const [quickBusy, setQuickBusy] = useState(false);

  // Type the trip in plain words: the backend reads it with fixed rules (no AI) and we fill the form from it.
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
        budget: f.budget_inr ?? prev.budget
      }));
      setErrors({});
    } catch (e) {
      setQuick({ error: e instanceof NetworkError ? e.message : 'Could not read that request.' });
    } finally {
      setQuickBusy(false);
    }
  };

  // Handle child count change and dynamically manage child age inputs
  const handleChildrenCountChange = (count) => {
    const num = Math.max(0, parseInt(count, 10) || 0);
    const newAges = [...formData.childrenAges];
    if (num > newAges.length) {
      for (let i = newAges.length; i < num; i++) {
        newAges.push(6);
      }
    } else if (num < newAges.length) {
      newAges.splice(num);
    }
    setFormData(prev => ({
      ...prev,
      childrenCount: num,
      childrenAges: newAges
    }));
  };

  const handleChildAgeChange = (index, age) => {
    const updatedAges = [...formData.childrenAges];
    updatedAges[index] = Math.max(0, Math.min(17, parseInt(age, 10) || 0));
    setFormData(prev => ({ ...prev, childrenAges: updatedAges }));
  };

  // Quick-Fill Handlers
  const handleFillSample = () => {
    setFormData({
      departureCity: sampleTrips.standardSample.departureCity,
      destinationCountry: sampleTrips.standardSample.destinationCountry,
      startDate: sampleTrips.standardSample.startDate,
      nights: sampleTrips.standardSample.nights,
      adults: sampleTrips.standardSample.adults,
      childrenCount: sampleTrips.standardSample.children.length,
      childrenAges: [...sampleTrips.standardSample.children],
      budget: sampleTrips.standardSample.budget
    });
    setErrors({});
  };

  const handleFillOverBudget = () => {
    setFormData({
      departureCity: sampleTrips.overBudgetSample.departureCity,
      destinationCountry: sampleTrips.overBudgetSample.destinationCountry,
      startDate: sampleTrips.overBudgetSample.startDate,
      nights: sampleTrips.overBudgetSample.nights,
      adults: sampleTrips.overBudgetSample.adults,
      childrenCount: sampleTrips.overBudgetSample.children.length,
      childrenAges: [...sampleTrips.overBudgetSample.children],
      budget: sampleTrips.overBudgetSample.budget
    });
    setErrors({});
  };

  const handleFillImpossible = () => {
    setFormData({
      departureCity: sampleTrips.impossibleTripSample.departureCity,
      destinationCountry: sampleTrips.impossibleTripSample.destinationCountry,
      startDate: sampleTrips.impossibleTripSample.startDate,
      nights: sampleTrips.impossibleTripSample.nights,
      adults: sampleTrips.impossibleTripSample.adults,
      childrenCount: sampleTrips.impossibleTripSample.children.length,
      childrenAges: [...sampleTrips.impossibleTripSample.children],
      budget: sampleTrips.impossibleTripSample.budget
    });
    setErrors({});
  };

  // Only "is it filled in?" is checked here. Every travel rule is answered by the backend, in its own words.
  const validate = () => {
    const newErrors = {};

    if (!formData.departureCity) {
      newErrors.departureCity = 'Please select a departure city in India.';
    }
    if (!formData.destinationCountry) {
      newErrors.destinationCountry = 'Please select a destination country.';
    }
    if (!formData.startDate) {
      newErrors.startDate = 'Please pick a holiday start date.';
    }
    if (formData.nights === '' || formData.nights === null) {
      newErrors.nights = 'Please enter duration (3–10 nights).';
    }
    if (formData.adults === '' || formData.adults === null) {
      newErrors.adults = 'At least 1 adult traveler is required.';
    }
    for (let i = 0; i < formData.childrenAges.length; i++) {
      if (formData.childrenAges[i] === '' || formData.childrenAges[i] === null) {
        newErrors[`child_${i}`] = 'Child age must be between 0 and 17.';
      }
    }
    if (formData.budget === '' || formData.budget === null) {
      newErrors.budget = 'Please enter a valid budget in INR (greater than 0).';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const submit = async (mode) => {
    if (!validate()) return;
    const result = await onSubmit({
      departureCity: formData.departureCity,
      destinationCountry: formData.destinationCountry,
      startDate: formData.startDate,
      nights: formData.nights,
      adults: formData.adults,
      children: formData.childrenAges,
      budget: formData.budget
    }, mode);
    if (result?.kind === 'INVALID') {
      const mapped = {};
      for (const [field, message] of Object.entries(result.fields || {})) mapped[FIELD_KEY[field] || field] = message;
      setErrors(mapped);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    submit('single');
  };

  return (
    <div className="space-y-4">
      
      {/* Booking.com Hero Banner */}
      <div className="bg-[#003580] text-white rounded-2xl p-6 sm:p-8 shadow-md">
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
          Find your next holiday package
        </h1>
        <p className="text-sm text-white/90 mt-1 max-w-2xl">
          Search all-inclusive packages with flights, hand-picked hotels, ground transfers, and attractions in Japan and the UAE.
        </p>

        {/* Quick Filter Deals Bar (Booking.com style) */}
        <div className="flex items-center gap-2 mt-4 flex-wrap">
          <span className="text-xs font-bold text-[#febb02] flex items-center gap-1 mr-1">
            <Tag className="w-3.5 h-3.5" />
            Quick Test Deals:
          </span>
          <button
            type="button"
            onClick={handleFillSample}
            className="px-3 py-1 text-xs font-bold bg-[#febb02] text-[#003580] hover:bg-[#e5a700] rounded transition-colors flex items-center gap-1 shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5 text-[#003580]" />
            Menon Family Sample (Japan, 6N)
          </button>
          <button
            type="button"
            onClick={handleFillOverBudget}
            className="px-3 py-1 text-xs font-bold bg-white/20 hover:bg-white/30 text-white rounded border border-white/40 transition-colors"
          >
            Test Over-Budget
          </button>
          <button
            type="button"
            onClick={handleFillImpossible}
            className="px-3 py-1 text-xs font-bold bg-white/20 hover:bg-white/30 text-white rounded border border-white/40 transition-colors"
          >
            Test Impossible Dates
          </button>
        </div>
      </div>

      {/* Type your trip in plain words */}
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
            className="flex-1 px-3 py-2 text-xs font-semibold text-slate-800 rounded border-2 border-slate-300 focus:border-[#006ce4] focus:outline-hidden bg-white"
          />
          <button
            type="button"
            onClick={readSentence}
            disabled={quickBusy || !quickText.trim()}
            className="px-4 py-2 text-xs font-bold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded disabled:opacity-50"
          >
            {quickBusy ? 'Reading…' : 'Fill the form'}
          </button>
        </div>
        {quick && (
          <div className="mt-2 space-y-1 text-[11px]">
            {quick.error && <p className="text-[#d4111e] font-bold">{quick.error}</p>}
            {!quick.error && quick.ready && (
              <p className="text-[#008009] font-bold flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Understood everything — check the form below, then search.</p>
            )}
            {!quick.error && quick.missing?.length > 0 && (
              <p className="text-[#b45309] font-bold">Still needed: {quick.missing.join(', ').replaceAll('_', ' ')}.</p>
            )}
            {(quick.notes || []).map((n, i) => <p key={i} className="text-slate-600">• {n}</p>)}
          </div>
        )}
      </div>

      {/* Booking.com Iconic Yellow-Framed Search Box */}
      <div className="bg-white rounded-2xl border-4 border-[#febb02] shadow-xl p-5 sm:p-7">
        
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-100">
          <h2 className="text-base font-extrabold text-[#003580] flex items-center gap-2">
            <Compass className="w-5 h-5 text-[#006ce4]" />
            Trip Builder • 7 Required Parameters
          </h2>
          <span className="text-xs font-bold text-[#008009] flex items-center gap-1 bg-[#008009]/10 px-2 py-0.5 rounded">
            <Check className="w-3.5 h-3.5" />
            Catalog Guaranteed
          </span>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

            {/* 1. Departure City */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1 flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-[#006ce4]" />
                1. Departure City (India)
              </label>
              <select
                value={formData.departureCity}
                onChange={(e) => {
                  setFormData({ ...formData, departureCity: e.target.value });
                  if (errors.departureCity) setErrors({ ...errors, departureCity: null });
                }}
                className={`w-full px-3 py-2.5 text-xs font-semibold text-slate-800 rounded border-2 focus:outline-hidden transition-all bg-white ${
                  errors.departureCity
                    ? 'border-[#d4111e] bg-red-50/20'
                    : 'border-slate-300 focus:border-[#006ce4]'
                }`}
              >
                <option value="">Where are you flying from?</option>
                {departureCities.map((c) => (
                  <option key={c.city} value={c.city}>{c.city} ({c.airport})</option>
                ))}
              </select>
              {errors.departureCity && (
                <p className="mt-1 text-[11px] text-[#d4111e] font-bold flex items-center gap-1">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  {errors.departureCity}
                </p>
              )}
            </div>

            {/* 2. Destination Country */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1 flex items-center gap-1">
                <Plane className="w-3.5 h-3.5 text-[#006ce4]" />
                2. Destination Country
              </label>
              <select
                value={formData.destinationCountry}
                onChange={(e) => {
                  setFormData({ ...formData, destinationCountry: e.target.value });
                  if (errors.destinationCountry) setErrors({ ...errors, destinationCountry: null });
                }}
                className={`w-full px-3 py-2.5 text-xs font-semibold text-slate-800 rounded border-2 focus:outline-hidden transition-all bg-white ${
                  errors.destinationCountry
                    ? 'border-[#d4111e] bg-red-50/20'
                    : 'border-slate-300 focus:border-[#006ce4]'
                }`}
              >
                <option value="">Where are you going?</option>
                {countries.map((c) => (
                  <option key={c.name} value={c.name}>{c.name} ({c.cities.join(', ')})</option>
                ))}
              </select>
              {errors.destinationCountry && (
                <p className="mt-1 text-[11px] text-[#d4111e] font-bold flex items-center gap-1">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  {errors.destinationCountry}
                </p>
              )}
            </div>

            {/* 3. Holiday Start Date */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1 flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-[#006ce4]" />
                3. Check-in / Start Date (Landing Date)
              </label>
              <input
                type="date"
                min="2027-04-01"
                max="2027-04-17"
                value={formData.startDate}
                onChange={(e) => {
                  setFormData({ ...formData, startDate: e.target.value });
                  if (errors.startDate) setErrors({ ...errors, startDate: null });
                }}
                className={`w-full px-3 py-2 text-xs font-semibold text-slate-800 rounded border-2 focus:outline-hidden transition-all bg-white ${
                  errors.startDate
                    ? 'border-[#d4111e] bg-red-50/20'
                    : 'border-slate-300 focus:border-[#006ce4]'
                }`}
              />
              {errors.startDate ? (
                <p className="mt-1 text-[11px] text-[#d4111e] font-bold flex items-center gap-1">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  {errors.startDate}
                </p>
              ) : (
                <p className="mt-1 text-[10px] text-slate-500 font-medium">
                  Valid window: 1 Apr 2027 – 17 Apr 2027
                </p>
              )}
            </div>

            {/* 4. Number of Nights */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1 flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-[#006ce4]" />
                4. Number of Nights (3 to 10)
              </label>
              <input
                type="number"
                min="3"
                max="10"
                placeholder="e.g. 6"
                value={formData.nights}
                onChange={(e) => {
                  setFormData({ ...formData, nights: e.target.value });
                  if (errors.nights) setErrors({ ...errors, nights: null });
                }}
                className={`w-full px-3 py-2 text-xs font-semibold text-slate-800 rounded border-2 focus:outline-hidden transition-all bg-white ${
                  errors.nights
                    ? 'border-[#d4111e] bg-red-50/20'
                    : 'border-slate-300 focus:border-[#006ce4]'
                }`}
              />
              {errors.nights && (
                <p className="mt-1 text-[11px] text-[#d4111e] font-bold flex items-center gap-1">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  {errors.nights}
                </p>
              )}
            </div>

            {/* 5. Adults */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1 flex items-center gap-1">
                <Users className="w-3.5 h-3.5 text-[#006ce4]" />
                5. Adults (Age 18+)
              </label>
              <input
                type="number"
                min="1"
                max="8"
                placeholder="e.g. 2"
                value={formData.adults}
                onChange={(e) => {
                  setFormData({ ...formData, adults: e.target.value });
                  if (errors.adults) setErrors({ ...errors, adults: null });
                }}
                className={`w-full px-3 py-2 text-xs font-semibold text-slate-800 rounded border-2 focus:outline-hidden transition-all bg-white ${
                  errors.adults
                    ? 'border-[#d4111e] bg-red-50/20'
                    : 'border-slate-300 focus:border-[#006ce4]'
                }`}
              />
              {errors.adults && (
                <p className="mt-1 text-[11px] text-[#d4111e] font-bold flex items-center gap-1">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  {errors.adults}
                </p>
              )}
            </div>

            {/* 6. Children Count */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1 flex items-center gap-1">
                <Users className="w-3.5 h-3.5 text-[#006ce4]" />
                6. Children Count (Age 0–17)
              </label>
              <input
                type="number"
                min="0"
                max="6"
                placeholder="0"
                value={formData.childrenCount}
                onChange={(e) => handleChildrenCountChange(e.target.value)}
                className="w-full px-3 py-2 text-xs font-semibold text-slate-800 rounded border-2 border-slate-300 focus:border-[#006ce4] focus:outline-hidden bg-white"
              />
              <p className="mt-1 text-[10px] text-slate-500 font-medium">
                {formData.childrenCount > 0 ? `${formData.childrenCount} child age input(s) rendered below` : 'No children added'}
              </p>
            </div>

            {/* 7. Total Budget in INR */}
            <div className="sm:col-span-2 lg:col-span-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1 flex items-center gap-1">
                    <DollarSign className="w-3.5 h-3.5 text-[#006ce4]" />
                    7. Total Budget in INR (₹)
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-2.5 text-xs font-extrabold text-slate-500">
                      ₹
                    </span>
                    <input
                      type="number"
                      min="1"
                      step="1000"
                      placeholder="e.g. 350000"
                      value={formData.budget}
                      onChange={(e) => {
                        setFormData({ ...formData, budget: e.target.value });
                        if (errors.budget) setErrors({ ...errors, budget: null });
                      }}
                      className={`w-full pl-7 pr-3 py-2 text-xs font-extrabold text-slate-900 rounded border-2 focus:outline-hidden transition-all tabular-nums bg-white ${
                        errors.budget
                          ? 'border-[#d4111e] bg-red-50/20'
                          : 'border-slate-300 focus:border-[#006ce4]'
                      }`}
                    />
                  </div>
                  {errors.budget ? (
                    <p className="mt-1 text-[11px] text-[#d4111e] font-bold flex items-center gap-1">
                      <AlertCircle className="w-3 h-3 shrink-0" />
                      {errors.budget}
                    </p>
                  ) : formData.budget ? (
                    <p className="mt-1 text-[11px] text-[#003580] font-bold tabular-nums">
                      Specified Budget: {formatINR(formData.budget)}
                    </p>
                  ) : null}
                </div>

                {/* Child Age Inputs */}
                {formData.childrenCount > 0 && (
                  <div className="bg-[#f2f6fa] p-3 rounded-lg border border-slate-300">
                    <label className="block text-[11px] font-bold uppercase tracking-wider text-[#003580] mb-2">
                      Child Age Inputs (0–17 years)
                    </label>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {formData.childrenAges.map((age, idx) => (
                        <div key={idx}>
                          <label className="block text-[10px] font-bold text-slate-600 mb-0.5">
                            Child #{idx + 1} Age
                          </label>
                          <input
                            type="number"
                            min="0"
                            max="17"
                            value={age}
                            onChange={(e) => handleChildAgeChange(idx, e.target.value)}
                            className="w-full px-2 py-1 text-xs font-bold bg-white rounded border border-slate-300 focus:border-[#006ce4] focus:outline-hidden tabular-nums"
                          />
                          {errors[`child_${idx}`] && (
                            <span className="text-[9px] text-[#d4111e] block mt-0.5 font-bold">
                              {errors[`child_${idx}`]}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

          </div>

          {/* Submit Action */}
          <div className="mt-6 pt-5 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
              <ShieldCheck className="w-4 h-4 text-[#008009]" />
              <span>Free cancellation on eligible rooms • Instant package confirmation</span>
            </div>

            <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
              <button
                type="button"
                disabled={isLoading}
                onClick={() => submit('compare')}
                className="w-full sm:w-auto px-6 py-3 text-sm font-extrabold text-[#006ce4] bg-white border-2 border-[#006ce4] hover:bg-[#006ce4]/10 rounded-md transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                <Layers className="w-4 h-4" />
                Compare Cheapest · Fastest · Best Rated
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full sm:w-auto px-10 py-3 text-sm font-extrabold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded-md shadow-md transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <Compass className="w-4 h-4 animate-spin" />
                    Building Best Package...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Search className="w-4 h-4" />
                    Search Holiday Packages
                  </span>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>

    </div>
  );
}

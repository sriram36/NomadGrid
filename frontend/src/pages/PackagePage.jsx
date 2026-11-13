import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, Lightbulb, ChevronDown, ChevronUp, SearchX } from 'lucide-react';
import Timeline from '../components/Timeline';
import BudgetSidebar from '../components/BudgetSidebar';
import SwapModal from '../components/SwapModal';
import { useApp } from '../context/AppContext';

const VARIANT_LABEL = {
  CHEAPEST: 'Cheapest', BEST_RATED: 'Best rated', RECOMMENDED: 'Recommended',
  ALTERNATIVE: 'Fits your budget',
};

// "RUSHED_PLAN: only 2 nights..." -> "only 2 nights..."
const plainWarning = (w) => w.replace(/^[A-Z_]+: /, '');

export default function PackagePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const {
    currentPackage, loadPackage, applyChange, handleConfirmBooking, handleRemoveAttraction, handleUndo,
    undoAvailable, swapModalState, setSwapModalState, handleResetTrip,
  } = useApp();
  const [state, setState] = useState(currentPackage?.package_id === id ? 'ready' : 'loading');
  const [showWhy, setShowWhy] = useState(true);

  useEffect(() => {
    let cancelled = false;
    if (currentPackage?.package_id === id) { setState('ready'); return undefined; }
    setState('loading');
    loadPackage(id).then((p) => { if (!cancelled) setState(p ? 'ready' : 'missing'); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const goBack = () => { handleResetTrip(); navigate('/'); };
  const confirmAndShow = async () => {
    const res = await handleConfirmBooking();
    if (res?.ok) navigate(`/reservations/${res.number}`);
  };
  const closeModal = () => setSwapModalState({ isOpen: false, modalType: null, targetItem: null, targetDate: null });
  const open = (modalType, extra = {}) => setSwapModalState({ isOpen: true, modalType, targetItem: null, targetDate: null, ...extra });

  if (state === 'loading') {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-12 h-12 border-4 border-[#003580] border-t-[#febb02] rounded-full animate-spin mx-auto" />
          <p className="text-sm font-bold text-[#003580]">Opening your holiday…</p>
        </div>
      </div>
    );
  }

  if (state === 'missing' || !currentPackage) {
    return (
      <div className="max-w-xl mx-auto px-4 py-16 text-center space-y-4">
        <SearchX className="w-12 h-12 text-slate-400 mx-auto" />
        <h2 className="text-lg font-extrabold text-[#003580]">We couldn't find that holiday</h2>
        <p className="text-sm text-slate-600">The link may be wrong, or the package was never saved.</p>
        <button onClick={goBack} className="px-5 py-2 text-xs font-bold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded">Plan a new holiday</button>
      </div>
    );
  }

  const pkg = currentPackage;
  const booked = pkg.status === 'BOOKED';
  const variantLabel = VARIANT_LABEL[pkg.variant];
  const reasons = pkg.rationale?.reasons || [];

  return (
    <div className="min-h-screen bg-[#f2f6fa]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">

        <button onClick={goBack} className="flex items-center gap-2 text-xs font-bold text-[#006ce4] hover:underline">
          <ArrowLeft className="w-4 h-4" /> New Search
        </button>

        <div className="bg-[#003580] rounded-xl p-6 text-white shadow-md">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#febb02] text-[#003580]">
                  {pkg.country} Holiday Package
                </span>
                {variantLabel && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-white text-[#003580]">{variantLabel}</span>
                )}
                {booked && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#008009] text-white">Booked</span>
                )}
                <span className="text-xs text-white/80 font-bold" data-testid="city-plan">
                  {pkg.cityPlan.map((c) => `${c.city} (${c.nights}N)`).join(' • ')}
                </span>
              </div>
              <h2 className="text-xl sm:text-2xl font-black tracking-tight">{pkg.country} All-Inclusive Itinerary</h2>
              <p className="text-xs text-white/80 mt-1 font-medium">
                From {pkg.traveler.departure_city || 'India'} ({pkg.traveler.home_airport}) •{' '}
                {pkg.traveler.adults} Adults
                {pkg.traveler.children > 0 ? `, ${pkg.traveler.children} Child` : ''}
              </p>
            </div>
            <button onClick={goBack}
              className="px-4 py-2 text-xs font-bold bg-white text-[#003580] hover:bg-slate-100 rounded transition-colors self-start sm:self-auto shadow-sm">
              Change Search
            </button>
          </div>
        </div>

        {pkg.warnings?.length > 0 && (
          <div className="bg-[#fff9e6] border border-[#febb02] rounded-xl p-4 text-xs text-slate-800" role="status" data-testid="warnings">
            <p className="font-black text-[#003580] flex items-center gap-1.5 mb-1">
              <AlertTriangle className="w-4 h-4 text-[#b45309]" /> Worth knowing
            </p>
            <ul className="space-y-0.5 list-disc pl-5">
              {pkg.warnings.map((w, i) => <li key={i}>{plainWarning(w)}</li>)}
            </ul>
          </div>
        )}

        {reasons.length > 0 && (
          <div className="bg-white border border-slate-300 rounded-xl shadow-sm" data-testid="why-panel">
            <button onClick={() => setShowWhy((v) => !v)} aria-expanded={showWhy}
              className="w-full flex items-center justify-between px-4 py-3 text-left">
              <span className="flex items-center gap-2 text-sm font-extrabold text-[#003580]">
                <Lightbulb className="w-4 h-4 text-[#febb02]" /> Why this plan
              </span>
              {showWhy ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
            </button>
            {showWhy && (
              <ul className="px-4 pb-4 space-y-1.5 text-xs text-slate-700 list-disc pl-9">
                {reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <div className="lg:col-span-8 space-y-6">
            <Timeline
              tripPackage={pkg}
              onOpenSwapFlight={booked ? undefined : (item) => open('flight', { targetItem: item })}
              onOpenSwapHotel={booked ? undefined : (item) => open('hotel', { targetItem: item })}
              onRemoveAttraction={booked ? undefined : handleRemoveAttraction}
              onOpenAddAttraction={booked ? undefined : (date) => open('add_attraction', { targetDate: date })}
              readOnly={booked}
            />
          </div>
          <div className="lg:col-span-4">
            <BudgetSidebar
              tripPackage={pkg}
              onConfirmBooking={confirmAndShow}
              onResetTrip={goBack}
              onUndo={handleUndo}
              onOpenCityPlans={() => open('city_plan')}
              undoAvailable={undoAvailable}
              isBooked={booked}
              reservationNumber={pkg.booking?.reference}
            />
          </div>
        </div>

      </div>

      <SwapModal
        isOpen={swapModalState.isOpen}
        onClose={closeModal}
        modalType={swapModalState.modalType}
        targetItem={swapModalState.targetItem}
        targetDate={swapModalState.targetDate}
        tripPackage={pkg}
        onApply={applyChange}
      />
    </div>
  );
}

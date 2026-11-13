import React from 'react';
import { useNavigate } from 'react-router-dom';
import Timeline from '../components/Timeline';
import BudgetSidebar from '../components/BudgetSidebar';
import SwapModal from '../components/SwapModal';
import { useApp } from '../context/AppContext';
import {
  AlertTriangle, ShieldAlert, DollarSign, X, ArrowLeft, CheckCircle2
} from 'lucide-react';
import { formatINR } from '../data/mockTripData';

export default function ResultsPage() {
  const navigate = useNavigate();
  const {
    currentPackage,
    lastRequest,
    generationError,
    isGenerating,
    overBudgetNotice, setOverBudgetNotice,
    swapModalState, setSwapModalState,
    handleConfirmBooking,
    handleResetTrip,
    handleConfirmSwapFlight,
    handleConfirmSwapHotel,
    handleConfirmAddAttraction,
    handleRemoveAttraction,
  } = useApp();

  const goBack = () => {
    handleResetTrip();
    navigate('/');
  };

  // If still generating
  if (isGenerating) {
    return (
      <div className="min-h-screen bg-[#f2f6fa] flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-12 h-12 border-4 border-[#003580] border-t-[#febb02] rounded-full animate-spin mx-auto" />
          <p className="text-sm font-bold text-[#003580]">Optimising your holiday package…</p>
          <p className="text-xs text-slate-500">Checking flights, hotels & attractions</p>
        </div>
      </div>
    );
  }

  // If error (impossible trip)
  if (generationError && !currentPackage) {
    return (
      <div className="min-h-screen bg-[#f2f6fa]">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-6">
          <button onClick={goBack} className="flex items-center gap-2 text-xs font-bold text-[#006ce4] hover:underline">
            <ArrowLeft className="w-4 h-4" /> Back to Search
          </button>

          <div className="bg-red-50 border-2 border-[#d4111e] rounded-xl p-6 text-[#d4111e] shadow-sm">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-red-100 rounded-lg shrink-0">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-sm font-black text-[#d4111e]">No Valid Package Possible for This Request</h3>
                <p className="text-xs text-slate-800 mt-1 leading-relaxed font-medium">{generationError}</p>
                <div className="mt-3 flex items-center gap-2 text-xs">
                  <span className="font-bold text-[#003580]">Recommendation:</span>
                  <span className="text-slate-700">
                    Select dates within 1–20 April 2027, choose 3–10 nights.
                  </span>
                </div>
                <button
                  onClick={goBack}
                  className="mt-4 px-4 py-2 text-xs font-bold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded transition-colors"
                >
                  Modify Search
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // No package at all — redirect prompt
  if (!currentPackage) {
    return (
      <div className="min-h-screen bg-[#f2f6fa] flex items-center justify-center">
        <div className="text-center space-y-4">
          <p className="text-sm font-bold text-slate-600">No package loaded. Please search first.</p>
          <button
            onClick={goBack}
            className="px-5 py-2 text-xs font-bold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded"
          >
            Go to Search
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f2f6fa]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">

        {/* Back link */}
        <button onClick={goBack} className="flex items-center gap-2 text-xs font-bold text-[#006ce4] hover:underline">
          <ArrowLeft className="w-4 h-4" /> New Search
        </button>

        {/* M8: Over-budget warning */}
        {overBudgetNotice && (
          <div className="bg-[#fff9e6] border-2 border-[#febb02] rounded-xl p-5 sm:p-6 text-slate-900 shadow-sm animate-in fade-in duration-150">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-[#febb02] rounded-lg text-[#003580] shrink-0">
                  <DollarSign className="w-6 h-6" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2 py-0.5 rounded bg-[#003580] text-white text-[10px] font-black uppercase tracking-wider">
                      Insufficient Budget Notice
                    </span>
                    <h3 className="text-sm font-black text-[#003580]">
                      Package Exceeds Target Budget by {formatINR(overBudgetNotice.excess)}
                    </h3>
                  </div>
                  <p className="text-xs text-slate-700 mt-1.5 leading-relaxed">
                    No valid holiday package fits within your requested budget of{' '}
                    <strong className="text-slate-900 font-bold">{formatINR(overBudgetNotice.budget)}</strong>. The cheapest compliant package is{' '}
                    <strong className="text-[#003580] font-black">{formatINR(overBudgetNotice.totalCost)}</strong>.
                  </p>
                  <div className="mt-3 p-3 bg-white rounded-lg border border-[#febb02] text-xs text-slate-800 space-y-1">
                    <p className="font-black text-[#003580]">Suggested Adjustments:</p>
                    <p>1. Increase budget by <strong className="text-[#003580]">{formatINR(overBudgetNotice.suggestedAddition)}</strong> to book this package.</p>
                    <p>2. Reduce trip duration from {lastRequest?.nights} to {overBudgetNotice.reducedNights} nights to lower costs.</p>
                  </div>
                </div>
              </div>
              <button onClick={() => setOverBudgetNotice(null)} className="p-1 text-slate-400 hover:text-slate-800 transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* Itinerary Header Banner */}
        <div className="bg-[#003580] rounded-xl p-6 text-white shadow-md">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#febb02] text-[#003580]">
                  {currentPackage.country} Holiday Package
                </span>
                <span className="text-xs text-white/80 font-bold">
                  {currentPackage.cityPlan?.map(c => `${c.city} (${c.nights}N)`).join(' • ')}
                </span>
              </div>
              <h2 className="text-xl sm:text-2xl font-black tracking-tight">
                {currentPackage.country} All-Inclusive Itinerary
              </h2>
              <p className="text-xs text-white/80 mt-1 font-medium">
                From {currentPackage.traveler.departure_city || 'India'} ({currentPackage.traveler.home_airport}) •{' '}
                {currentPackage.traveler.adults} Adults
                {currentPackage.traveler.children > 0 ? `, ${currentPackage.traveler.children} Child` : ''}
              </p>
            </div>
            <button
              onClick={goBack}
              className="px-4 py-2 text-xs font-bold bg-white text-[#003580] hover:bg-slate-100 rounded transition-colors self-start sm:self-auto shadow-sm"
            >
              Change Search
            </button>
          </div>
        </div>

        {/* Two-column layout: Timeline + Sidebar */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

          {/* Left: Timeline */}
          <div className="lg:col-span-8 space-y-6">
            <Timeline
              tripPackage={currentPackage}
              onOpenSwapFlight={(flightItem) => setSwapModalState({ isOpen: true, modalType: 'flight', targetItem: flightItem, targetDate: null })}
              onOpenSwapHotel={(hotelItem) => setSwapModalState({ isOpen: true, modalType: 'hotel', targetItem: hotelItem, targetDate: null })}
              onRemoveAttraction={handleRemoveAttraction}
              onOpenAddAttraction={(date) => setSwapModalState({ isOpen: true, modalType: 'add_attraction', targetItem: null, targetDate: date })}
            />
          </div>

          {/* Right: Sticky Budget Sidebar */}
          <div className="lg:col-span-4">
            <BudgetSidebar
              tripPackage={currentPackage}
              onConfirmBooking={handleConfirmBooking}
              onResetTrip={goBack}
              isBooked={currentPackage.status === 'BOOKED'}
              reservationNumber={currentPackage.booking?.reference}
            />
          </div>
        </div>
      </div>

      {/* M6: Swap Modal */}
      <SwapModal
        isOpen={swapModalState.isOpen}
        onClose={() => setSwapModalState({ isOpen: false, modalType: null, targetItem: null, targetDate: null })}
        modalType={swapModalState.modalType}
        targetItem={swapModalState.targetItem}
        targetDate={swapModalState.targetDate}
        tripPackage={currentPackage}
        onConfirmSwapFlight={handleConfirmSwapFlight}
        onConfirmSwapHotel={handleConfirmSwapHotel}
        onConfirmAddAttraction={handleConfirmAddAttraction}
      />
    </div>
  );
}

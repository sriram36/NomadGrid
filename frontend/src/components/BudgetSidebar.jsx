import React, { useState } from 'react';
import { 
  Download, 
  CheckCircle2, 
  AlertTriangle, 
  CreditCard, 
  Plane, 
  Hotel, 
  Car, 
  MapPin, 
  Copy, 
  RotateCcw,
  Sparkles,
  ShieldCheck,
  Check,
  Lock,
  Undo2,
  Map
} from 'lucide-react';
import { formatINR } from '../lib/format';
import { api } from '../api/client';

export default function BudgetSidebar({
  tripPackage,
  onConfirmBooking,
  onResetTrip,
  onUndo,
  onOpenCityPlans,
  undoAvailable = false,
  isBooked = false,
  reservationNumber = null
}) {
  const [copied, setCopied] = useState(false);
  const [confirming, setConfirming] = useState(false);

  if (!tripPackage || !tripPackage.items) {
    return null;
  }

  const {
    total_inr,
    budget_inr,
    items,
    country,
    start_date,
    end_date,
    nights,
    traveler
  } = tripPackage;

  const flightsSubtotal = items
    .filter(i => i.type === 'flight')
    .reduce((sum, i) => sum + i.price_inr, 0);

  const hotelsSubtotal = items
    .filter(i => i.type === 'hotel')
    .reduce((sum, i) => sum + i.price_inr, 0);

  const transfersSubtotal = items
    .filter(i => i.type === 'transfer')
    .reduce((sum, i) => sum + i.price_inr, 0);

  const attractionsSubtotal = items
    .filter(i => i.type === 'attraction')
    .reduce((sum, i) => sum + i.price_inr, 0);

  const remainingBudget = budget_inr - total_inr;
  const isOverBudget = remainingBudget < 0;

  const handleCopyReservation = () => {
    if (reservationNumber) {
      navigator.clipboard.writeText(reservationNumber);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const exportHref = api.exportUrl(tripPackage.package_id);

  const confirm = async () => {
    setConfirming(true);
    try { await onConfirmBooking(); } finally { setConfirming(false); }
  };

  return (
    <div className="sticky top-20 space-y-4">

      {/* Booking.com Price Summary Card */}
      <div className="bg-white rounded-xl border border-slate-300 shadow-sm p-5 sm:p-6">
        
        {/* Header */}
        <div className="pb-4 mb-4 border-b border-slate-200">
          <div className="flex items-center justify-between">
            <span className="text-xs font-black uppercase tracking-wider text-[#003580] bg-[#f2f6fa] px-2 py-0.5 rounded border border-slate-200">
              Your Booking Summary
            </span>
            <span className="text-xs font-bold text-slate-600">
              {nights} Nights • {traveler.adults} Adults{traveler.children > 0 ? `, ${traveler.children} Children` : ''}
            </span>
          </div>
          <h3 className="text-lg font-extrabold text-[#003580] mt-1.5">
            {country} Holiday Package
          </h3>
          <p className="text-xs text-slate-500 font-medium">
            {start_date} to {end_date}
          </p>
        </div>

        {/* Itemized Subtotals */}
        <div className="space-y-3 pb-4 mb-4 border-b border-slate-200 text-xs">
          
          <div className="flex items-center justify-between text-slate-700">
            <div className="flex items-center gap-2">
              <span className="p-1 rounded bg-[#006ce4]/10 text-[#006ce4]">
                <Plane className="w-3.5 h-3.5" />
              </span>
              <span className="font-semibold">Flights (Return + Arrival)</span>
            </div>
            <span className="font-extrabold text-slate-900 tabular-nums">
              {formatINR(flightsSubtotal)}
            </span>
          </div>

          <div className="flex items-center justify-between text-slate-700">
            <div className="flex items-center gap-2">
              <span className="p-1 rounded bg-[#003580]/10 text-[#003580]">
                <Hotel className="w-3.5 h-3.5" />
              </span>
              <span className="font-semibold">Hotels & Rooms</span>
            </div>
            <span className="font-extrabold text-slate-900 tabular-nums">
              {formatINR(hotelsSubtotal)}
            </span>
          </div>

          <div className="flex items-center justify-between text-slate-700">
            <div className="flex items-center gap-2">
              <span className="p-1 rounded bg-[#febb02]/20 text-[#003580]">
                <Car className="w-3.5 h-3.5" />
              </span>
              <span className="font-semibold">Airport & Intercity Transfers</span>
            </div>
            <span className="font-extrabold text-slate-900 tabular-nums">
              {formatINR(transfersSubtotal)}
            </span>
          </div>

          <div className="flex items-center justify-between text-slate-700">
            <div className="flex items-center gap-2">
              <span className="p-1 rounded bg-[#008009]/10 text-[#008009]">
                <MapPin className="w-3.5 h-3.5" />
              </span>
              <span className="font-semibold">Attractions & Sightseeing</span>
            </div>
            <span className="font-extrabold text-slate-900 tabular-nums">
              {formatINR(attractionsSubtotal)}
            </span>
          </div>

        </div>

        {/* Grand Total & Budget */}
        <div className="space-y-2.5 pb-5 mb-5 border-b border-slate-200">
          
          <div className="flex items-baseline justify-between">
            <div>
              <span className="text-xs font-black uppercase tracking-wider text-slate-600 block">
                Total Price (INR)
              </span>
              <span className="text-[10px] text-slate-500 font-medium">
                Includes taxes and charges
              </span>
            </div>
            <span className="text-2xl font-black text-[#003580] tabular-nums tracking-tight">
              {formatINR(total_inr)}
            </span>
          </div>

          <div className="flex items-center justify-between text-xs text-slate-700">
            <span className="font-medium">Specified Target Budget:</span>
            <span className="font-extrabold tabular-nums text-slate-900">
              {formatINR(budget_inr)}
            </span>
          </div>

          {/* Budget status badge */}
          <div className="pt-1">
            {isOverBudget ? (
              <div className="flex items-center gap-2 p-2.5 rounded bg-red-50 border border-[#d4111e] text-[#d4111e] text-xs font-bold">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>
                  {formatINR(Math.abs(remainingBudget))} Over Budget
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-2 p-2.5 rounded bg-emerald-50 border border-[#008009] text-[#008009] text-xs font-bold">
                <Check className="w-4 h-4 shrink-0" />
                <span>
                  {formatINR(remainingBudget)} Remaining (Within Budget)
                </span>
              </div>
            )}
          </div>

        </div>

        {/* Confirmation Status / Booking CTA */}
        {isBooked ? (
          <div className="mb-4 p-4 rounded-lg bg-emerald-50 border-2 border-[#008009]">
            <div className="flex items-center gap-2 text-[#008009] font-black text-xs mb-1.5">
              <CheckCircle2 className="w-4 h-4 text-[#008009]" />
              <span>RESERVATION CONFIRMED</span>
            </div>
            <p className="text-[11px] text-slate-700 mb-2 font-medium">
              Your 10-digit booking reference is saved on the server:
            </p>
            <div className="flex items-center justify-between bg-white px-3 py-2 rounded border border-[#008009] font-mono text-sm font-black text-slate-900 shadow-sm">
              <span className="tracking-widest text-[#003580]">{reservationNumber}</span>
              <button
                onClick={handleCopyReservation}
                className="text-xs font-bold text-[#006ce4] hover:underline flex items-center gap-1"
                title="Copy Reservation Number"
              >
                <Copy className="w-3.5 h-3.5" />
                <span>{copied ? 'Copied!' : 'Copy'}</span>
              </button>
            </div>
            <p className="text-[10px] text-[#008009] mt-2 font-bold">
              ✓ Open anytime from the top bar or "My Bookings"
            </p>
          </div>
        ) : (
          <div className="mb-4">
            <button
              onClick={confirm}
              disabled={confirming}
              className="w-full py-3.5 px-4 text-sm font-black text-white bg-[#006ce4] hover:bg-[#0057b8] rounded-md shadow-md transition-all flex items-center justify-center gap-2 disabled:opacity-60"
            >
              <Lock className="w-4 h-4" />
              <span>{confirming ? 'Booking…' : 'Confirm & Book Holiday'}</span>
            </button>
            <p className="text-[10px] text-slate-500 text-center mt-1.5 font-medium flex items-center justify-center gap-1">
              <Check className="w-3 h-3 text-[#008009]" />
              Generates unique 10-digit Reservation ID
            </p>
          </div>
        )}

        {/* Actions */}
        <div className="space-y-2">
          {!isBooked && onOpenCityPlans && (
            <button
              onClick={onOpenCityPlans}
              className="w-full py-2.5 px-4 text-xs font-bold text-[#006ce4] hover:bg-[#006ce4]/10 rounded border border-[#006ce4] transition-colors flex items-center justify-center gap-2"
            >
              <Map className="w-3.5 h-3.5" />
              <span>Compare Other City Plans</span>
            </button>
          )}
          {!isBooked && undoAvailable && onUndo && (
            <button
              onClick={onUndo}
              className="w-full py-2.5 px-4 text-xs font-bold text-[#006ce4] hover:bg-[#006ce4]/10 rounded border border-[#006ce4] transition-colors flex items-center justify-center gap-2"
            >
              <Undo2 className="w-3.5 h-3.5" />
              <span>Undo Last Change</span>
            </button>
          )}
          <a
            href={exportHref}
            download
            className="w-full py-2.5 px-4 text-xs font-bold text-[#006ce4] hover:bg-[#006ce4]/10 rounded border border-[#006ce4] transition-colors flex items-center justify-center gap-2"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Package JSON</span>
          </a>

          <button
            onClick={onResetTrip}
            className="w-full py-2 px-4 text-xs font-semibold text-slate-600 hover:text-slate-900 rounded transition-colors flex items-center justify-center gap-1.5"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Search Different Dates / Reset</span>
          </button>
        </div>

      </div>

      {/* Booking.com Guarantee Badges */}
      <div className="bg-white rounded-xl p-4 border border-slate-300 text-xs text-slate-700 space-y-2">
        <div className="flex items-center gap-2 font-black text-[#003580] text-xs">
          <ShieldCheck className="w-4 h-4 text-[#008009]" />
          <span>Booking.com Package Guarantees</span>
        </div>
        <div className="text-[11px] text-slate-600 space-y-1">
          <p className="flex items-center gap-1.5">
            <Check className="w-3.5 h-3.5 text-[#008009] shrink-0" />
            <span><strong>No hidden fees</strong> — catalog verified rates</span>
          </p>
          <p className="flex items-center gap-1.5">
            <Check className="w-3.5 h-3.5 text-[#008009] shrink-0" />
            <span><strong>100% Rules Compliant</strong> — tested transfer buffers</span>
          </p>
          <p className="flex items-center gap-1.5">
            <Check className="w-3.5 h-3.5 text-[#008009] shrink-0" />
            <span><strong>Free cancellation</strong> on participating hotels</span>
          </p>
        </div>
      </div>

    </div>
  );
}

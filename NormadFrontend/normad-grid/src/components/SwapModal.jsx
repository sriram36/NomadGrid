import React, { useState } from 'react';
import { 
  X, 
  RefreshCw, 
  Check, 
  AlertCircle, 
  Plane, 
  Hotel, 
  MapPin, 
  Clock, 
  Users, 
  Star,
  Plus,
  ShieldAlert
} from 'lucide-react';
import { 
  formatINR, 
  getAlternativeFlights, 
  getAlternativeHotels, 
  getAvailableAttractionsForDay 
} from '../data/mockTripData';

export default function SwapModal({
  isOpen,
  onClose,
  modalType, // 'flight' | 'hotel' | 'add_attraction'
  targetItem,
  targetDate,
  tripPackage,
  onConfirmSwapFlight,
  onConfirmSwapHotel,
  onConfirmAddAttraction
}) {
  const [errorBanner, setErrorBanner] = useState(null);

  if (!isOpen || !tripPackage) return null;

  // Render Flight Swapping
  const renderFlightSwap = () => {
    const isArrival = targetItem?.details?.isArrival;
    const alternatives = getAlternativeFlights(targetItem, tripPackage);

    const handleSelectFlight = (alt) => {
      setErrorBanner(null);
      if (!alt.canSwap) {
        setErrorBanner(alt.conflictReason || 'This flight cannot be selected due to travel rule constraints.');
        return;
      }
      onConfirmSwapFlight(targetItem, alt.flight);
      onClose();
    };

    return (
      <div className="space-y-4">
        <div className="bg-[#f2f6fa] p-3.5 rounded-lg border border-slate-300 text-xs">
          <span className="font-bold text-slate-500 uppercase text-[10px] tracking-wider block mb-1">
            Current Flight Selection
          </span>
          <div className="flex items-center justify-between font-extrabold text-[#003580]">
            <span>{targetItem.name}</span>
            <span className="text-slate-900 tabular-nums">{formatINR(targetItem.price_inr)}</span>
          </div>
          <div className="text-slate-600 text-[11px] mt-0.5">
            Timing: {targetItem.start?.substring(11, 16)} → {targetItem.end?.substring(11, 16)} • {targetItem.details?.durationMinutes} mins
          </div>
        </div>

        <h4 className="text-xs font-black uppercase tracking-wider text-[#003580]">
          Available Alternative Flights ({isArrival ? 'Arrival to First City' : 'Homeward Return'})
        </h4>

        {alternatives.length === 0 ? (
          <p className="text-xs text-slate-500 italic py-4 text-center">
            No alternative flights found in the catalog for this date and route.
          </p>
        ) : (
          <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
            {alternatives.map((alt, idx) => (
              <div
                key={alt.flight.flight_id || idx}
                className={`p-3.5 rounded-lg border text-xs transition-all ${
                  alt.canSwap
                    ? 'border-slate-300 hover:border-[#006ce4] bg-white hover:bg-[#f2f6fa]'
                    : 'border-slate-200 bg-slate-50 opacity-80'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-[#003580]">
                        {alt.flight.airline} {alt.flight.flight_number}
                      </span>
                      <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-[10px] font-bold">
                        {alt.flight.from} → {alt.flight.to}
                      </span>
                      <span className="text-[11px] text-slate-500">
                        {alt.flight.stops === 0 ? 'Direct' : '1 Stop'}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 mt-1.5 text-slate-600 text-[11px]">
                      <span className="font-mono tabular-nums font-bold text-slate-800">
                        {alt.flight.departure_local.substring(11, 16)} → {alt.flight.arrival_local.substring(11, 16)}
                      </span>
                      <span>
                        Seats Left: <strong className={alt.hasEnoughSeats ? 'text-slate-900' : 'text-[#d4111e]'}>{alt.flight.seats_left}</strong>
                      </span>
                    </div>

                    {!alt.canSwap && (
                      <div className="mt-2 text-[11px] text-[#d4111e] font-bold flex items-center gap-1">
                        <AlertCircle className="w-3 h-3 shrink-0" />
                        <span>Rule Conflict: {alt.conflictReason}</span>
                      </div>
                    )}
                  </div>

                  <div className="text-right shrink-0">
                    <div className="font-black text-[#003580] tabular-nums">
                      {formatINR(alt.totalPrice)}
                    </div>
                    <div className={`text-[10px] font-bold tabular-nums ${
                      alt.priceDiff > 0 ? 'text-[#d4111e]' : alt.priceDiff < 0 ? 'text-[#008009]' : 'text-slate-400'
                    }`}>
                      {alt.priceDiff > 0 ? `+${formatINR(alt.priceDiff)}` : alt.priceDiff < 0 ? `-${formatINR(Math.abs(alt.priceDiff))}` : 'Same Price'}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleSelectFlight(alt)}
                      className={`mt-2 px-3 py-1 text-xs font-bold rounded transition-colors ${
                        alt.canSwap
                          ? 'bg-[#006ce4] hover:bg-[#0057b8] text-white'
                          : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                      }`}
                    >
                      Select
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Render Hotel Swapping
  const renderHotelSwap = () => {
    const stayNights = targetItem.details?.nights || 3;
    const travelersCount = tripPackage.traveler.adults + tripPackage.traveler.children;
    const alternatives = getAlternativeHotels(
      targetItem,
      targetItem.city,
      targetItem.start,
      stayNights,
      travelersCount,
      tripPackage.traveler.adults,
      tripPackage.traveler.children
    );

    const handleSelectHotel = (alt) => {
      setErrorBanner(null);
      if (!alt.canSwap) {
        setErrorBanner(alt.conflictReason || 'This hotel cannot accommodate your party or lacks availability.');
        return;
      }
      onConfirmSwapHotel(targetItem, alt.hotel, alt.room, alt.roomsNeeded);
      onClose();
    };

    return (
      <div className="space-y-4">
        <div className="bg-[#f2f6fa] p-3.5 rounded-lg border border-slate-300 text-xs">
          <span className="font-bold text-slate-500 uppercase text-[10px] tracking-wider block mb-1">
            Current Hotel in {targetItem.city}
          </span>
          <div className="flex items-center justify-between font-extrabold text-[#003580]">
            <span>{targetItem.name}</span>
            <span className="text-slate-900 tabular-nums">{formatINR(targetItem.price_inr)}</span>
          </div>
          <div className="text-slate-600 text-[11px] mt-0.5">
            {stayNights} Nights • Area: {targetItem.details?.area} • {targetItem.quantity} Room(s)
          </div>
        </div>

        <h4 className="text-xs font-black uppercase tracking-wider text-[#003580]">
          Available Alternative Hotels in {targetItem.city}
        </h4>

        {alternatives.length === 0 ? (
          <p className="text-xs text-slate-500 italic py-4 text-center">
            No other hotels found in {targetItem.city}.
          </p>
        ) : (
          <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
            {alternatives.map((alt, idx) => (
              <div
                key={alt.hotel.hotel_id || idx}
                className={`p-3.5 rounded-lg border text-xs transition-all ${
                  alt.canSwap
                    ? 'border-slate-300 hover:border-[#006ce4] bg-white hover:bg-[#f2f6fa]'
                    : 'border-slate-200 bg-slate-50 opacity-80'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-[#003580]">
                        {alt.hotel.name}
                      </span>
                      <div className="w-6 h-6 rounded-t rounded-br bg-[#003580] text-white font-extrabold text-[10px] flex items-center justify-center">
                        {(alt.hotel.stars * 1.8).toFixed(1)}
                      </div>
                      <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px] font-semibold">
                        {alt.hotel.area}
                      </span>
                    </div>

                    {alt.room && (
                      <div className="mt-1 text-slate-700 text-[11px]">
                        Room Type: <strong>{alt.room.name}</strong> ({alt.roomsNeeded} room needed)
                      </div>
                    )}

                    {!alt.canSwap && (
                      <div className="mt-2 text-[11px] text-[#d4111e] font-bold flex items-center gap-1">
                        <AlertCircle className="w-3 h-3 shrink-0" />
                        <span>Rule Conflict: {alt.conflictReason}</span>
                      </div>
                    )}
                  </div>

                  <div className="text-right shrink-0">
                    <div className="font-black text-[#003580] tabular-nums">
                      {formatINR(alt.totalPrice)}
                    </div>
                    <div className={`text-[10px] font-bold tabular-nums ${
                      alt.priceDiff > 0 ? 'text-[#d4111e]' : alt.priceDiff < 0 ? 'text-[#008009]' : 'text-slate-400'
                    }`}>
                      {alt.priceDiff > 0 ? `+${formatINR(alt.priceDiff)}` : alt.priceDiff < 0 ? `-${formatINR(Math.abs(alt.priceDiff))}` : 'Same Price'}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleSelectHotel(alt)}
                      className={`mt-2 px-3 py-1 text-xs font-bold rounded transition-colors ${
                        alt.canSwap
                          ? 'bg-[#006ce4] hover:bg-[#0057b8] text-white'
                          : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                      }`}
                    >
                      Select
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Render Add Attraction
  const renderAddAttraction = () => {
    const available = getAvailableAttractionsForDay(targetDate, tripPackage);

    const handleSelectAttraction = (cand) => {
      setErrorBanner(null);
      if (!cand.canAdd) {
        setErrorBanner(cand.conflictReason || 'This attraction cannot be scheduled due to opening hours or schedule conflicts.');
        return;
      }
      onConfirmAddAttraction(cand.attraction, targetDate, cand.availableSlot);
      onClose();
    };

    return (
      <div className="space-y-4">
        <div className="bg-[#f2f6fa] p-3 rounded-lg border border-slate-300 text-xs">
          <span className="text-slate-700 font-bold">
            Adding Sightseeing for Date: <strong className="text-[#003580]">{targetDate}</strong>
          </span>
          <p className="text-[11px] text-slate-500 mt-0.5">
            Verified for opening days, operating hours, and zero overlap with existing activities.
          </p>
        </div>

        <h4 className="text-xs font-black uppercase tracking-wider text-[#003580]">
          Available Attractions in Catalog
        </h4>

        {available.length === 0 ? (
          <p className="text-xs text-slate-500 italic py-4 text-center">
            No more available attractions in this city that fit the remaining time slots.
          </p>
        ) : (
          <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
            {available.map((cand, idx) => (
              <div
                key={cand.attraction.attraction_id || idx}
                className={`p-3.5 rounded-lg border text-xs transition-all ${
                  cand.canAdd
                    ? 'border-slate-300 hover:border-[#008009] bg-white hover:bg-emerald-50/20'
                    : 'border-slate-200 bg-slate-50 opacity-80'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-[#003580]">
                        {cand.attraction.name}
                      </span>
                      <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-[#008009] border border-emerald-200 text-[10px] font-bold">
                        {cand.attraction.category}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 mt-1 text-slate-500 text-[11px]">
                      <span>Hours: {cand.attraction.open_from} - {cand.attraction.open_until}</span>
                      <span>Visit: {cand.attraction.visit_minutes}m</span>
                      {cand.canAdd && (
                        <span className="text-[#006ce4] font-bold">
                          Slot: {cand.availableSlot.start} - {cand.availableSlot.end}
                        </span>
                      )}
                    </div>

                    {!cand.canAdd && (
                      <div className="mt-2 text-[11px] text-[#d4111e] font-bold flex items-center gap-1">
                        <AlertCircle className="w-3 h-3 shrink-0" />
                        <span>Rule Conflict: {cand.conflictReason}</span>
                      </div>
                    )}
                  </div>

                  <div className="text-right shrink-0">
                    <div className="font-black text-[#003580] tabular-nums">
                      {formatINR(cand.price)}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleSelectAttraction(cand)}
                      className={`mt-2 px-3 py-1 text-xs font-bold rounded transition-colors ${
                        cand.canAdd
                          ? 'bg-[#008009] hover:bg-emerald-700 text-white'
                          : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                      }`}
                    >
                      Add
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 bg-[#003580]/50 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl border border-slate-300 max-w-xl w-full p-6 animate-in fade-in zoom-in-95 duration-150">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded bg-[#006ce4]/10 text-[#006ce4]">
              <RefreshCw className="w-4 h-4" />
            </span>
            <h3 className="text-base font-extrabold text-[#003580]">
              {modalType === 'flight' && 'Change Flight (Rule Re-Validation)'}
              {modalType === 'hotel' && 'Change Room / Hotel (Booking.com Rules)'}
              {modalType === 'add_attraction' && 'Add Sightseeing (Schedule Check)'}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-700 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Conflict Alert Banner */}
        {errorBanner && (
          <div className="mb-4 p-3 rounded bg-red-50 border border-[#d4111e] text-[#d4111e] text-xs font-semibold flex items-start gap-2">
            <ShieldAlert className="w-4 h-4 shrink-0 text-[#d4111e] mt-0.5" />
            <div>
              <p className="font-bold">Edit Refused (Booking Rule Conflict):</p>
              <p>{errorBanner}</p>
            </div>
          </div>
        )}

        {/* Modal Content */}
        {modalType === 'flight' && renderFlightSwap()}
        {modalType === 'hotel' && renderHotelSwap()}
        {modalType === 'add_attraction' && renderAddAttraction()}

        {/* Modal Footer */}
        <div className="mt-6 pt-4 border-t border-slate-200 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-bold text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded transition-colors"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
}

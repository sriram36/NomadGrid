import React, { useState } from 'react';
import { 
  Plane, 
  Hotel, 
  Car, 
  MapPin, 
  Clock, 
  Plus, 
  Trash2, 
  RefreshCw, 
  Star, 
  ShieldCheck, 
  AlertTriangle,
  Info,
  Calendar,
  Sparkles,
  ArrowRight,
  Check,
  BookOpen
} from 'lucide-react';
import { formatINR, addDays } from '../lib/format';

export default function Timeline({
  tripPackage,
  onOpenSwapFlight,
  onOpenSwapHotel,
  onOpenCityGuide,
  onRemoveAttraction,
  onOpenAddAttraction,
  readOnly = false
}) {
  const [selectedDayFilter, setSelectedDayFilter] = useState('ALL');

  if (!tripPackage || !tripPackage.items) {
    return null;
  }

  const { start_date, end_date, nights, country, items } = tripPackage;

  const daysList = [];
  for (let i = 0; i <= nights; i++) {
    const curDate = addDays(start_date, i);
    daysList.push({
      dayNumber: i + 1,
      date: curDate,
      isArrivalDay: i === 0,
      isDepartureDay: i === nights,
      isSightseeingDay: i > 0 && i < nights
    });
  }

  const getItemsForDay = (date, isArrival, isDeparture) => {
    const dayItems = [];

    // 1. Flights
    items.filter(item => item.type === 'flight').forEach(flight => {
      if (isArrival && flight.details?.isArrival) {
        dayItems.push({
          ...flight,
          sortTime: flight.end?.substring(11, 16) || '08:00',
          displayTime: `${flight.start?.substring(11, 16)} → ${flight.end?.substring(11, 16)}`,
          timeLabel: 'Arrival Flight'
        });
      }
      if (isDeparture && flight.details?.isReturn) {
        dayItems.push({
          ...flight,
          sortTime: flight.start?.substring(11, 16) || '12:00',
          displayTime: `${flight.start?.substring(11, 16)} → ${flight.end?.substring(11, 16)}`,
          timeLabel: 'Return Flight'
        });
      }
    });

    // 2. Transfers
    items.filter(item => item.type === 'transfer').forEach(transfer => {
      const transDate = transfer.start?.substring(0, 10);
      if (transDate === date) {
        dayItems.push({
          ...transfer,
          sortTime: transfer.start?.substring(11, 16) || '11:00',
          displayTime: `${transfer.start?.substring(11, 16)} → ${transfer.end?.substring(11, 16)}`,
          timeLabel: transfer.details?.isAirportTransfer ? 'Airport Transfer' : 'City-to-City Transit'
        });
      }
    });

    // 3. Hotel Check-in / Night
    items.filter(item => item.type === 'hotel').forEach(hotel => {
      if (hotel.start === date) {
        dayItems.push({
          ...hotel,
          sortTime: '15:00',
          displayTime: `Check-in from ${hotel.details?.checkInFrom || '15:00'}`,
          timeLabel: 'Hotel Accommodation'
        });
      }
    });

    // 4. Attractions
    items.filter(item => item.type === 'attraction').forEach(att => {
      const attDate = att.start?.substring(0, 10);
      if (attDate === date) {
        dayItems.push({
          ...att,
          sortTime: att.start?.substring(11, 16) || '10:00',
          displayTime: `${att.start?.substring(11, 16)} - ${att.end?.substring(11, 16)}`,
          timeLabel: 'Sightseeing & Culture'
        });
      }
    });

    dayItems.sort((a, b) => (a.sortTime || '').localeCompare(b.sortTime || ''));
    return dayItems;
  };

  const filteredDays = selectedDayFilter === 'ALL'
    ? daysList
    : daysList.filter(d => `Day ${d.dayNumber}` === selectedDayFilter);

  return (
    <div className="space-y-6">

      {/* Booking.com Filter Bar */}
      <div className="bg-white rounded-xl border border-slate-300 shadow-sm p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-[#006ce4]" />
            <h3 className="text-base font-extrabold text-[#003580]">
              Day-by-Day Master Itinerary
            </h3>
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-[#febb02] text-[#003580]">
              {nights} Nights / {nights + 1} Days
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-0.5">
            Verified schedule with 60-min post-landing and 180-min pre-flight buffers
          </p>
        </div>

        {/* Day Filter Buttons */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 max-w-full">
          <button
            onClick={() => setSelectedDayFilter('ALL')}
            className={`px-3 py-1.5 text-xs font-bold rounded-full shrink-0 transition-colors ${
              selectedDayFilter === 'ALL'
                ? 'bg-[#003580] text-white'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            All Days ({daysList.length})
          </button>
          {daysList.map(d => (
            <button
              key={d.dayNumber}
              onClick={() => setSelectedDayFilter(`Day ${d.dayNumber}`)}
              className={`px-3 py-1.5 text-xs font-bold rounded-full shrink-0 transition-colors ${
                selectedDayFilter === `Day ${d.dayNumber}`
                  ? 'bg-[#006ce4] text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              Day {d.dayNumber}
            </button>
          ))}
        </div>
      </div>

      {/* Day Cards */}
      <div className="space-y-6">
        {filteredDays.map(day => {
          const dayItems = getItemsForDay(day.date, day.isArrivalDay, day.isDepartureDay);

          return (
            <div key={day.dayNumber} className="relative">
              
              {/* Day Header Banner (Booking.com deep blue strip) */}
              <div className="flex items-center justify-between bg-white rounded-t-xl px-4 py-3 border border-slate-300 border-b-2 border-b-[#003580]">
                <div className="flex items-center gap-3">
                  <span className="px-2.5 py-1 rounded bg-[#003580] text-white text-xs font-black shadow-sm">
                    Day {day.dayNumber}
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-extrabold text-slate-900">
                        {day.date}
                      </h4>
                      {day.isArrivalDay && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-[#006ce4]/10 text-[#006ce4]">
                          Flight Arrival in {country}
                        </span>
                      )}
                      {day.isDepartureDay && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-slate-200 text-slate-800">
                          Return to India
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {!day.isDepartureDay && !readOnly && (
                  <button
                    onClick={() => onOpenAddAttraction(day.date)}
                    className="px-3 py-1 text-xs font-bold text-[#006ce4] hover:bg-[#006ce4]/10 rounded border border-[#006ce4] transition-colors flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add Attraction</span>
                  </button>
                )}
              </div>

              {/* Day Events */}
              <div className="bg-white rounded-b-xl border-x border-b border-slate-300 p-4 sm:p-5 space-y-4">
                {dayItems.length === 0 ? (
                  <div className="p-4 bg-slate-50 rounded border border-dashed border-slate-200 text-xs text-slate-500 text-center">
                    No scheduled items for this day.
                  </div>
                ) : (
                  dayItems.map((item, idx) => {
                    const isFlight = item.type === 'flight';
                    const isHotel = item.type === 'hotel';
                    const isTransfer = item.type === 'transfer';
                    const isAttraction = item.type === 'attraction';

                    return (
                      <div
                        key={item.item_id || idx}
                        className={`rounded-xl border p-4 sm:p-5 transition-all hover:shadow-md ${
                          isHotel
                            ? 'border-slate-300 bg-white hover:border-[#003580]'
                            : isFlight
                            ? 'border-slate-300 bg-white hover:border-[#006ce4]'
                            : isTransfer
                            ? 'border-slate-300 bg-white hover:border-amber-400'
                            : 'border-slate-300 bg-white hover:border-emerald-400'
                        }`}
                      >
                        {/* Top Bar */}
                        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-3 mb-3 border-b border-slate-100">
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              {/* Category Badge */}
                              <span
                                className={`text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded ${
                                  isHotel
                                    ? 'bg-[#003580] text-white'
                                    : isFlight
                                    ? 'bg-[#006ce4] text-white'
                                    : isTransfer
                                    ? 'bg-[#febb02] text-[#003580]'
                                    : 'bg-[#008009] text-white'
                                }`}
                              >
                                {item.timeLabel || item.type}
                              </span>

                              {/* Time */}
                              <span className="flex items-center gap-1 text-xs font-bold text-slate-800 font-mono tabular-nums">
                                <Clock className="w-3.5 h-3.5 text-slate-500" />
                                {item.displayTime}
                              </span>

                              <span className="text-xs font-bold text-slate-500">
                                • {item.city}
                              </span>
                            </div>

                            {/* Name */}
                            <h5 className="text-base font-extrabold text-[#003580] mt-1.5 tracking-tight">
                              {item.name}
                            </h5>
                          </div>

                          {/* Price & Booking.com style rating badge */}
                          <div className="flex sm:flex-col items-baseline sm:items-end justify-between gap-1 shrink-0">
                            {isHotel && item.details && (
                              <div className="flex items-center gap-1.5 mb-1">
                                <div className="text-right hidden sm:block">
                                  <span className="text-[11px] font-bold text-slate-800 block leading-tight">
                                    {item.details.stars >= 4 ? 'Wonderful' : 'Very Good'}
                                  </span>
                                  <span className="text-[10px] text-slate-500">
                                    {item.details.stars}-star hotel
                                  </span>
                                </div>
                                <div className="w-8 h-8 rounded-t rounded-br bg-[#003580] text-white font-extrabold text-xs flex items-center justify-center shadow-xs">
                                  {Number(item.details.rating ?? item.details.stars * 1.8).toFixed(1)}
                                </div>
                              </div>
                            )}

                            <div>
                              <div className="text-base font-black text-slate-900 tabular-nums">
                                {formatINR(item.price_inr)}
                              </div>
                              <div className="text-[10px] font-medium text-slate-500">
                                {isFlight && `${item.quantity} passenger seat(s)`}
                                {isHotel && `${item.quantity} room(s) • ${item.details?.nights || 1} nights`}
                                {isTransfer && (item.details?.pricing === 'PER_PERSON' ? `${item.quantity} passenger(s)` : `${item.quantity} private vehicle(s)`)}
                                {isAttraction && `${item.quantity} ticket(s)`}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Details & Actions */}
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-slate-600">
                          
                          <div className="flex items-center gap-3 flex-wrap">
                            {isFlight && item.details && (
                              <>
                                <span className="font-bold text-[#003580] bg-slate-100 px-2 py-0.5 rounded">
                                  {item.details.airline} • {item.details.flightNumber}
                                </span>
                                <span className="text-slate-600 font-semibold">
                                  {item.details.stops === 0 ? 'Direct flight' : `${item.details.stops} stop`}
                                </span>
                                <span className="text-slate-500">
                                  Duration: {Math.floor(item.details.durationMinutes / 60)}h {item.details.durationMinutes % 60}m
                                </span>
                              </>
                            )}

                            {isTransfer && item.details && (
                              <>
                                <span className="font-bold text-[#003580] bg-slate-100 px-2 py-0.5 rounded">
                                  {item.details.transferType?.replace(/_/g, ' ')}
                                </span>
                                <span className="text-slate-600">
                                  Duration: {item.details.durationMinutes} mins
                                </span>
                                {item.details.isAirportTransfer && (
                                  <span className="text-[#008009] font-bold bg-[#008009]/10 px-2 py-0.5 rounded text-[11px] flex items-center gap-1">
                                    <Check className="w-3 h-3" /> Buffer verified
                                  </span>
                                )}
                              </>
                            )}

                            {isHotel && item.details && (
                              <>
                                <span className="text-slate-700 font-semibold">
                                  Area: <strong>{item.details.area}</strong>
                                </span>
                                {item.details.refundable === false ? (
                                  <span className="text-slate-500 font-semibold">Non-refundable</span>
                                ) : (
                                  <span className="text-[#008009] font-bold flex items-center gap-1">
                                    <Check className="w-3.5 h-3.5" /> Free cancellation
                                  </span>
                                )}
                                <span className="text-slate-500">
                                  {formatINR(item.details.pricePerNight)} / night
                                </span>
                              </>
                            )}

                            {isAttraction && item.details && (
                              <>
                                <span className="font-bold text-[#003580] bg-slate-100 px-2 py-0.5 rounded">
                                  {item.details.category}
                                </span>
                                <span className="text-slate-600">
                                  Visit: {item.details.visitMinutes}m
                                </span>
                                <span className="text-slate-500">
                                  Hours: {item.details.openHours}
                                </span>
                              </>
                            )}
                          </div>

                          {/* Action Buttons */}
                          <div className="flex items-center gap-2 shrink-0">
                            {isFlight && !readOnly && (
                              <button
                                onClick={() => onOpenSwapFlight(item)}
                                className="px-3 py-1.5 text-xs font-bold text-[#006ce4] hover:bg-[#006ce4]/10 rounded border border-[#006ce4] transition-colors flex items-center gap-1"
                              >
                                <RefreshCw className="w-3 h-3" />
                                <span>Change Flight</span>
                              </button>
                            )}

                            {isHotel && onOpenCityGuide && (
                              <button
                                onClick={() => onOpenCityGuide(item)}
                                className="px-3 py-1.5 text-xs font-bold text-[#003580] hover:bg-[#003580]/10 rounded border border-[#003580]/40 transition-colors flex items-center gap-1"
                              >
                                <BookOpen className="size-3" />
                                <span>City Guide</span>
                              </button>
                            )}

                            {isHotel && !readOnly && (
                              <button
                                onClick={() => onOpenSwapHotel(item)}
                                className="px-3 py-1.5 text-xs font-bold text-[#006ce4] hover:bg-[#006ce4]/10 rounded border border-[#006ce4] transition-colors flex items-center gap-1"
                              >
                                <RefreshCw className="w-3 h-3" />
                                <span>Change Room / Hotel</span>
                              </button>
                            )}

                            {isAttraction && !readOnly && (
                              <button
                                onClick={() => onRemoveAttraction(item)}
                                className="px-2 py-1 text-xs font-semibold text-[#d4111e] hover:bg-red-50 rounded transition-colors flex items-center gap-1"
                                title="Remove Sightseeing"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                                <span>Remove</span>
                              </button>
                            )}
                          </div>

                        </div>

                      </div>
                    );
                  })
                )}
              </div>

            </div>
          );
        })}
      </div>

    </div>
  );
}

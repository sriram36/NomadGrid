import React, { useState } from 'react';
import { 
  Bookmark, 
  Calendar, 
  MapPin, 
  Users, 
  CreditCard, 
  CheckCircle2, 
  ArrowRight, 
  Trash2, 
  Copy, 
  Download,
  PlaneTakeoff,
  Luggage,
  Check
} from 'lucide-react';
import { formatINR } from '../lib/format';
import { api } from '../api/client';

export default function MyBookingsPage({
  bookings = [],
  onSelectBooking,
  onDeleteBooking,
  onStartNewTrip
}) {
  const [copiedId, setCopiedId] = useState(null);

  const handleCopy = (refId) => {
    navigator.clipboard.writeText(refId);
    setCopiedId(refId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">

      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-300 p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <Bookmark className="w-5 h-5 text-[#006ce4]" />
            <h2 className="text-xl font-extrabold text-[#003580] tracking-tight">
              My Bookings & Trips
            </h2>
          </div>
          <p className="text-xs text-slate-600 mt-1">
            Your confirmed holidays are saved on the server, so they are here even after a restart.
          </p>
        </div>

        <button
          onClick={onStartNewTrip}
          className="px-4 py-2 text-xs font-black text-white bg-[#006ce4] hover:bg-[#0057b8] rounded transition-colors shadow-sm flex items-center gap-1.5 self-start sm:self-auto"
        >
          <PlaneTakeoff className="w-4 h-4" />
          <span>Plan New Holiday</span>
        </button>
      </div>

      {/* Bookings List */}
      {bookings.length === 0 ? (
        <div className="bg-white rounded-xl border-2 border-dashed border-slate-300 p-12 text-center">
          <div className="w-14 h-14 rounded-full bg-[#f2f6fa] border border-slate-300 flex items-center justify-center text-[#003580] mx-auto mb-3">
            <Luggage className="w-7 h-7" />
          </div>
          <h3 className="text-base font-extrabold text-[#003580]">
            No Confirmed Reservations Found
          </h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 mb-6">
            You haven't confirmed any holiday bookings yet. Use the Trip Builder to create a package and click "Confirm & Book".
          </p>
          <button
            onClick={onStartNewTrip}
            className="px-6 py-2.5 text-xs font-black text-white bg-[#006ce4] hover:bg-[#0057b8] rounded shadow-sm transition-colors"
          >
            Start Planning Now
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {bookings.map((booking) => {
            const refNumber = booking.booking?.reference || booking.trip_id;

            return (
              <div
                key={refNumber}
                className="bg-white rounded-xl border border-slate-300 p-5 hover:border-[#003580] shadow-sm transition-all flex flex-col justify-between"
              >
                <div>
                  
                  {/* Top Bar */}
                  <div className="flex items-start justify-between pb-3 mb-3 border-b border-slate-100 gap-2">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                        10-Digit Reservation Number
                      </span>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="font-mono text-base font-black text-[#003580] tracking-wider">
                          {refNumber}
                        </span>
                        <button
                          onClick={() => handleCopy(refNumber)}
                          className="text-slate-400 hover:text-slate-700 transition-colors p-1"
                          title="Copy Reservation ID"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                        {copiedId === refNumber && (
                          <span className="text-[10px] font-bold text-[#008009]">
                            Copied!
                          </span>
                        )}
                      </div>
                    </div>

                    <span className="px-2.5 py-1 rounded text-[10px] font-extrabold bg-[#008009]/10 text-[#008009] border border-[#008009]/30 flex items-center gap-1 shrink-0">
                      <Check className="w-3 h-3 text-[#008009]" />
                      BOOKED
                    </span>
                  </div>

                  {/* Trip Info */}
                  <div className="space-y-2 text-xs text-slate-700 mb-4">
                    <div className="flex items-center gap-2">
                      <MapPin className="w-3.5 h-3.5 text-[#006ce4]" />
                      <span className="font-bold text-[#003580]">
                        {booking.country} ({booking.cityPlan?.map(c => c.city).join(' → ') || 'Multi-City'})
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Calendar className="w-3.5 h-3.5 text-[#006ce4]" />
                      <span>
                        {booking.start_date} to {booking.end_date} ({booking.nights} Nights)
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Users className="w-3.5 h-3.5 text-[#006ce4]" />
                      <span>
                        {booking.traveler.adults} Adults
                        {booking.traveler.children > 0 ? `, ${booking.traveler.children} Children` : ''} • From {booking.traveler.departure_city || 'India'}
                      </span>
                    </div>
                  </div>

                </div>

                {/* Bottom Total & Actions */}
                <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-slate-500 block leading-tight">
                      Confirmed Total
                    </span>
                    <span className="text-base font-black text-[#003580] tabular-nums">
                      {formatINR(booking.total_inr)}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <a
                      href={api.exportUrl(booking.package_id)}
                      download
                      className="p-2 text-slate-600 hover:text-[#006ce4] hover:bg-[#f2f6fa] rounded border border-slate-200 transition-colors"
                      title="Download Package JSON"
                    >
                      <Download className="w-4 h-4" />
                    </a>

                    <button
                      onClick={() => onDeleteBooking(refNumber)}
                      className="p-2 text-slate-400 hover:text-[#d4111e] hover:bg-red-50 rounded border border-slate-200 transition-colors"
                      title="Remove from this device's list (the reservation stays on the server)"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>

                    <button
                      onClick={() => onSelectBooking(booking)}
                      className="px-3.5 py-1.5 text-xs font-bold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded transition-colors flex items-center gap-1 shadow-xs"
                    >
                      <span>View Itinerary</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}

import React, { useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { CheckCircle2, Copy, Check, Eye, Download, ShieldAlert } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import { formatINR } from '../lib/format';

export default function ConfirmationPage() {
  const navigate = useNavigate();
  const { number } = useParams();
  const { currentPackage, handleLookupReservation, handleResetTrip } = useApp();
  const [missing, setMissing] = useState(false);
  const [copied, setCopied] = useState(false);

  const pkg = currentPackage?.booking?.reference === number ? currentPackage : null;

  // After a page refresh the reservation is fetched from the server again.
  useEffect(() => {
    if (pkg) return undefined;
    let cancelled = false;
    setMissing(false);
    handleLookupReservation(number).then((found) => { if (!cancelled && !found) setMissing(true); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [number]);

  const planAnother = () => { handleResetTrip(); navigate('/'); };

  const handleCopy = () => {
    navigator.clipboard?.writeText(number);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (missing) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center px-4">
        <div className="bg-white rounded-xl border border-slate-300 shadow-sm p-8 text-center max-w-sm space-y-3">
          <ShieldAlert className="w-10 h-10 text-[#d4111e] mx-auto" />
          <h2 className="text-base font-black text-[#003580]">Reservation not found</h2>
          <p className="text-xs text-slate-600">No reservation matches #{number}. Check the number and try again.</p>
          <button onClick={planAnother} className="px-5 py-2 text-xs font-bold text-white bg-[#006ce4] hover:bg-[#0057b8] rounded">
            Back to Search
          </button>
        </div>
      </div>
    );
  }

  if (!pkg) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-[#003580] border-t-[#febb02] rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f2f6fa]">
      <div className="max-w-xl mx-auto px-4 sm:px-6 py-10 sm:py-16">
        <div className="bg-white rounded-xl border border-slate-300 shadow-sm overflow-hidden">
          {/* Success header */}
          <div className="bg-[#003580] px-6 py-8 text-center text-white">
            <div className="w-14 h-14 rounded-full bg-[#008009] flex items-center justify-center mx-auto mb-3">
              <CheckCircle2 className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-xl sm:text-2xl font-black tracking-tight">Your holiday is confirmed!</h1>
            <p className="text-xs sm:text-sm text-white/80 mt-1 font-medium">
              {pkg.country} · {pkg.start_date} to {pkg.end_date}
            </p>
          </div>

          {/* Reservation number */}
          <div className="px-6 py-8 text-center space-y-4">
            <p className="text-xs font-black uppercase tracking-wider text-slate-600">
              Your 10-digit reservation number
            </p>
            <div className="inline-block bg-[#f2f6fa] border-2 border-[#008009] rounded-lg px-6 py-4">
              <span data-testid="reservation-number" className="font-mono text-3xl sm:text-4xl font-black tracking-[0.2em] text-[#003580]">
                {number}
              </span>
            </div>
            <div>
              <button onClick={handleCopy} className="text-xs font-bold text-[#006ce4] hover:underline inline-flex items-center gap-1.5">
                {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? 'Copied!' : 'Copy number'}
              </button>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Please save this number. You can enter it in the top bar at any time to view your itinerary.
            </p>
            <p className="text-xs font-bold text-slate-800">
              Total: <span className="text-[#003580]">{formatINR(pkg.total_inr)}</span>
            </p>
          </div>

          {/* Actions */}
          <div className="px-6 pb-6 space-y-2">
            <Link
              to={`/packages/${pkg.package_id}`}
              className="w-full py-3 px-4 text-sm font-black text-white bg-[#006ce4] hover:bg-[#0057b8] rounded-md shadow-md transition-all flex items-center justify-center gap-2"
            >
              <Eye className="w-4 h-4" />
              <span>View my itinerary</span>
            </Link>
            <a
              href={api.exportUrl(pkg.package_id)}
              className="w-full py-2.5 px-4 text-xs font-bold text-[#006ce4] hover:bg-[#006ce4]/10 rounded border border-[#006ce4] transition-colors flex items-center justify-center gap-2"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export Package JSON</span>
            </a>
            <button onClick={planAnother} className="w-full py-2 px-4 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors">
              Plan another trip
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

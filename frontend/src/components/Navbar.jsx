import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Search, PlaneTakeoff } from 'lucide-react';
import { useApp } from '../context/AppContext';

export default function Navbar() {
  const navigate = useNavigate();
  const { handleLookupReservation } = useApp();
  const [looking, setLooking] = useState(false);

  const [lookupId, setLookupId] = useState('');
  const [lookupError, setLookupError] = useState('');

  const handleLookupSubmit = async (e) => {
    e.preventDefault();
    setLookupError('');
    const trimmed = lookupId.trim();
    if (!trimmed) { setLookupError('Please enter a 10-digit reservation number.'); return; }
    if (!/^\d{10}$/.test(trimmed)) { setLookupError('Reservation number must be exactly 10 digits.'); return; }
    setLooking(true);
    const found = await handleLookupReservation(trimmed);
    setLooking(false);
    if (!found) {
      setLookupError(`Reservation #${trimmed} not found in records.`);
    } else {
      setLookupId('');
      setLookupError('');
      navigate(`/packages/${found.package_id}`);
    }
  };

  return (
    <header className="sticky top-0 z-50 bg-[#003580] text-white shadow-md border-b border-[#00224f]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-4">

          {/* Left: Logo + Nav */}
          <div className="flex items-center gap-2 sm:gap-6">
            <Link to="/" className="flex items-center gap-2 text-left group focus:outline-hidden">
              <div className="text-2xl font-black tracking-tight flex items-baseline">
                <span className="text-white">normad</span>
                <span className="text-[#febb02]">.grid</span>
              </div>
              <span className="hidden sm:inline-block text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#00224f] text-[#febb02] border border-[#febb02]/30 ml-1">
                Packages
              </span>
            </Link>

            {/* Nav Tabs */}
            <nav className="flex items-center gap-1 sm:gap-2 pl-2 sm:pl-4 border-l border-white/20">
              <Link
                to="/"
                className="px-2 sm:px-3.5 py-1.5 text-xs font-bold rounded-full transition-all flex items-center gap-1.5 border bg-white/20 text-white border-white"
              >
                <PlaneTakeoff className="w-3.5 h-3.5 text-[#febb02]" />
                <span>Build Package</span>
              </Link>
            </nav>
          </div>

          {/* Right: Reservation Lookup */}
          <div className="w-72 sm:w-80 md:w-96 hidden sm:block">
            <form onSubmit={handleLookupSubmit} className="relative">
              <div className="relative flex items-center">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 pointer-events-none" />
                <input
                  type="text"
                  maxLength={10}
                  value={lookupId}
                  onChange={(e) => { setLookupId(e.target.value.replace(/\D/g, '')); setLookupError(''); }}
                  placeholder="Find 10-digit Reservation ID..."
                  className="w-full pl-9 pr-24 py-1.5 text-xs bg-white text-slate-900 placeholder-slate-400 rounded border-2 border-transparent focus:border-[#febb02] focus:outline-hidden transition-all font-mono font-medium tracking-wider shadow-inner"
                />
                <button
                  type="submit"
                  className="absolute right-1 px-3 py-1 text-xs font-bold bg-[#006ce4] hover:bg-[#0057b8] text-white rounded transition-colors"
                >
                  {looking ? '…' : 'Find Trip'}
                </button>
              </div>
              {lookupError && (
                <div className="absolute top-full left-0 right-0 mt-1.5 p-2 bg-[#d4111e] text-white rounded text-[11px] font-bold shadow-lg z-50 flex items-center justify-between">
                  <span>{lookupError}</span>
                  <button type="button" onClick={() => setLookupError('')} className="text-white hover:text-slate-200 font-extrabold ml-2">×</button>
                </div>
              )}
            </form>
          </div>
        </div>

        {/* Mobile Search */}
        <div className="pb-3 sm:hidden">
          <form onSubmit={handleLookupSubmit} className="relative">
            <div className="relative flex items-center">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 pointer-events-none" />
              <input
                type="text"
                maxLength={10}
                value={lookupId}
                onChange={(e) => { setLookupId(e.target.value.replace(/\D/g, '')); setLookupError(''); }}
                placeholder="Find 10-digit Reservation ID..."
                className="w-full pl-9 pr-24 py-2 text-xs bg-white text-slate-900 rounded font-mono font-semibold"
              />
              <button type="submit" className="absolute right-1 px-3 py-1.5 text-xs font-bold bg-[#006ce4] text-white rounded">
                Find
              </button>
            </div>
            {lookupError && <p className="mt-1 text-[11px] text-[#febb02] font-semibold">{lookupError}</p>}
          </form>
        </div>
      </div>
    </header>
  );
}

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider, useApp } from './context/AppContext';
import Navbar from './components/Navbar';
import HomePage from './pages/HomePage';
import PackagePage from './pages/PackagePage';
import OutcomePage from './pages/OutcomePage';
import ComparePage from './pages/ComparePage';
import BookingsPage from './pages/BookingsPage';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';

function ToastLayer() {
  const { toastMessage } = useApp();
  if (!toastMessage) return null;
  return (
    <div className="fixed bottom-6 right-6 z-50 animate-in fade-in slide-in-from-bottom-4 duration-200">
      <div className={`px-4 py-3 rounded-lg shadow-xl border text-xs font-bold flex items-center gap-2.5 ${
        toastMessage.type === 'error'
          ? 'bg-[#d4111e] text-white border-[#b00d17]'
          : 'bg-[#003580] text-white border-[#00224f]'
      }`}>
        {toastMessage.type === 'error'
          ? <AlertTriangle className="w-4 h-4 text-white shrink-0" />
          : <CheckCircle2 className="w-4 h-4 text-[#febb02] shrink-0" />
        }
        <span>{toastMessage.text}</span>
      </div>
    </div>
  );
}

function AppShell() {
  return (
    <div className="min-h-screen bg-[#f2f6fa] flex flex-col text-slate-800">
      <Navbar />

      <main className="flex-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/packages/:id" element={<PackagePage />} />
          <Route path="/outcome" element={<OutcomePage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/bookings" element={<BookingsPage />} />
          {/* Catch-all → home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      {/* Toast notifications (global) */}
      <ToastLayer />

      {/* Footer */}
      <footer className="border-t border-slate-300 bg-white py-6 text-xs text-slate-600">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="font-black text-[#003580] text-sm">normad<span className="text-[#febb02]">.grid</span></span>
            <span>•</span>
            <span className="font-medium">International Holiday Package System</span>
          </div>
          <div className="flex items-center gap-4 text-slate-500 font-semibold">
            <span>Booking.com Theme Edition</span>
            <span>•</span>
            <span>React + Tailwind v4 • powered by the NomadGrid API</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <AppShell />
      </AppProvider>
    </BrowserRouter>
  );
}

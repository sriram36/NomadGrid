import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MyBookingsPage from '../components/MyBookingsPage';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import { toView } from '../api/adapt';

export default function BookingsPage() {
  const navigate = useNavigate();
  const { reservationNumbers, handleForgetReservation, handleResetTrip } = useApp();
  const [bookings, setBookings] = useState(null);

  // The reservations live on the server; this device only remembers their numbers.
  useEffect(() => {
    let cancelled = false;
    Promise.all(reservationNumbers.map((n) => api.reservation(n).catch(() => null))).then((results) => {
      if (cancelled) return;
      setBookings(results.filter((r) => r && r.status === 200).map((r) => toView(r.data)));
    });
    return () => { cancelled = true; };
  }, [reservationNumbers]);

  return (
    <div className="min-h-screen bg-[#f2f6fa]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {bookings === null ? (
          <div className="py-16 flex justify-center"><div className="w-10 h-10 border-4 border-[#003580] border-t-[#febb02] rounded-full animate-spin" /></div>
        ) : (
          <MyBookingsPage
            bookings={bookings}
            onSelectBooking={(b) => navigate(`/packages/${b.package_id}`)}
            onDeleteBooking={handleForgetReservation}
            onStartNewTrip={() => { handleResetTrip(); navigate('/'); }}
          />
        )}
      </div>
    </div>
  );
}

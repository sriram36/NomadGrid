import React from 'react';
import { useNavigate } from 'react-router-dom';
import MyBookingsPage from '../components/MyBookingsPage';
import { useApp } from '../context/AppContext';

export default function BookingsPage() {
  const navigate = useNavigate();
  const { bookings, setCurrentPackage, handleDeleteBooking } = useApp();

  const handleSelectBooking = (booking) => {
    setCurrentPackage(booking);
    navigate('/results');
  };

  const handleStartNewTrip = () => {
    setCurrentPackage(null);
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-[#f2f6fa]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        <MyBookingsPage
          bookings={bookings}
          onSelectBooking={handleSelectBooking}
          onDeleteBooking={handleDeleteBooking}
          onStartNewTrip={handleStartNewTrip}
        />
      </div>
    </div>
  );
}

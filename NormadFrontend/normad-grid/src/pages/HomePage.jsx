import React from 'react';
import { useNavigate } from 'react-router-dom';
import RequestForm from '../components/RequestForm';
import { useApp } from '../context/AppContext';

export default function HomePage() {
  const navigate = useNavigate();
  const { handleTripRequestSubmit, isGenerating } = useApp();

  const onSubmit = (request) => {
    handleTripRequestSubmit(request, () => {
      navigate('/results');
    });
  };

  return (
    <div className="min-h-screen bg-[#f2f6fa]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        <RequestForm onSubmit={onSubmit} isLoading={isGenerating} />
      </div>
    </div>
  );
}

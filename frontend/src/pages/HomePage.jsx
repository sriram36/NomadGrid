import { useLocation, useNavigate } from 'react-router-dom';
import RequestForm from '../components/RequestForm';
import { useApp } from '../context/AppContext';

export default function HomePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { submitTrip, isGenerating, lastRequest } = useApp();

  // "Edit the trip" brings the previous values back; a fresh visit starts with an empty form.
  const initialData = location.state?.edit ? lastRequest : null;

  const onSubmit = async (request, mode) => {
    const result = await submitTrip(request, mode);
    if (result.kind === 'PACKAGE') navigate(`/packages/${result.id}`);
    else if (result.kind === 'VARIANTS') navigate('/compare');
    else if (result.kind === 'OVER_BUDGET' || result.kind === 'NO_PACKAGE') navigate('/outcome');
    return result;
  };

  return (
    <div className="min-h-screen bg-[#f2f6fa]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        <RequestForm onSubmit={onSubmit} isLoading={isGenerating} initialData={initialData} />
      </div>
    </div>
  );
}

import React, { createContext, useContext, useState, useEffect } from 'react';
import { generatePackage, validatePackage, calculateAttractionPrice, exportPackageJSON } from '../data/mockTripData';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  // Persistent bookings from localStorage
  const [bookings, setBookings] = useState(() => {
    try {
      const saved = localStorage.getItem('normad_bookings');
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });

  // Active package & related state
  const [currentPackage, setCurrentPackage] = useState(null);
  const [lastRequest, setLastRequest] = useState(null);
  const [generationError, setGenerationError] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [overBudgetNotice, setOverBudgetNotice] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);

  // Swap modal state
  const [swapModalState, setSwapModalState] = useState({
    isOpen: false,
    modalType: null,
    targetItem: null,
    targetDate: null
  });

  // Sync bookings to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('normad_bookings', JSON.stringify(bookings));
    } catch (e) { console.error(e); }
  }, [bookings]);

  const showToast = (text, type = 'success') => {
    setToastMessage({ text, type });
    setTimeout(() => setToastMessage(null), 3500);
  };

  // M1 & M2: Handle form submit — returns true so caller can navigate
  const handleTripRequestSubmit = (request, onDone) => {
    setIsGenerating(true);
    setGenerationError(null);
    setOverBudgetNotice(null);
    setLastRequest(request);

    setTimeout(() => {
      const result = generatePackage(request);

      if (result.error) {
        setGenerationError(result.error);
        setCurrentPackage(null);
        setIsGenerating(false);
        if (onDone) onDone({ error: true });
        return;
      }

      const pkg = result.package;
      setCurrentPackage(pkg);
      setIsGenerating(false);

      if (pkg.total_inr > request.budget) {
        const excess = pkg.total_inr - request.budget;
        setOverBudgetNotice({
          totalCost: pkg.total_inr,
          budget: request.budget,
          excess,
          suggestedAddition: excess,
          reducedNights: Math.max(3, request.nights - 1)
        });
      } else {
        setOverBudgetNotice(null);
        showToast('Holiday package successfully generated and validated!');
      }

      if (onDone) onDone({ error: false });
    }, 300);
  };

  // M7: Confirm booking
  const handleConfirmBooking = () => {
    if (!currentPackage) return;
    const randomDigits = Math.floor(1000000000 + Math.random() * 9000000000).toString();
    const confirmedPackage = {
      ...currentPackage,
      status: 'BOOKED',
      booking: { reference: randomDigits },
      items: currentPackage.items.map(item => ({
        ...item,
        status: 'BOOKED',
        booking: { reference: randomDigits }
      }))
    };
    const updatedBookings = [confirmedPackage, ...bookings.filter(b => b.booking?.reference !== randomDigits)];
    setBookings(updatedBookings);
    setCurrentPackage(confirmedPackage);
    showToast(`Reservation #${randomDigits} Confirmed! Saved to My Bookings.`, 'success');
  };

  // M7: Lookup reservation by ID
  const handleLookupReservation = (reservationId) => {
    const found = bookings.find(b => b.booking?.reference === reservationId);
    if (found) {
      setCurrentPackage(found);
      setOverBudgetNotice(null);
      setGenerationError(null);
      showToast(`Loaded confirmed reservation #${reservationId}!`);
      return found;
    }
    return null;
  };

  // Reset trip builder
  const handleResetTrip = () => {
    setCurrentPackage(null);
    setOverBudgetNotice(null);
    setGenerationError(null);
  };

  // M6: Swap flight
  const handleConfirmSwapFlight = (oldFlightItem, newFlightCatalog) => {
    if (!currentPackage) return;
    const travelers = currentPackage.traveler.adults + currentPackage.traveler.children;
    const newPrice = newFlightCatalog.price_per_seat.amount * travelers;

    const updatedItems = currentPackage.items.map(item => {
      if (item.item_id === oldFlightItem.item_id) {
        return {
          ...item,
          name: `${newFlightCatalog.airline} ${newFlightCatalog.flight_number} (${newFlightCatalog.from} → ${newFlightCatalog.to})`,
          catalog_id: newFlightCatalog.flight_id,
          start: newFlightCatalog.departure_local.substring(0, 16),
          end: newFlightCatalog.arrival_local.substring(0, 16),
          price_inr: newPrice,
          details: {
            ...item.details,
            flightNumber: newFlightCatalog.flight_number,
            airline: newFlightCatalog.airline,
            from: newFlightCatalog.from,
            to: newFlightCatalog.to,
            durationMinutes: newFlightCatalog.duration_minutes,
            stops: newFlightCatalog.stops,
            pricePerSeat: newFlightCatalog.price_per_seat.amount,
            seatsLeft: newFlightCatalog.seats_left
          }
        };
      }
      return item;
    });

    const newTotal = updatedItems.reduce((sum, i) => sum + i.price_inr, 0);
    const updatedPackage = { ...currentPackage, items: updatedItems, total_inr: newTotal, total_price_inr: newTotal };
    const validation = validatePackage(updatedPackage);
    if (!validation.isValid) {
      showToast(`Rule Violation: ${validation.errors[0]}`, 'error');
      return;
    }
    setCurrentPackage(updatedPackage);
    showToast('Flight updated and schedule re-validated!');
  };

  // M6: Swap hotel
  const handleConfirmSwapHotel = (oldHotelItem, newHotelCatalog, newRoomCatalog, roomsNeeded) => {
    if (!currentPackage) return;
    const stayNights = oldHotelItem.details?.nights || 3;
    const newPrice = newRoomCatalog.price_per_night.amount * roomsNeeded * stayNights;

    const updatedItems = currentPackage.items.map(item => {
      if (item.item_id === oldHotelItem.item_id) {
        return {
          ...item,
          name: `${newHotelCatalog.name} (${newRoomCatalog.name})`,
          catalog_id: newHotelCatalog.hotel_id,
          room_id: newRoomCatalog.room_id,
          quantity: roomsNeeded,
          price_inr: newPrice,
          details: {
            ...item.details,
            hotelName: newHotelCatalog.name,
            roomType: newRoomCatalog.name,
            roomCategory: newRoomCatalog.room_type,
            area: newHotelCatalog.area,
            stars: newHotelCatalog.stars,
            rating: newHotelCatalog.rating,
            pricePerNight: newRoomCatalog.price_per_night.amount,
            roomsNeeded
          }
        };
      }
      return item;
    });

    const newTotal = updatedItems.reduce((sum, i) => sum + i.price_inr, 0);
    const updatedPackage = { ...currentPackage, items: updatedItems, total_inr: newTotal, total_price_inr: newTotal };
    const validation = validatePackage(updatedPackage);
    if (!validation.isValid) {
      showToast(`Rule Violation: ${validation.errors[0]}`, 'error');
      return;
    }
    setCurrentPackage(updatedPackage);
    showToast('Hotel accommodations updated and room capacity confirmed!');
  };

  // M6: Add attraction
  const handleConfirmAddAttraction = (attraction, dateStr, slot) => {
    if (!currentPackage) return;
    const travelers = currentPackage.traveler.adults + currentPackage.traveler.children;
    const price = calculateAttractionPrice(attraction, currentPackage.traveler.adults, currentPackage.traveler.children);

    const newItem = {
      item_id: `item-att-${Date.now().toString().slice(-4)}`,
      type: 'attraction',
      name: attraction.name,
      city: attraction.city,
      status: currentPackage.status || 'PLANNED',
      catalog_id: attraction.attraction_id,
      room_id: null,
      start: `${dateStr}T${slot.start}`,
      end: `${dateStr}T${slot.end}`,
      quantity: travelers,
      price_inr: price,
      booking: currentPackage.booking || null,
      sources: [],
      warnings: [],
      details: {
        category: attraction.category,
        openHours: `${attraction.open_from} - ${attraction.open_until}`,
        visitMinutes: attraction.visit_minutes,
        slotName: 'Added Sightseeing',
        pricePerPerson: attraction.price_per_person.amount,
        childPrice: attraction.child_price ? attraction.child_price.amount : attraction.price_per_person.amount,
        childFriendly: attraction.child_friendly
      }
    };

    const updatedItems = [...currentPackage.items, newItem];
    const newTotal = updatedItems.reduce((sum, i) => sum + i.price_inr, 0);
    const updatedPackage = { ...currentPackage, items: updatedItems, total_inr: newTotal, total_price_inr: newTotal };
    const validation = validatePackage(updatedPackage);
    if (!validation.isValid) {
      showToast(`Rule Violation: ${validation.errors[0]}`, 'error');
      return;
    }
    setCurrentPackage(updatedPackage);
    showToast(`Added "${attraction.name}" to itinerary!`);
  };

  // M6: Remove attraction
  const handleRemoveAttraction = (attractionItem) => {
    if (!currentPackage) return;
    const updatedItems = currentPackage.items.filter(i => i.item_id !== attractionItem.item_id);
    const newTotal = updatedItems.reduce((sum, i) => sum + i.price_inr, 0);
    setCurrentPackage({ ...currentPackage, items: updatedItems, total_inr: newTotal, total_price_inr: newTotal });
    showToast(`Removed "${attractionItem.name}".`);
  };

  // Delete booking
  const handleDeleteBooking = (refNumber) => {
    setBookings(prev => prev.filter(b => b.booking?.reference !== refNumber));
    if (currentPackage?.booking?.reference === refNumber) setCurrentPackage(null);
    showToast(`Deleted reservation #${refNumber}.`);
  };

  return (
    <AppContext.Provider value={{
      bookings,
      currentPackage, setCurrentPackage,
      lastRequest,
      generationError, setGenerationError,
      isGenerating,
      overBudgetNotice, setOverBudgetNotice,
      toastMessage,
      swapModalState, setSwapModalState,
      showToast,
      handleTripRequestSubmit,
      handleConfirmBooking,
      handleLookupReservation,
      handleResetTrip,
      handleConfirmSwapFlight,
      handleConfirmSwapHotel,
      handleConfirmAddAttraction,
      handleRemoveAttraction,
      handleDeleteBooking,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}

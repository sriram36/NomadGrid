import destinationsData from './catalog/destinations.json';
import airportsData from './catalog/airports.json';
import flightsData from './catalog/flights.json';
import hotelsData from './catalog/hotels.json';
import roomsData from './catalog/rooms.json';
import availabilityData from './catalog/availability.json';
import transfersData from './catalog/transfers.json';
import attractionsData from './catalog/attractions.json';

export {
  destinationsData,
  airportsData,
  flightsData,
  hotelsData,
  roomsData,
  availabilityData,
  transfersData,
  attractionsData
};

// City airport mapping
const CITY_TO_AIRPORT = {
  'Bengaluru': 'BLR',
  'Delhi': 'DEL',
  'Mumbai': 'BOM',
  'Chennai': 'MAA',
  'Hyderabad': 'HYD'
};

const DAY_NAMES = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];

// Format currency in Indian Rupees
export function formatINR(amount) {
  if (amount === undefined || amount === null || isNaN(amount)) return '₹0';
  return '₹' + Math.round(amount).toLocaleString('en-IN');
}

// Helper to add days to a date string YYYY-MM-DD
export function addDays(dateStr, days) {
  const [y, m, d] = dateStr.split('-').map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().split('T')[0];
}

// Difference in days between two YYYY-MM-DD
export function daysBetween(dateStr1, dateStr2) {
  const d1 = new Date(dateStr1);
  const d2 = new Date(dateStr2);
  const diffTime = Math.abs(d2 - d1);
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

// Parse HH:MM to minutes from midnight
export function timeToMinutes(timeStr) {
  if (!timeStr) return 0;
  const [h, m] = timeStr.split(':').map(Number);
  return h * 60 + (m || 0);
}

// Format minutes from midnight to HH:MM
export function minutesToTime(mins) {
  const normalized = (mins % (24 * 60) + (24 * 60)) % (24 * 60);
  const h = Math.floor(normalized / 60);
  const m = normalized % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

// Add minutes to an ISO datetime string
export function addMinutesToIso(isoStr, minutes) {
  const date = new Date(isoStr);
  date.setMinutes(date.getMinutes() + minutes);
  const y = date.getFullYear();
  const mo = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  const h = String(date.getHours()).padStart(2, '0');
  const mi = String(date.getMinutes()).padStart(2, '0');
  return `${y}-${mo}-${d}T${h}:${mi}`;
}

// Check if a time falls within window HH:MM - HH:MM
export function isTimeInWindow(timeStr, windowStart, windowEnd) {
  const t = timeToMinutes(timeStr);
  const start = timeToMinutes(windowStart);
  let end = timeToMinutes(windowEnd);
  if (end === 0) end = 24 * 60; // 24:00 or 00:00 midnight
  if (end < start) {
    // Window crosses midnight (e.g., 06:00 to 00:30)
    return t >= start || t <= end;
  }
  return t >= start && t <= end;
}

// Get weekday code (MON..SUN) for a date YYYY-MM-DD
export function getWeekdayCode(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  return DAY_NAMES[date.getUTCDay()];
}

// Helper: Calculate transfer price
export function calculateTransferPrice(transfer, adults, childrenCount) {
  const travelers = adults + childrenCount;
  if (transfer.pricing === 'PER_PERSON') {
    const adultPrice = transfer.price.amount;
    const childPrice = transfer.child_price ? transfer.child_price.amount : adultPrice;
    return adults * adultPrice + childrenCount * childPrice;
  } else {
    // PER_VEHICLE
    const maxPass = transfer.max_passengers || 4;
    const vehicles = Math.ceil(travelers / maxPass);
    return vehicles * transfer.price.amount;
  }
}

// Helper: Calculate attraction price
export function calculateAttractionPrice(attraction, adults, childrenCount) {
  const adultPrice = attraction.price_per_person.amount;
  const childPrice = attraction.child_price ? attraction.child_price.amount : adultPrice;
  return adults * adultPrice + childrenCount * childPrice;
}

// Check room fit rule for travelers
export function checkRoomFit(room, adults, childrenCount) {
  const totalTravelers = adults + childrenCount;
  for (let k = 1; k <= 5; k++) {
    const adultsFit = adults <= k * room.max_adults;
    const totalFit = totalTravelers <= k * (room.max_adults + room.max_children);
    const adultsMin = adults >= k;
    if (adultsFit && totalFit && adultsMin) {
      return { fits: true, roomsNeeded: k };
    }
  }
  return { fits: false, roomsNeeded: 0 };
}

// Check if room has availability for all nights
export function checkRoomAvailability(roomId, startDate, nights, roomsNeeded) {
  for (let i = 0; i < nights; i++) {
    const date = addDays(startDate, i);
    const record = availabilityData.find(a => a.room_id === roomId && a.date === date);
    if (!record || record.rooms_left < roomsNeeded) {
      return false;
    }
  }
  return true;
}

// Select city plan for nights
export function getCityPlan(country, nights) {
  if (country === 'Japan') {
    if (nights === 3) return [{ city: 'Tokyo', nights: 3 }];
    if (nights === 4) return [{ city: 'Tokyo', nights: 2 }, { city: 'Kyoto', nights: 2 }];
    if (nights === 5) return [{ city: 'Tokyo', nights: 3 }, { city: 'Kyoto', nights: 2 }];
    if (nights === 6) return [{ city: 'Tokyo', nights: 3 }, { city: 'Kyoto', nights: 3 }];
    if (nights === 7) return [{ city: 'Tokyo', nights: 4 }, { city: 'Kyoto', nights: 3 }];
    if (nights === 8) return [{ city: 'Tokyo', nights: 3 }, { city: 'Kyoto', nights: 3 }, { city: 'Osaka', nights: 2 }];
    if (nights === 9) return [{ city: 'Tokyo', nights: 4 }, { city: 'Kyoto', nights: 3 }, { city: 'Osaka', nights: 2 }];
    if (nights >= 10) return [{ city: 'Tokyo', nights: 4 }, { city: 'Kyoto', nights: 3 }, { city: 'Osaka', nights: 3 }];
  } else if (country === 'United Arab Emirates') {
    if (nights === 3) return [{ city: 'Dubai', nights: 3 }];
    if (nights === 4) return [{ city: 'Dubai', nights: 2 }, { city: 'Abu Dhabi', nights: 2 }];
    if (nights === 5) return [{ city: 'Dubai', nights: 3 }, { city: 'Abu Dhabi', nights: 2 }];
    if (nights === 6) return [{ city: 'Dubai', nights: 3 }, { city: 'Abu Dhabi', nights: 3 }];
    if (nights === 7) return [{ city: 'Dubai', nights: 4 }, { city: 'Abu Dhabi', nights: 3 }];
    if (nights === 8) return [{ city: 'Dubai', nights: 4 }, { city: 'Abu Dhabi', nights: 4 }];
    if (nights === 9) return [{ city: 'Dubai', nights: 5 }, { city: 'Abu Dhabi', nights: 4 }];
    if (nights >= 10) return [{ city: 'Dubai', nights: 5 }, { city: 'Abu Dhabi', nights: 5 }];
  }
  return null;
}

// Generate complete package
export function generatePackage(request) {
  const {
    departureCity,
    destinationCountry,
    startDate,
    nights,
    adults = 2,
    children = [],
    budget = 350000
  } = request;

  const numNights = parseInt(nights, 10);
  const numAdults = parseInt(adults, 10);
  const childrenAges = Array.isArray(children) ? children.map(Number) : [];
  const numChildren = childrenAges.length;
  const travelers = numAdults + numChildren;
  const numBudget = Number(budget);

  // M1 & M2 Validation
  if (!departureCity) return { error: 'Please select a departure city.' };
  if (!destinationCountry) return { error: 'Please select a destination country.' };
  if (!startDate) return { error: 'Please select a holiday start date.' };

  const depAirport = CITY_TO_AIRPORT[departureCity];
  if (!depAirport) {
    return {
      error: `No airport mapping found for ${departureCity}. Available cities: Bengaluru, Delhi, Mumbai, Chennai.`
    };
  }

  // Check Hyderabad specifically
  if (depAirport === 'HYD') {
    return {
      error: `No direct or connecting international flights operate from Hyderabad (HYD) in the catalog. Please select Bengaluru (BLR), Mumbai (BOM), Delhi (DEL), or Chennai (MAA).`
    };
  }

  // Validate dates
  if (numNights < 3 || numNights > 10) {
    return {
      error: `Holiday duration must be between 3 and 10 nights. You specified ${numNights} nights.`
    };
  }

  const endDate = addDays(startDate, numNights);
  if (startDate < '2027-04-01' || endDate > '2027-04-20') {
    return {
      error: `The holiday package must operate within the travel window of 1 April 2027 to 20 April 2027. Your selected dates (${startDate} to ${endDate}) exceed the 20 April 2027 return cutoff.`
    };
  }

  // Get city plan
  const cityPlan = getCityPlan(destinationCountry, numNights);
  if (!cityPlan || cityPlan.length === 0) {
    return { error: `Could not determine a valid multi-city plan for ${destinationCountry} with ${numNights} nights.` };
  }

  const firstCity = cityPlan[0].city;
  const lastCity = cityPlan[cityPlan.length - 1].city;

  // 1. Find Arrival Flight
  // Airport serving first city
  const countryObj = destinationsData.countries.find(c => c.name === destinationCountry);
  const firstCityObj = countryObj.cities.find(c => c.name === firstCity);
  const validArrivalAirports = firstCityObj.airports;

  const candidateArrivalFlights = flightsData.filter(f =>
    f.from === depAirport &&
    validArrivalAirports.includes(f.to) &&
    f.arrival_local.startsWith(startDate) &&
    f.seats_left >= travelers
  ).sort((a, b) => a.price_per_seat.amount - b.price_per_seat.amount);

  if (candidateArrivalFlights.length === 0) {
    return {
      error: `No arrival flights found from ${departureCity} (${depAirport}) to ${firstCity} on ${startDate} with at least ${travelers} seats available.`
    };
  }
  const arrivalFlight = candidateArrivalFlights[0];

  // 2. Find Return Flight
  const lastCityObj = countryObj.cities.find(c => c.name === lastCity);
  const validDepartureAirports = lastCityObj.airports;

  const candidateReturnFlights = flightsData.filter(f =>
    validDepartureAirports.includes(f.from) &&
    f.to === depAirport &&
    f.departure_local.startsWith(endDate) &&
    f.seats_left >= travelers
  ).sort((a, b) => a.price_per_seat.amount - b.price_per_seat.amount);

  if (candidateReturnFlights.length === 0) {
    return {
      error: `No return flights found from ${lastCity} to ${departureCity} (${depAirport}) on ${endDate} with at least ${travelers} seats available.`
    };
  }
  const returnFlight = candidateReturnFlights[0];

  // 3. Select Hotels & Rooms for each city
  const cityStays = [];
  let currentDayOffset = 0;

  for (const plan of cityPlan) {
    const city = plan.city;
    const nightsInCity = plan.nights;
    const checkInDate = addDays(startDate, currentDayOffset);
    const checkOutDate = addDays(checkInDate, nightsInCity);

    // Find hotels in this city
    const cityHotels = hotelsData.filter(h => h.city === city);
    let chosenHotel = null;
    let chosenRoom = null;
    let chosenRoomsNeeded = 0;

    // Sort hotels by rating or price
    cityHotels.sort((a, b) => b.stars - a.stars || b.rating - a.rating);

    for (const hotel of cityHotels) {
      const hRooms = roomsData.filter(r => r.hotel_id === hotel.hotel_id);
      for (const room of hRooms) {
        const { fits, roomsNeeded } = checkRoomFit(room, numAdults, numChildren);
        if (fits) {
          const isAvail = checkRoomAvailability(room.room_id, checkInDate, nightsInCity, roomsNeeded);
          if (isAvail) {
            chosenHotel = hotel;
            chosenRoom = room;
            chosenRoomsNeeded = roomsNeeded;
            break;
          }
        }
      }
      if (chosenHotel) break;
    }

    if (!chosenHotel) {
      return {
        error: `No hotels in ${city} have available rooms that fit ${travelers} travelers from ${checkInDate} to ${checkOutDate}.`
      };
    }

    cityStays.push({
      city,
      nights: nightsInCity,
      checkInDate,
      checkOutDate,
      hotel: chosenHotel,
      room: chosenRoom,
      roomsNeeded: chosenRoomsNeeded
    });

    currentDayOffset += nightsInCity;
  }

  // 4. Ground Transfers
  // 4a. Arrival Transfer
  const firstHotel = cityStays[0].hotel;
  const arrivalAirport = arrivalFlight.to;
  const landingTimeStr = arrivalFlight.arrival_local.substring(11, 16); // HH:MM
  const landingMins = timeToMinutes(landingTimeStr);
  const minPickupMins = landingMins + 60; // Pickup at least 60m after landing
  const pickupTimeStr = minutesToTime(minPickupMins);

  const candidateArrTransfers = transfersData.filter(t =>
    t.airport === arrivalAirport &&
    t.city === firstCity &&
    (t.area === null || t.area === firstHotel.area)
  );

  let chosenArrTransfer = null;
  for (const t of candidateArrTransfers) {
    if (isTimeInWindow(pickupTimeStr, t.service_from, t.service_until)) {
      chosenArrTransfer = t;
      break;
    }
  }

  if (!chosenArrTransfer && candidateArrTransfers.length > 0) {
    chosenArrTransfer = candidateArrTransfers[0];
  }

  if (!chosenArrTransfer) {
    return {
      error: `No airport transfer found from ${arrivalAirport} to ${firstCity} (${firstHotel.area}) within operating hours.`
    };
  }

  // 4b. Departure Transfer
  const lastStay = cityStays[cityStays.length - 1];
  const lastHotel = lastStay.hotel;
  const returnAirport = returnFlight.from;
  const returnDepTimeStr = returnFlight.departure_local.substring(11, 16);
  const returnDepMins = timeToMinutes(returnDepTimeStr);

  const candidateDepTransfers = transfersData.filter(t =>
    t.airport === returnAirport &&
    t.city === lastCity &&
    (t.area === null || t.area === lastHotel.area)
  );

  let chosenDepTransfer = null;
  let departureLeaveMins = 0;

  for (const t of candidateDepTransfers) {
    // Dropoff at airport at least 180 min before return flight
    const requiredDropoffMins = returnDepMins - 180;
    const leaveHotelMins = requiredDropoffMins - t.duration_minutes;
    const leaveTimeStr = minutesToTime(leaveHotelMins);
    if (isTimeInWindow(leaveTimeStr, t.service_from, t.service_until)) {
      chosenDepTransfer = t;
      departureLeaveMins = leaveHotelMins;
      break;
    }
  }

  if (!chosenDepTransfer && candidateDepTransfers.length > 0) {
    chosenDepTransfer = candidateDepTransfers[0];
    departureLeaveMins = returnDepMins - 180 - chosenDepTransfer.duration_minutes;
  }

  if (!chosenDepTransfer) {
    return {
      error: `No airport transfer found from ${lastCity} (${lastHotel.area}) to ${returnAirport} within operating hours.`
    };
  }

  // 4c. Intercity Transfers
  const intercityTransfers = [];
  for (let i = 0; i < cityStays.length - 1; i++) {
    const fromC = cityStays[i].city;
    const toC = cityStays[i + 1].city;
    const moveDate = cityStays[i + 1].checkInDate;

    // Find link
    const link = countryObj.links.find(l => l.from_city === fromC && l.to_city === toC);
    if (!link || !link.transfer_ids || link.transfer_ids.length === 0) {
      return { error: `No transfer connection found between ${fromC} and ${toC}.` };
    }

    const tId = link.transfer_ids[0];
    const transObj = transfersData.find(t => t.transfer_id === tId);
    if (!transObj) {
      return { error: `Transfer ID ${tId} for ${fromC} to ${toC} not found in catalog.` };
    }

    // Schedule around 11:30 or 12:00
    const departureTime = '11:30';
    const departureMins = timeToMinutes(departureTime);
    const arrivalMins = departureMins + transObj.duration_minutes;
    const arrivalTime = minutesToTime(arrivalMins);

    intercityTransfers.push({
      date: moveDate,
      fromCity: fromC,
      toCity: toC,
      transfer: transObj,
      departureTime,
      arrivalTime
    });
  }

  // 5. Attractions
  const chosenAttractionIds = new Set();
  const dayAttractionsMap = {}; // key: date YYYY-MM-DD -> array of attraction items

  // Populate attractions for each day
  for (let d = 0; d < numNights; d++) {
    const date = addDays(startDate, d);
    const weekday = getWeekdayCode(date);
    // Find city for this date
    let currentCityStay = cityStays[0];
    for (const stay of cityStays) {
      if (date >= stay.checkInDate && date < stay.checkOutDate) {
        currentCityStay = stay;
        break;
      }
    }
    const currentCity = currentCityStay.city;
    const isArrivalDay = d === 0;
    const isCityChangeDay = cityStays.some(s => s.checkInDate === date && s !== cityStays[0]);

    // Available attractions in this city
    const candidates = attractionsData.filter(a =>
      a.city === currentCity &&
      !chosenAttractionIds.has(a.attraction_id) &&
      a.open_days.includes(weekday) &&
      (!a.closed_dates || !a.closed_dates.includes(date))
    );

    const scheduledToday = [];

    if (isArrivalDay) {
      // Optional 1 attraction late afternoon (e.g. 16:30 or 17:00)
      const slotStart = '16:30';
      const slotStartMins = timeToMinutes(slotStart);
      for (const att of candidates) {
        const slotEndMins = slotStartMins + att.visit_minutes;
        const slotEnd = minutesToTime(slotEndMins);
        if (isTimeInWindow(slotStart, att.open_from, att.open_until) &&
            timeToMinutes(slotEnd) <= timeToMinutes(att.open_until)) {
          scheduledToday.push({
            attraction: att,
            start: `${date}T${slotStart}`,
            end: `${date}T${slotEnd}`,
            slot: 'Late Afternoon'
          });
          chosenAttractionIds.add(att.attraction_id);
          break;
        }
      }
    } else if (isCityChangeDay) {
      // 1 attraction in afternoon after arriving in new city (e.g. 15:30)
      const slotStart = '15:30';
      const slotStartMins = timeToMinutes(slotStart);
      for (const att of candidates) {
        const slotEndMins = slotStartMins + att.visit_minutes;
        const slotEnd = minutesToTime(slotEndMins);
        if (isTimeInWindow(slotStart, att.open_from, att.open_until) &&
            timeToMinutes(slotEnd) <= timeToMinutes(att.open_until)) {
          scheduledToday.push({
            attraction: att,
            start: `${date}T${slotStart}`,
            end: `${date}T${slotEnd}`,
            slot: 'Afternoon Discovery'
          });
          chosenAttractionIds.add(att.attraction_id);
          break;
        }
      }
    } else {
      // Full day: schedule 1 to 2 attractions
      // Slot 1: Morning (10:00)
      let slot1EndMins = 0;
      for (const att of candidates) {
        const startMins = 10 * 60;
        const endMins = startMins + att.visit_minutes;
        if (isTimeInWindow('10:00', att.open_from, att.open_until) &&
            endMins <= timeToMinutes(att.open_until)) {
          scheduledToday.push({
            attraction: att,
            start: `${date}T10:00`,
            end: `${date}T${minutesToTime(endMins)}`,
            slot: 'Morning Highlight'
          });
          chosenAttractionIds.add(att.attraction_id);
          slot1EndMins = endMins;
          break;
        }
      }

      // Slot 2: Afternoon (after slot 1 + 90 min lunch break, min 14:00)
      const afternoonStartMins = Math.max(14 * 60, slot1EndMins + 60);
      const remainingCandidates = candidates.filter(a => !chosenAttractionIds.has(a.attraction_id));
      for (const att of remainingCandidates) {
        const endMins = afternoonStartMins + att.visit_minutes;
        const startTimeStr = minutesToTime(afternoonStartMins);
        const endTimeStr = minutesToTime(endMins);
        if (isTimeInWindow(startTimeStr, att.open_from, att.open_until) &&
            endMins <= timeToMinutes(att.open_until)) {
          scheduledToday.push({
            attraction: att,
            start: `${date}T${startTimeStr}`,
            end: `${date}T${endTimeStr}`,
            slot: 'Afternoon Exploration'
          });
          chosenAttractionIds.add(att.attraction_id);
          break;
        }
      }
    }

    dayAttractionsMap[date] = scheduledToday;
  }

  // 6. Build Items List (conforming to DATA_DICTIONARY.md)
  let itemIdCounter = 1;
  const items = [];

  // Item: Arrival Flight
  const arrFlightPrice = arrivalFlight.price_per_seat.amount * travelers;
  items.push({
    item_id: `item-${itemIdCounter++}`,
    type: 'flight',
    name: `${arrivalFlight.airline} ${arrivalFlight.flight_number} (${arrivalFlight.from} → ${arrivalFlight.to})`,
    city: firstCity,
    status: 'PLANNED',
    catalog_id: arrivalFlight.flight_id,
    room_id: null,
    start: arrivalFlight.departure_local.substring(0, 16),
    end: arrivalFlight.arrival_local.substring(0, 16),
    quantity: travelers,
    price_inr: arrFlightPrice,
    booking: null,
    sources: [],
    warnings: [],
    details: {
      flightNumber: arrivalFlight.flight_number,
      airline: arrivalFlight.airline,
      from: arrivalFlight.from,
      to: arrivalFlight.to,
      durationMinutes: arrivalFlight.duration_minutes,
      stops: arrivalFlight.stops,
      pricePerSeat: arrivalFlight.price_per_seat.amount,
      seatsLeft: arrivalFlight.seats_left,
      isArrival: true
    }
  });

  // Item: Arrival Airport Transfer
  const arrPickupDateTime = `${startDate}T${pickupTimeStr}`;
  const arrTransferEndDateTime = addMinutesToIso(arrPickupDateTime, chosenArrTransfer.duration_minutes);
  const arrTransferPrice = calculateTransferPrice(chosenArrTransfer, numAdults, numChildren);
  items.push({
    item_id: `item-${itemIdCounter++}`,
    type: 'transfer',
    name: `${chosenArrTransfer.name} (${chosenArrTransfer.airport} → ${firstCity})`,
    city: firstCity,
    status: 'PLANNED',
    catalog_id: chosenArrTransfer.transfer_id,
    room_id: null,
    start: arrPickupDateTime,
    end: arrTransferEndDateTime,
    quantity: chosenArrTransfer.pricing === 'PER_PERSON' ? travelers : Math.ceil(travelers / (chosenArrTransfer.max_passengers || 4)),
    price_inr: arrTransferPrice,
    booking: null,
    sources: [],
    warnings: [],
    details: {
      transferType: chosenArrTransfer.type,
      fromPoint: chosenArrTransfer.from_point,
      toPoint: chosenArrTransfer.to_point,
      durationMinutes: chosenArrTransfer.duration_minutes,
      pricing: chosenArrTransfer.pricing,
      unitPrice: chosenArrTransfer.price.amount,
      serviceHours: `${chosenArrTransfer.service_from} - ${chosenArrTransfer.service_until}`,
      isAirportTransfer: true
    }
  });

  // Items: Hotels & Intercity Transfers & Attractions
  cityStays.forEach((stay, idx) => {
    // Hotel item
    const hotelPrice = stay.room.price_per_night.amount * stay.roomsNeeded * stay.nights;
    items.push({
      item_id: `item-${itemIdCounter++}`,
      type: 'hotel',
      name: `${stay.hotel.name} (${stay.room.name})`,
      city: stay.city,
      status: 'PLANNED',
      catalog_id: stay.hotel.hotel_id,
      room_id: stay.room.room_id,
      start: stay.checkInDate,
      end: stay.checkOutDate,
      quantity: stay.roomsNeeded,
      price_inr: hotelPrice,
      booking: null,
      sources: [],
      warnings: [],
      details: {
        hotelName: stay.hotel.name,
        roomType: stay.room.name,
        roomCategory: stay.room.room_type,
        area: stay.hotel.area,
        stars: stay.hotel.stars,
        rating: stay.hotel.rating,
        nights: stay.nights,
        pricePerNight: stay.room.price_per_night.amount,
        roomsNeeded: stay.roomsNeeded,
        checkInFrom: stay.hotel.check_in_from,
        checkOutUntil: stay.hotel.check_out_until,
        familyFriendly: stay.hotel.family_friendly
      }
    });

    // Intercity transfer to next city (if not last stay)
    if (idx < cityStays.length - 1) {
      const transObj = intercityTransfers[idx];
      const transPrice = calculateTransferPrice(transObj.transfer, numAdults, numChildren);
      const startIso = `${transObj.date}T${transObj.departureTime}`;
      const endIso = `${transObj.date}T${transObj.arrivalTime}`;
      items.push({
        item_id: `item-${itemIdCounter++}`,
        type: 'transfer',
        name: `${transObj.transfer.name} (${transObj.fromCity} → ${transObj.toCity})`,
        city: transObj.toCity,
        status: 'PLANNED',
        catalog_id: transObj.transfer.transfer_id,
        room_id: null,
        start: startIso,
        end: endIso,
        quantity: transObj.transfer.pricing === 'PER_PERSON' ? travelers : Math.ceil(travelers / (transObj.transfer.max_passengers || 4)),
        price_inr: transPrice,
        booking: null,
        sources: [],
        warnings: [],
        details: {
          transferType: transObj.transfer.type,
          fromCity: transObj.fromCity,
          toCity: transObj.toCity,
          fromPoint: transObj.transfer.from_point,
          toPoint: transObj.transfer.to_point,
          durationMinutes: transObj.transfer.duration_minutes,
          pricing: transObj.transfer.pricing,
          unitPrice: transObj.transfer.price.amount,
          isIntercity: true
        }
      });
    }
  });

  // Attraction items
  Object.keys(dayAttractionsMap).forEach(date => {
    const list = dayAttractionsMap[date] || [];
    list.forEach(item => {
      const att = item.attraction;
      const attPrice = calculateAttractionPrice(att, numAdults, numChildren);
      items.push({
        item_id: `item-${itemIdCounter++}`,
        type: 'attraction',
        name: att.name,
        city: att.city,
        status: 'PLANNED',
        catalog_id: att.attraction_id,
        room_id: null,
        start: item.start,
        end: item.end,
        quantity: travelers,
        price_inr: attPrice,
        booking: null,
        sources: [],
        warnings: [],
        details: {
          category: att.category,
          openHours: `${att.open_from} - ${att.open_until}`,
          visitMinutes: att.visit_minutes,
          slotName: item.slot,
          pricePerPerson: att.price_per_person.amount,
          childPrice: att.child_price ? att.child_price.amount : att.price_per_person.amount,
          childFriendly: att.child_friendly
        }
      });
    });
  });

  // Item: Departure Airport Transfer
  const depPickupTimeStr = minutesToTime(departureLeaveMins);
  const depPickupDateTime = `${endDate}T${depPickupTimeStr}`;
  const depTransferEndDateTime = addMinutesToIso(depPickupDateTime, chosenDepTransfer.duration_minutes);
  const depTransferPrice = calculateTransferPrice(chosenDepTransfer, numAdults, numChildren);
  items.push({
    item_id: `item-${itemIdCounter++}`,
    type: 'transfer',
    name: `${chosenDepTransfer.name} (${lastCity} → ${chosenDepTransfer.airport})`,
    city: lastCity,
    status: 'PLANNED',
    catalog_id: chosenDepTransfer.transfer_id,
    room_id: null,
    start: depPickupDateTime,
    end: depTransferEndDateTime,
    quantity: chosenDepTransfer.pricing === 'PER_PERSON' ? travelers : Math.ceil(travelers / (chosenDepTransfer.max_passengers || 4)),
    price_inr: depTransferPrice,
    booking: null,
    sources: [],
    warnings: [],
    details: {
      transferType: chosenDepTransfer.type,
      fromPoint: chosenDepTransfer.from_point,
      toPoint: chosenDepTransfer.to_point,
      durationMinutes: chosenDepTransfer.duration_minutes,
      pricing: chosenDepTransfer.pricing,
      unitPrice: chosenDepTransfer.price.amount,
      serviceHours: `${chosenDepTransfer.service_from} - ${chosenDepTransfer.service_until}`,
      isAirportTransfer: true
    }
  });

  // Item: Return Flight
  const retFlightPrice = returnFlight.price_per_seat.amount * travelers;
  items.push({
    item_id: `item-${itemIdCounter++}`,
    type: 'flight',
    name: `${returnFlight.airline} ${returnFlight.flight_number} (${returnFlight.from} → ${returnFlight.to})`,
    city: lastCity,
    status: 'PLANNED',
    catalog_id: returnFlight.flight_id,
    room_id: null,
    start: returnFlight.departure_local.substring(0, 16),
    end: returnFlight.arrival_local.substring(0, 16),
    quantity: travelers,
    price_inr: retFlightPrice,
    booking: null,
    sources: [],
    warnings: [],
    details: {
      flightNumber: returnFlight.flight_number,
      airline: returnFlight.airline,
      from: returnFlight.from,
      to: returnFlight.to,
      durationMinutes: returnFlight.duration_minutes,
      stops: returnFlight.stops,
      pricePerSeat: returnFlight.price_per_seat.amount,
      seatsLeft: returnFlight.seats_left,
      isReturn: true
    }
  });

  // Calculate totals
  const totalInr = items.reduce((sum, item) => sum + item.price_inr, 0);

  // Generate trip object
  const tripId = `trip-${Date.now().toString().slice(-6)}`;
  const tripPackage = {
    trip_id: tripId,
    country: destinationCountry,
    status: 'PLANNED',
    booking: null,
    traveler: {
      name: `${departureCity} Traveler`,
      home_airport: depAirport,
      departure_city: departureCity,
      adults: numAdults,
      children: numChildren,
      child_ages: childrenAges
    },
    start_date: startDate,
    end_date: endDate,
    nights: numNights,
    budget_inr: numBudget,
    total_inr: totalInr,
    total_price_inr: totalInr,
    cityPlan,
    items
  };

  return { package: tripPackage, error: null };
}

// Full package validation against Section 4 travel rules
export function validatePackage(tripPackage) {
  const errors = [];
  const warnings = [];

  if (!tripPackage || !tripPackage.items || tripPackage.items.length === 0) {
    return { isValid: false, errors: ['Package has no items.'], warnings: [] };
  }

  const { start_date, end_date, traveler, items, country } = tripPackage;
  const travelersCount = traveler.adults + traveler.children;

  // Rule 1: Dates & Window
  if (start_date < '2027-04-01') errors.push('First night must be on or after 1 April 2027.');
  if (end_date > '2027-04-20') errors.push('Return flight must be on or before 20 April 2027.');

  const nights = daysBetween(start_date, end_date);
  if (nights < 3 || nights > 10) errors.push(`Trip duration must be between 3 and 10 nights (currently ${nights} nights).`);

  // Rule 2: Flights
  const flights = items.filter(i => i.type === 'flight');
  if (flights.length < 2) {
    errors.push('Package must contain exactly one arrival flight and one return flight.');
  } else {
    const arrFlight = flights[0];
    const retFlight = flights[flights.length - 1];

    if (!arrFlight.start || !arrFlight.end) errors.push('Arrival flight missing departure or arrival time.');
    if (!retFlight.start || !retFlight.end) errors.push('Return flight missing departure or arrival time.');

    // Seats check
    const arrCat = flightsData.find(f => f.flight_id === arrFlight.catalog_id);
    if (arrCat && arrCat.seats_left < travelersCount) {
      errors.push(`Arrival flight ${arrCat.flight_number} has only ${arrCat.seats_left} seats (needs ${travelersCount}).`);
    }

    const retCat = flightsData.find(f => f.flight_id === retFlight.catalog_id);
    if (retCat && retCat.seats_left < travelersCount) {
      errors.push(`Return flight ${retCat.flight_number} has only ${retCat.seats_left} seats (needs ${travelersCount}).`);
    }
  }

  // Rule 3: Hotels & Cities
  const hotels = items.filter(i => i.type === 'hotel');
  if (hotels.length === 0) {
    errors.push('Package must contain hotel accommodations.');
  } else {
    // Check minimum 2 nights per city
    hotels.forEach(h => {
      const stayNights = daysBetween(h.start, h.end);
      if (stayNights < 2 && hotels.length > 1) {
        errors.push(`City stay in ${h.city} is only ${stayNights} nights. Rule requires at least 2 nights per city.`);
      }

      // Check room fit
      const room = roomsData.find(r => r.room_id === h.room_id);
      if (room) {
        const { fits, roomsNeeded } = checkRoomFit(room, traveler.adults, traveler.children);
        if (!fits || h.quantity < roomsNeeded) {
          errors.push(`Room type ${room.name} does not satisfy capacity for ${travelersCount} travelers with ${h.quantity} rooms.`);
        }
      }
    });
  }

  // Rule 4: Airport Transfers Buffer Times
  const transfers = items.filter(i => i.type === 'transfer');
  const arrFlight = flights[0];
  const retFlight = flights[flights.length - 1];

  if (arrFlight && transfers.length > 0) {
    const arrTransfer = transfers[0];
    if (arrTransfer.details?.isAirportTransfer) {
      const landingMins = timeToMinutes(arrFlight.end.substring(11, 16));
      const pickupMins = timeToMinutes(arrTransfer.start.substring(11, 16));
      if (pickupMins < landingMins + 60) {
        errors.push(`Arrival airport transfer pickup (${pickupMins - landingMins}m after landing) violates the mandatory 60-minute post-landing buffer.`);
      }
    }
  }

  if (retFlight && transfers.length > 0) {
    const retTransfer = transfers[transfers.length - 1];
    if (retTransfer.details?.isAirportTransfer) {
      const depFlightMins = timeToMinutes(retFlight.start.substring(11, 16));
      const dropoffMins = timeToMinutes(retTransfer.end.substring(11, 16));
      if (depFlightMins - dropoffMins < 180) {
        errors.push(`Return airport transfer arrival (${depFlightMins - dropoffMins}m before flight) violates the mandatory 180-minute pre-departure check-in buffer.`);
      }
    }
  }

  // Rule 5: Attractions
  const attractions = items.filter(i => i.type === 'attraction');
  const seenAttractions = new Set();
  const dayAttractions = {};

  attractions.forEach(att => {
    // Unique check
    if (seenAttractions.has(att.catalog_id)) {
      errors.push(`Attraction ${att.name} appears more than once in the package.`);
    }
    seenAttractions.add(att.catalog_id);

    // No attractions on last day
    const attDate = att.start.substring(0, 10);
    if (attDate === end_date) {
      errors.push(`Attraction ${att.name} is scheduled on the departure day (${end_date}). No attractions allowed on the last day.`);
    }

    if (!dayAttractions[attDate]) dayAttractions[attDate] = [];
    dayAttractions[attDate].push(att);
  });

  // Check overlaps on the same day
  Object.keys(dayAttractions).forEach(date => {
    const dayList = dayAttractions[date];
    for (let i = 0; i < dayList.length; i++) {
      for (let j = i + 1; j < dayList.length; j++) {
        const a1 = dayList[i];
        const a2 = dayList[j];
        const a1Start = a1.start.substring(11, 16);
        const a1End = a1.end.substring(11, 16);
        const a2Start = a2.start.substring(11, 16);
        const a2End = a2.end.substring(11, 16);

        if (a1Start < a2End && a2Start < a1End) {
          errors.push(`Sightseeing schedule conflict on ${date}: "${a1.name}" (${a1Start}-${a1End}) overlaps with "${a2.name}" (${a2Start}-${a2End}).`);
        }
      }
    }
  });

  return {
    isValid: errors.length === 0,
    errors,
    warnings
  };
}

// Find cheapest possible valid package for budget feedback (M8)
export function findCheapestPackage(request) {
  // Try generating a package with cheapest choices
  const result = generatePackage(request);
  if (result.error) return null;
  return result.package;
}

// Get alternative flights for swapping (M6)
export function getAlternativeFlights(currentFlightItem, tripPackage) {
  const isArrival = currentFlightItem.details?.isArrival;
  const depCity = tripPackage.traveler.departure_city || 'Bengaluru';
  const depAirport = CITY_TO_AIRPORT[depCity];
  const travelers = tripPackage.traveler.adults + tripPackage.traveler.children;

  if (isArrival) {
    const startDate = tripPackage.start_date;
    const firstCity = tripPackage.cityPlan[0].city;
    const countryObj = destinationsData.countries.find(c => c.name === tripPackage.country);
    const validAirports = countryObj.cities.find(c => c.name === firstCity).airports;

    return flightsData
      .filter(f =>
        f.from === depAirport &&
        validAirports.includes(f.to) &&
        f.arrival_local.startsWith(startDate) &&
        f.flight_id !== currentFlightItem.catalog_id
      )
      .map(f => {
        const landingMins = timeToMinutes(f.arrival_local.substring(11, 16));
        const pricePerSeat = f.price_per_seat.amount;
        const totalPrice = pricePerSeat * travelers;
        const diff = totalPrice - currentFlightItem.price_inr;
        const hasEnoughSeats = f.seats_left >= travelers;

        // Check if landing time conflicts with arrival transfer buffer
        const meetsBuffer = landingMins <= (22 * 60); // Must land before transfer curfew

        return {
          flight: f,
          totalPrice,
          priceDiff: diff,
          hasEnoughSeats,
          meetsBuffer,
          canSwap: hasEnoughSeats && meetsBuffer,
          conflictReason: !hasEnoughSeats
            ? `Only ${f.seats_left} seats left (requires ${travelers})`
            : !meetsBuffer
            ? `Landing time ${f.arrival_local.substring(11, 16)} leaves insufficient buffer for hotel transfer`
            : null
        };
      });
  } else {
    // Return flight
    const endDate = tripPackage.end_date;
    const lastCity = tripPackage.cityPlan[tripPackage.cityPlan.length - 1].city;
    const countryObj = destinationsData.countries.find(c => c.name === tripPackage.country);
    const validAirports = countryObj.cities.find(c => c.name === lastCity).airports;

    return flightsData
      .filter(f =>
        validAirports.includes(f.from) &&
        f.to === depAirport &&
        f.departure_local.startsWith(endDate) &&
        f.flight_id !== currentFlightItem.catalog_id
      )
      .map(f => {
        const depMins = timeToMinutes(f.departure_local.substring(11, 16));
        const pricePerSeat = f.price_per_seat.amount;
        const totalPrice = pricePerSeat * travelers;
        const diff = totalPrice - currentFlightItem.price_inr;
        const hasEnoughSeats = f.seats_left >= travelers;
        const meetsBuffer = depMins >= (9 * 60); // Must depart after 09:00 to allow 180 min checkin + 90 min transfer

        return {
          flight: f,
          totalPrice,
          priceDiff: diff,
          hasEnoughSeats,
          meetsBuffer,
          canSwap: hasEnoughSeats && meetsBuffer,
          conflictReason: !hasEnoughSeats
            ? `Only ${f.seats_left} seats left (requires ${travelers})`
            : !meetsBuffer
            ? `Early departure ${f.departure_local.substring(11, 16)} violates 180m check-in buffer with ground transfer`
            : null
        };
      });
  }
}

// Get alternative hotels for swapping (M6)
export function getAlternativeHotels(currentHotelItem, city, checkInDate, nights, travelersCount, adults, children) {
  const cityHotels = hotelsData.filter(h => h.city === city && h.hotel_id !== currentHotelItem.catalog_id);

  return cityHotels.map(h => {
    const hRooms = roomsData.filter(r => r.hotel_id === h.hotel_id);
    let validRoom = null;
    let validRoomsNeeded = 0;
    let conflict = null;

    for (const room of hRooms) {
      const { fits, roomsNeeded } = checkRoomFit(room, adults, children);
      if (fits) {
        const isAvail = checkRoomAvailability(room.room_id, checkInDate, nights, roomsNeeded);
        if (isAvail) {
          validRoom = room;
          validRoomsNeeded = roomsNeeded;
          break;
        } else {
          conflict = `Room ${room.name} has insufficient inventory on requested dates`;
        }
      } else {
        conflict = `Rooms in this hotel cannot accommodate ${travelersCount} travelers (capacity limits)`;
      }
    }

    const price = validRoom ? validRoom.price_per_night.amount * validRoomsNeeded * nights : 0;
    const diff = price - currentHotelItem.price_inr;

    return {
      hotel: h,
      room: validRoom,
      roomsNeeded: validRoomsNeeded,
      totalPrice: price,
      priceDiff: diff,
      canSwap: validRoom !== null,
      conflictReason: validRoom ? null : (conflict || 'No suitable room availability found')
    };
  });
}

// Get attractions that can be added to a specific day (M6)
export function getAvailableAttractionsForDay(dateStr, tripPackage) {
  const weekday = getWeekdayCode(dateStr);
  const existingAttractions = tripPackage.items.filter(i => i.type === 'attraction');
  const existingIds = new Set(existingAttractions.map(i => i.catalog_id));

  // Determine city for date
  const hotels = tripPackage.items.filter(i => i.type === 'hotel');
  const stay = hotels.find(h => dateStr >= h.start && dateStr < h.end) || hotels[0];
  const city = stay ? stay.city : tripPackage.cityPlan[0].city;

  // Attractions for that date
  const dayAttractions = existingAttractions.filter(i => i.start.startsWith(dateStr));

  return attractionsData
    .filter(a => a.city === city && !existingIds.has(a.attraction_id))
    .map(att => {
      const isOpenToday = att.open_days.includes(weekday);
      const isNotClosedDate = !att.closed_dates || !att.closed_dates.includes(dateStr);

      // Check slot availability (10:00 - 12:00 or 14:30 - 16:30 or 17:00 - 18:30)
      let availableSlot = null;
      let conflictReason = null;

      if (!isOpenToday) {
        conflictReason = `Closed on ${weekday}s`;
      } else if (!isNotClosedDate) {
        conflictReason = `Closed on ${dateStr} for special event`;
      } else if (dayAttractions.length >= 3) {
        conflictReason = `Maximum 3 attractions already planned for this day`;
      } else {
        // Test standard sightseeing slots
        const candidateSlots = ['10:00', '13:30', '16:00'];
        for (const slotStart of candidateSlots) {
          const slotStartMins = timeToMinutes(slotStart);
          const slotEndMins = slotStartMins + att.visit_minutes;
          const slotEnd = minutesToTime(slotEndMins);

          // Check open hours
          if (isTimeInWindow(slotStart, att.open_from, att.open_until) &&
              slotEndMins <= timeToMinutes(att.open_until)) {
            // Check non-overlap with today's attractions
            const overlaps = dayAttractions.some(existing => {
              const eStart = timeToMinutes(existing.start.substring(11, 16));
              const eEnd = timeToMinutes(existing.end.substring(11, 16));
              return slotStartMins < eEnd && eStart < slotEndMins;
            });

            if (!overlaps) {
              availableSlot = { start: slotStart, end: slotEnd };
              break;
            }
          }
        }

        if (!availableSlot) {
          conflictReason = `Operating hours (${att.open_from}-${att.open_until}) overlap with existing sightseeing slots`;
        }
      }

      const travelers = tripPackage.traveler.adults + tripPackage.traveler.children;
      const price = calculateAttractionPrice(att, tripPackage.traveler.adults, tripPackage.traveler.children);

      return {
        attraction: att,
        canAdd: availableSlot !== null,
        availableSlot,
        conflictReason,
        price
      };
    });
}

// Browser download helper for JSON export (M5)
export function exportPackageJSON(tripPackage) {
  if (!tripPackage) return;

  // Clean export conforming strictly to DATA_DICTIONARY.md
  const exportPayload = {
    trip_id: tripPackage.trip_id,
    country: tripPackage.country,
    status: tripPackage.status || 'PLANNED',
    booking: tripPackage.booking || null,
    traveler: tripPackage.traveler,
    start_date: tripPackage.start_date,
    end_date: tripPackage.end_date,
    budget_inr: tripPackage.budget_inr,
    total_inr: tripPackage.total_inr,
    total_price_inr: tripPackage.total_price_inr || tripPackage.total_inr,
    items: tripPackage.items.map(item => ({
      item_id: item.item_id,
      type: item.type,
      name: item.name,
      city: item.city,
      status: tripPackage.status || item.status,
      catalog_id: item.catalog_id,
      room_id: item.room_id || null,
      start: item.start,
      end: item.end,
      quantity: item.quantity,
      price_inr: item.price_inr,
      booking: tripPackage.booking || null,
      sources: item.sources || [],
      warnings: item.warnings || []
    }))
  };

  const jsonStr = JSON.stringify(exportPayload, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `normad-grid-package-${tripPackage.booking?.reference || tripPackage.trip_id}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Sample trip presets for quick-fill buttons
export const sampleTrips = {
  standardSample: {
    departureCity: 'Bengaluru',
    destinationCountry: 'Japan',
    startDate: '2027-04-10',
    nights: 6,
    adults: 2,
    children: [6],
    budget: 350000
  },
  overBudgetSample: {
    departureCity: 'Bengaluru',
    destinationCountry: 'Japan',
    startDate: '2027-04-10',
    nights: 6,
    adults: 2,
    children: [6],
    budget: 120000
  },
  impossibleTripSample: {
    departureCity: 'Bengaluru',
    destinationCountry: 'Japan',
    startDate: '2027-04-16',
    nights: 8,
    adults: 2,
    children: [6],
    budget: 350000
  }
};

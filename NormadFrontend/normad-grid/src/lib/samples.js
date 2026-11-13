// One-click example trips for the form (the values are sent to the backend like any other request).
export const sampleTrips = {
  standardSample: {
    departureCity: 'Bengaluru', destinationCountry: 'Japan', startDate: '2027-04-10',
    nights: 6, adults: 2, children: [6], budget: 350000,
  },
  overBudgetSample: {
    departureCity: 'Bengaluru', destinationCountry: 'Japan', startDate: '2027-04-10',
    nights: 6, adults: 2, children: [6], budget: 120000,
  },
  impossibleTripSample: {
    departureCity: 'Bengaluru', destinationCountry: 'Japan', startDate: '2027-04-16',
    nights: 8, adults: 2, children: [6], budget: 350000,
  },
};

// The form keeps its own field names; the backend has its own. This is the only place that translates between them.
export function toApiRequest(r) {
  return {
    departure_city: r.departureCity,
    country: r.destinationCountry,
    start_date: r.startDate,
    nights: Number(r.nights),
    adults: Number(r.adults),
    child_ages: (r.children || []).map((a) => (a === '' || a === null || a === undefined ? null : Number(a))),
    budget_inr: Number(r.budget),
  };
}

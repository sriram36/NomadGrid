// The backend package -> the shape the screens use. Only renames and derived fields: no business logic.
export function toView(pkg) {
  if (!pkg) return pkg;
  const traveler = pkg.traveler || {};
  return {
    ...pkg,
    nights: pkg.nights ?? pkg.request?.nights,
    cityPlan: (pkg.city_plan || []).map((c) => ({ ...c })),
    total_inr: pkg.pricing?.total_inr,
    budget_inr: pkg.pricing?.budget_inr,
    booking: pkg.reservation ? { reference: pkg.reservation.number } : null,
    traveler: { ...traveler, departure_city: traveler.departure_city || pkg.request?.departure_city },
  };
}

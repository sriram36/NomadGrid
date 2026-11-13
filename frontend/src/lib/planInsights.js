// S5: the "rule and trade-off" bullets for the Why This Plan card, worked out from the package itself.
// Pure functions, no network and no AI. The backend still owns every rule: this only explains the result.
import { formatINR } from './format';

const toMinutes = (iso) => {
  const [d, t] = iso.split('T');
  const [y, m, day] = d.split('-').map(Number);
  const [hh, mm] = t.split(':').map(Number);
  return Date.UTC(y, m - 1, day, hh, mm) / 60000;
};

const hm = (mins) => {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h ? `${h}h ${String(m).padStart(2, '0')}m` : `${m} min`;
};

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

function planBullet(pkg) {
  const plan = pkg.cityPlan || [];
  const split = plan.map((c) => `${c.city} ${c.nights}N`).join(' + ');
  if (plan.length === 1) {
    return `${plan[0].nights} nights in ${plan[0].city} meets the minimum of 2 nights per city. With one base there is no moving between cities, so no backtracking.`;
  }
  const hops = plan.length - 1;
  return `${split}: every city gets at least 2 nights, each city appears once and the ${plural(hops, 'move')} go${hops === 1 ? 'es' : ''} `
    + `straight ${plan.map((c) => c.city).join(' → ')} with no backtracking.`;
}

function roomBullets(pkg) {
  const { adults, children, child_ages: ages = [] } = pkg.traveler || {};
  const who = `${plural(adults, 'adult')}${children ? ` + ${plural(children, 'child')}${ages.length ? ` (age${ages.length > 1 ? 's' : ''} ${ages.join(', ')})` : ''}` : ''}`;
  return (pkg.items || []).filter((i) => i.type === 'hotel').map((h) => {
    const room = h.details?.roomType || 'room';
    return `${h.city}: ${h.quantity} × ${room} for ${who}. The backend picks the fewest rooms that fit everyone and keep at least one adult per room.`;
  });
}

function bufferBullets(pkg) {
  const items = pkg.items || [];
  const arrFlight = items.find((i) => i.type === 'flight' && i.leg === 'ARRIVAL');
  const arrTransfer = items.find((i) => i.type === 'transfer' && i.leg === 'AIRPORT_ARRIVAL');
  const depTransfer = items.find((i) => i.type === 'transfer' && i.leg === 'AIRPORT_DEPARTURE');
  const retFlight = items.find((i) => i.type === 'flight' && i.leg === 'RETURN');
  const out = [];
  if (arrFlight && arrTransfer) {
    const gap = toMinutes(arrTransfer.start) - toMinutes(arrFlight.end);
    out.push(`Arrival: the airport pickup is ${hm(gap)} after landing (the rule needs at least 1h).`);
  }
  if (depTransfer && retFlight) {
    const margin = toMinutes(retFlight.start) - toMinutes(depTransfer.end);
    out.push(`Departure: you reach the airport ${hm(margin)} before take-off (the rule needs at least 3h).`);
  }
  return out;
}

function budgetBullet(pkg) {
  const remaining = pkg.pricing?.remaining_inr ?? 0;
  const budget = pkg.pricing?.budget_inr ?? pkg.budget_inr;
  const base = remaining >= 0
    ? `Budget: ${formatINR(pkg.pricing.total_inr)} of ${formatINR(budget)} used, leaving ${formatINR(remaining)} headroom.`
    : `Budget: ${formatINR(Math.abs(remaining))} over the ${formatINR(budget)} budget.`;
  return base;
}

export function buildPlanInsights(pkg) {
  if (!pkg) return [];
  return [
    { title: 'Night split and city order', lines: [planBullet(pkg)] },
    { title: 'Room capacity', lines: roomBullets(pkg) },
    { title: 'Airport buffers', lines: bufferBullets(pkg) },
    { title: 'Budget', lines: [budgetBullet(pkg)] },
  ].filter((s) => s.lines.length > 0);
}

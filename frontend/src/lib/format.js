// Small display helpers (no travel rules here: the backend owns all logic).

// 350000 -> "₹3,50,000"
export function formatINR(amount) {
  if (amount === undefined || amount === null || isNaN(amount)) return '₹0';
  return '₹' + Math.round(amount).toLocaleString('en-IN');
}

// "2027-04-10" + 3 -> "2027-04-13"
export function addDays(dateStr, days) {
  const [y, m, d] = dateStr.split('-').map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().split('T')[0];
}

// "2027-04-10" -> "Sat, 10 Apr"
export function prettyDate(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('en-IN', {
    weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC',
  });
}

// 1075 -> "17h 55m"
export function hoursMinutes(minutes) {
  if (minutes === undefined || minutes === null) return '';
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, '0')}m`;
}

// "+₹2,400" / "−₹1,360" / "Same price"
export function signedINR(delta) {
  if (delta === null || delta === undefined) return '';
  if (delta === 0) return 'Same price';
  return `${delta > 0 ? '+' : '−'}${formatINR(Math.abs(delta))}`;
}

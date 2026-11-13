// Thin client for the NomadGrid backend. Every call returns { status, data } and never throws for HTTP errors,
// so screens can show the backend's own messages. Only a network failure throws (as NetworkError).

export class NetworkError extends Error {
  constructor() {
    super('We could not reach the booking server. Please check that the backend is running and try again.');
    this.name = 'NetworkError';
  }
}

async function call(method, path, body) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body === undefined ? undefined : { 'content-type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new NetworkError();
  }
  let data = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  return { status: res.status, data };
}

const enc = encodeURIComponent;

export const api = {
  meta: () => call('GET', '/api/meta'),
  build: (request) => call('POST', '/api/packages', request),
  variants: (request) => call('POST', '/api/packages/variants', request),
  parseRequest: (text) => call('POST', '/api/parse-request', { text }),
  getPackage: (id) => call('GET', `/api/packages/${enc(id)}`),
  hotelOptions: (id, city) => call('GET', `/api/packages/${enc(id)}/options/hotels?city=${enc(city)}`),
  flightOptions: (id, leg) => call('GET', `/api/packages/${enc(id)}/options/flights?leg=${enc(leg)}`),
  attractionOptions: (id, date) => call('GET', `/api/packages/${enc(id)}/options/attractions?date=${enc(date)}`),
  cityPlanOptions: (id) => call('GET', `/api/packages/${enc(id)}/options/city-plans`),
  change: (id, op) => call('POST', `/api/packages/${enc(id)}/changes`, op),
  undo: (id) => call('POST', `/api/packages/${enc(id)}/undo`),
  confirm: (id) => call('POST', `/api/packages/${enc(id)}/confirm`),
  reservation: (number) => call('GET', `/api/reservations/${enc(number)}`),
  cityGuide: (city) => call('GET', `/api/cities/${enc(city)}/guide`),
  dining: (id) => call('GET', `/api/packages/${enc(id)}/dining`),
  exportUrl: (id) => `/api/packages/${enc(id)}/export`,
};

// "Please fix the highlighted fields" -> { nights: 'Nights must be…', … } keyed by the backend's field names.
export function fieldErrors(data) {
  const out = {};
  for (const f of data?.error?.fields || []) out[f.field] = f.message;
  return out;
}

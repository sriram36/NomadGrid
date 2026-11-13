import React from 'react';
import { Plane, TrainFront, Bus, Car, MapPin, Home } from 'lucide-react';
import { hoursMinutes } from '../lib/format';

const minutesBetween = (a, b) => {
  const t = (iso) => {
    const [d, tm] = iso.split('T');
    const [y, m, day] = d.split('-').map(Number);
    const [hh, mm] = tm.split(':').map(Number);
    return Date.UTC(y, m - 1, day, hh, mm) / 60000;
  };
  return t(b) - t(a);
};

// A short label for an intercity transfer: "Shinkansen", "Bus" or "Private transfer".
function transferMode(item) {
  const name = (item.name || '').toLowerCase();
  if (name.includes('shinkansen')) return { label: 'Shinkansen', Icon: TrainFront };
  const type = item.details?.transferType || '';
  if (type === 'TRAIN' || item.icon === 'train') return { label: 'Train', Icon: TrainFront };
  if (type.includes('BUS') || item.icon === 'bus') return { label: 'Bus', Icon: Bus };
  return { label: 'Private transfer', Icon: Car };
}

// "AirVeda AV 832" -> "AV 832"
const flightCode = (item) => {
  const d = item.details;
  if (d?.flightNumber) return d.flightNumber;
  const parts = (item.subtitle || '').split(' · ')[0].split(' ');
  return parts.slice(-2).join(' ');
};

function Connector({ Icon, top, bottom }) {
  return (
    <div className="flex md:flex-col items-center md:min-w-28 gap-2 md:gap-0 py-1 md:py-0 px-1">
      <div className="hidden md:block text-[10px] font-extrabold text-[#003580] leading-tight text-center">{top}</div>
      <div className="flex items-center md:w-full">
        <div className="hidden md:block h-px flex-1 bg-slate-300" />
        <span className="size-8 rounded-full bg-white border border-[#006ce4] text-[#006ce4] flex items-center justify-center shadow-xs shrink-0">
          <Icon className="size-4" />
        </span>
        <div className="hidden md:block h-px flex-1 bg-slate-300" />
      </div>
      <div className="text-[10px] font-semibold text-slate-500 leading-tight text-center">{bottom}</div>
      <div className="md:hidden text-[11px] font-bold text-[#003580]">{top}</div>
    </div>
  );
}

function Node({ icon: Icon, title, caption, tone = 'city' }) {
  const styles = tone === 'home'
    ? 'bg-[#003580] text-white border-[#003580]'
    : 'bg-white text-[#003580] border-slate-300';
  return (
    <div className={`rounded-xl border px-3.5 py-2.5 shadow-xs min-w-28 text-center ${styles}`}>
      <Icon className={`size-4 mx-auto mb-1 ${tone === 'home' ? 'text-[#febb02]' : 'text-[#006ce4]'}`} />
      <div className="text-xs font-black leading-tight">{title}</div>
      <div className={`text-[10px] font-semibold mt-0.5 ${tone === 'home' ? 'text-white/80' : 'text-slate-500'}`}>{caption}</div>
    </div>
  );
}

// S6: departure city -> flight -> each city (with its nights) -> flight -> departure city.
// Everything is read from the current package, so it follows variant switches and flight/hotel/city changes.
export default function VisualRoute({ tripPackage }) {
  const items = tripPackage?.items || [];
  const plan = tripPackage?.cityPlan || [];
  if (!plan.length) return null;

  const home = tripPackage.traveler?.departure_city || 'Home';
  const arrival = items.find((i) => i.type === 'flight' && i.leg === 'ARRIVAL');
  const ret = items.find((i) => i.type === 'flight' && i.leg === 'RETURN');
  const hops = items.filter((i) => i.type === 'transfer' && i.leg === 'INTERCITY');

  const flightInfo = (f) => (f ? {
    top: `${flightCode(f)}${f.details?.from && f.details?.to ? ` · ${f.details.from}→${f.details.to}` : ''}`,
    bottom: `${f.badges?.includes('DIRECT') ? 'Direct' : '1 stop'} · ${hoursMinutes(f.details?.durationMinutes ?? minutesBetween(f.start, f.end))}`,
  } : { top: 'Flight', bottom: '' });

  const nodes = [];
  nodes.push({ kind: 'node', key: 'home-out', props: { icon: Home, title: home, caption: 'Departure', tone: 'home' } });
  nodes.push({ kind: 'link', key: 'fly-out', Icon: Plane, ...flightInfo(arrival) });
  plan.forEach((c, idx) => {
    nodes.push({ kind: 'node', key: `city-${c.city}`, props: { icon: MapPin, title: c.city, caption: `${c.nights} night${c.nights === 1 ? '' : 's'}` } });
    if (idx < plan.length - 1) {
      const hop = hops[idx];
      if (hop) {
        const { label, Icon } = transferMode(hop);
        const mins = hop.details?.durationMinutes ?? minutesBetween(hop.start, hop.end);
        nodes.push({ kind: 'link', key: `hop-${idx}`, Icon, top: label, bottom: hoursMinutes(mins) });
      } else {
        nodes.push({ kind: 'link', key: `hop-${idx}`, Icon: Car, top: 'Transfer', bottom: '' });
      }
    }
  });
  nodes.push({ kind: 'link', key: 'fly-back', Icon: Plane, ...flightInfo(ret) });
  nodes.push({ kind: 'node', key: 'home-back', props: { icon: Home, title: home, caption: 'Back home', tone: 'home' } });

  return (
    <section className="bg-white rounded-xl border border-slate-300 shadow-sm p-4 sm:p-5" aria-label="Your journey" data-testid="visual-route">
      <h3 className="text-sm font-extrabold text-[#003580] mb-3">Your journey</h3>
      <div className="flex flex-col md:flex-row md:items-center md:justify-center items-stretch gap-1 md:gap-0 md:overflow-x-auto">
        {nodes.map((n) => (n.kind === 'node'
          ? <div key={n.key} className="flex justify-center"><Node {...n.props} /></div>
          : <Connector key={n.key} Icon={n.Icon} top={n.top} bottom={n.bottom} />))}
      </div>
    </section>
  );
}

import React from 'react';
import { Plane, Train, Bus, Car, MapPin, Home } from 'lucide-react';

// S6: the journey at a glance - departure hub, cities in visit order, and every leg with its mode and duration.
// Drawn from `package.route`, so it updates whenever the package changes (variant switch, hotel/flight/city edits).
const MODE_ICON = { FLIGHT: Plane, TRAIN: Train, BUS: Bus, TAXI: Car, TRANSFER: Car };
const MODE_LABEL = { FLIGHT: 'Flight', TRAIN: 'Train', BUS: 'Bus', TAXI: 'Taxi', TRANSFER: 'Transfer' };

function Leg({ leg }) {
  const Icon = MODE_ICON[leg.mode] || Car;
  return (
    <div className="flex flex-col items-center justify-center min-w-[110px] px-1" data-testid="route-leg">
      <span className="text-[10px] font-bold text-slate-500 text-center leading-tight">{leg.label}</span>
      <div className="flex items-center w-full my-1">
        <span className="flex-1 border-t-2 border-dashed border-[#006ce4]" />
        <span className="mx-1 w-6 h-6 rounded-full bg-[#006ce4] text-white flex items-center justify-center shrink-0">
          <Icon className="w-3.5 h-3.5" />
        </span>
        <span className="flex-1 border-t-2 border-dashed border-[#006ce4]" />
      </div>
      <span className="text-[10px] font-bold text-[#003580] tabular-nums">
        {MODE_LABEL[leg.mode] || 'Transfer'} · {leg.duration_label}
      </span>
    </div>
  );
}

function Node({ title, sub, hub }) {
  return (
    <div className="flex flex-col items-center text-center min-w-[84px]" data-testid="route-stop">
      <span className={`w-10 h-10 rounded-full flex items-center justify-center shadow-sm border-2 ${
        hub ? 'bg-[#febb02] border-[#febb02] text-[#003580]' : 'bg-[#003580] border-[#003580] text-white'}`}>
        {hub ? <Home className="w-4 h-4" /> : <MapPin className="w-4 h-4" />}
      </span>
      <span className="mt-1 text-xs font-extrabold text-slate-900 leading-tight">{title}</span>
      <span className="text-[10px] font-bold text-slate-500">{sub}</span>
    </div>
  );
}

export default function RouteMap({ route }) {
  if (!route || !route.stops?.length) return null;
  const { origin, stops, legs, summary } = route;
  // legs: outbound flight, [intercity...], return flight  ->  hub - leg - stop - leg - stop ... - leg - hub
  const cells = [<Node key="o" title={origin.city} sub={origin.airport || 'Home'} hub />];
  legs.forEach((leg, i) => {
    cells.push(<Leg key={`l${i}`} leg={leg} />);
    if (i < stops.length) {
      const s = stops[i];
      cells.push(<Node key={`s${i}`} title={s.city} sub={`${s.nights} night${s.nights === 1 ? '' : 's'}`} />);
    } else {
      cells.push(<Node key="r" title={origin.city} sub="Home" hub />);
    }
  });
  return (
    <div className="bg-white border border-slate-300 rounded-xl shadow-sm p-4" data-testid="route-map">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h3 className="text-sm font-extrabold text-[#003580]">Your journey</h3>
        <span className="text-[11px] font-bold text-slate-500">
          {summary.cities} {summary.cities === 1 ? 'city' : 'cities'} · {summary.nights} nights · {summary.travel_label} travelling
        </span>
      </div>
      <div className="overflow-x-auto pb-1">
        <div className="flex items-center min-w-max">{cells}</div>
      </div>
    </div>
  );
}

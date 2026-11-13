import { Plane, Train, Bus, Car, MapPin, Home, Moon, Clock, Route } from 'lucide-react';

// S6: the journey at a glance - departure hub, cities in visit order, and every leg with its mode and duration.
// Drawn from `package.route`, so it updates whenever the package changes (variant switch, hotel/flight/city edits).
const MODE_ICON = { FLIGHT: Plane, TRAIN: Train, BUS: Bus, TAXI: Car, TRANSFER: Car };
const MODE_LABEL = { FLIGHT: 'Flight', TRAIN: 'Train', BUS: 'Bus', TAXI: 'Taxi', TRANSFER: 'Transfer' };

const shortDate = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });

// A leg between two places: a dashed line (vertical on phones, horizontal on wider screens) with the mode on it.
function Leg({ leg }) {
  const Icon = MODE_ICON[leg.mode] || Car;
  return (
    <div className="flex md:flex-col items-center justify-center md:flex-1 md:min-w-[150px] gap-3 md:gap-1.5 py-1 md:py-0 px-2" data-testid="route-leg">
      <span className="hidden md:block text-[11px] font-bold text-slate-500 text-center leading-tight">{leg.label}</span>
      <div className="relative flex items-center justify-center md:w-full h-14 md:h-9">
        <span className="absolute h-full w-0 md:h-0 md:w-full border-l-2 md:border-l-0 md:border-t-2 border-dashed border-[#006ce4]/60" />
        <span className="relative w-9 h-9 rounded-full bg-[#006ce4] text-white flex items-center justify-center shadow-md ring-4 ring-white">
          <Icon className="w-4 h-4" />
        </span>
      </div>
      <div className="text-left md:text-center">
        <span className="md:hidden block text-[11px] font-bold text-slate-500 leading-tight">{leg.label}</span>
        <span className="inline-flex items-center gap-1 text-[11px] font-extrabold text-[#003580] tabular-nums">
          <Clock className="w-3 h-3" /> {MODE_LABEL[leg.mode] || 'Transfer'} · {leg.duration_label}
        </span>
      </div>
    </div>
  );
}

// A place on the route: home, or a city you stay in.
function Stop({ stop, hub }) {
  return (
    <div
      className={`rounded-xl border-2 p-3 text-center md:min-w-[130px] shadow-sm ${
        hub ? 'border-[#febb02] bg-[#fff9e6]' : 'border-[#003580] bg-[#f2f6fa]'}`}
      data-testid="route-stop"
    >
      <span className={`mx-auto w-10 h-10 rounded-full flex items-center justify-center ${
        hub ? 'bg-[#febb02] text-[#003580]' : 'bg-[#003580] text-white'}`}>
        {hub ? <Home className="w-5 h-5" /> : <MapPin className="w-5 h-5" />}
      </span>
      <p className="mt-1.5 text-sm font-black text-slate-900 leading-tight">{stop.city}</p>
      {hub ? (
        <p className="text-[11px] font-bold text-slate-500">{stop.sub}</p>
      ) : (
        <>
          <p className="mt-0.5 inline-flex items-center gap-1 text-[11px] font-extrabold text-[#003580]">
            <Moon className="w-3 h-3" /> {stop.nights} night{stop.nights === 1 ? '' : 's'}
          </p>
          <p className="text-[10px] font-semibold text-slate-500">{shortDate(stop.check_in)} – {shortDate(stop.check_out)}</p>
          <p className="text-[10px] text-slate-400 leading-tight mt-0.5">{stop.hotel}</p>
        </>
      )}
    </div>
  );
}

function Chip({ children }) {
  return <span className="px-2.5 py-1 rounded-full bg-white/15 text-white text-[11px] font-bold">{children}</span>;
}

export default function RouteMap({ route }) {
  if (!route || !route.stops?.length) return null;
  const { origin, stops, legs, summary } = route;
  // legs: outbound flight, [intercity...], return flight  ->  home - leg - stop - leg - stop ... - leg - home
  const home = { city: origin.city, sub: origin.airport ? `${origin.airport} · Home` : 'Home' };
  const cells = [<Stop key="o" stop={home} hub />];
  legs.forEach((leg, i) => {
    cells.push(<Leg key={`l${i}`} leg={leg} />);
    cells.push(i < stops.length ? <Stop key={`s${i}`} stop={stops[i]} /> : <Stop key="r" stop={home} hub />);
  });
  return (
    <div className="bg-white border border-slate-300 rounded-xl shadow-sm overflow-hidden" data-testid="route-map">
      <div className="bg-[#003580] px-4 py-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-extrabold text-white">
          <Route className="w-4 h-4 text-[#febb02]" /> Your journey
        </h3>
        <div className="flex flex-wrap gap-1.5">
          <Chip>{summary.cities} {summary.cities === 1 ? 'city' : 'cities'}</Chip>
          <Chip>{summary.nights} nights</Chip>
          <Chip>{summary.travel_label} travelling</Chip>
        </div>
      </div>
      <div className="p-4 sm:p-5 overflow-x-auto">
        <div className="flex flex-col md:flex-row md:items-center md:justify-center md:min-w-max">{cells}</div>
      </div>
    </div>
  );
}

import ChatPanel from "../components/ChatPanel";
import ItineraryTimeline from "../components/ItineraryTimeline";
import MapView from "../components/MapView";
import CalendarButton from "../components/CalendarButton";
import trip from "../data/sampleTrip.json";
import { buildFlightsLink, buildHotelsLink } from "../utils/travelLinks";

const tripStart = new Date(trip.start_date);
const tripEnd = new Date(trip.end_date ?? trip.start_date);
const tripNights = Math.max(
  1,
  Math.round((tripEnd.getTime() - tripStart.getTime()) / (1000 * 60 * 60 * 24))
);

const rangeFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

const highlights = [
  { label: "Origin", value: trip.origin ?? "Flexible" },
  { label: "Destination", value: trip.city },
  {
    label: "Trip window",
    value: `${rangeFormatter.format(tripStart)} → ${rangeFormatter.format(
      tripEnd
    )} · ${tripNights} night${tripNights === 1 ? "" : "s"}`,
  },
];

const hotelsLink = buildHotelsLink(trip);
const flightsLink = buildFlightsLink(trip);

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 right-0 h-96 w-96 rounded-full bg-indigo-500/30 blur-[160px]" />
        <div className="absolute bottom-0 left-0 h-[28rem] w-[28rem] rounded-full bg-fuchsia-500/20 blur-[200px]" />
      </div>

      <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-12 lg:px-8">
        <header className="space-y-6 text-center lg:text-left">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/20 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-white/70">
            Live itinerary · Updated in seconds
          </div>
          <div>
            <p className="text-sm uppercase tracking-[0.5em] text-indigo-200">
              WanderGenie
            </p>
            <h1 className="mt-3 text-4xl font-black leading-tight text-white sm:text-5xl">
              NYC winter escape, mapped to your mood.
            </h1>
            <p className="mt-4 text-lg text-slate-300">
              Blend iconic highlights with local secrets. Fine-tune every day
              with AI co-planning, live maps, and calendar-ready exports.
            </p>
          </div>
        </header>

        <section className="mt-8 grid gap-4 sm:grid-cols-3">
          {highlights.map((item) => (
            <div
              key={item.label}
              className="rounded-3xl border border-white/10 bg-white/5 p-4 text-left shadow-lg backdrop-blur"
            >
              <p className="text-xs uppercase tracking-[0.3em] text-white/70">
                {item.label}
              </p>
              <p className="mt-2 text-xl font-semibold text-white">
                {item.value}
              </p>
            </div>
          ))}
          <div className="rounded-3xl border border-white/10 bg-gradient-to-r from-orange-500 to-pink-500 p-4 text-left shadow-xl">
            <p className="text-xs uppercase tracking-[0.3em] text-white/70">
              Instant actions
            </p>
            <div className="mt-3 space-y-2">
              <a
                href={flightsLink.url}
                target="_blank"
                rel="noreferrer"
                className="flex w-full flex-col rounded-2xl bg-white/20 px-4 py-3 text-left text-sm font-semibold text-white transition hover:bg-white/30"
              >
                <span className="text-xs uppercase tracking-[0.3em] text-white/80">
                  Flights
                </span>
                <span className="text-base">
                  {trip.city} · {flightsLink.window}
                </span>
              </a>
              <a
                href={hotelsLink.url}
                target="_blank"
                rel="noreferrer"
                className="flex w-full flex-col rounded-2xl bg-white/20 px-4 py-3 text-left text-sm font-semibold text-white transition hover:bg-white/30"
              >
                <span className="text-xs uppercase tracking-[0.3em] text-white/80">
                  Stays
                </span>
                <span className="text-base">
                  Near {hotelsLink.landmark}
                </span>
              </a>
            </div>
          </div>
        </section>

        <section className="mt-10 grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="space-y-6">
            <ChatPanel />
            <ItineraryTimeline />
          </div>
          <div className="space-y-6">
            <MapView />
            <CalendarButton />
          </div>
        </section>
      </div>
    </div>
  );
}

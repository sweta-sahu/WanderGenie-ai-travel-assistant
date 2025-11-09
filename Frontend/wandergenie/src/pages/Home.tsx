import { useState } from "react";
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
  const [hasPlan, setHasPlan] = useState(false);
  const [lastPrompt, setLastPrompt] = useState<string | null>(null);
  const [isPlanning, setIsPlanning] = useState(false);

  const heroTitle = hasPlan
    ? trip.origin
      ? `${trip.origin} → ${trip.city}`
      : trip.city
    : "Let's design your next escape";

  const heroSubtitle = hasPlan
    ? "Blend iconic highlights with local secrets. Fine-tune every day with AI co-planning, live maps, and calendar-ready exports."
    : "Describe the mood, travel pace, or dream experiences above and WanderGenie will craft the rest.";

  const handlePlan = (prompt: string) => {
    setIsPlanning(true);
    setLastPrompt(prompt);
    setTimeout(() => {
      setHasPlan(true);
      setIsPlanning(false);
    }, 600);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 right-0 h-96 w-96 rounded-full bg-indigo-500/30 blur-[160px]" />
        <div className="absolute bottom-0 left-0 h-[28rem] w-[28rem] rounded-full bg-fuchsia-500/20 blur-[200px]" />
      </div>

      <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-12 lg:px-8">
        <header className="space-y-4 rounded-[32px] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-indigo-900/10 backdrop-blur">
          <div className="flex flex-col gap-4 text-center lg:flex-row lg:items-center lg:justify-between lg:text-left">
            <p className="text-3xl font-black uppercase tracking-[0.55em] text-white sm:text-4xl">
              WanderGenie
            </p>
            <span className="self-center rounded-full border border-white/20 px-4 py-1 text-[0.70rem] font-semibold uppercase tracking-[0.5em] text-white/80 lg:self-auto">
              Live itinerary · Updated in seconds
            </span>
          </div>
          <h1 className="text-2xl font-black leading-tight text-white sm:text-3xl">
            {heroTitle}
          </h1>
          <p className="text-lg text-slate-200 sm:text-xl">
            {lastPrompt && hasPlan
              ? `Dialed in for: “${lastPrompt}”`
              : heroSubtitle}
          </p>
        </header>

        <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-6">
            <ChatPanel onPlan={handlePlan} isPlanning={isPlanning} />
            {hasPlan ? (
              <ItineraryTimeline />
            ) : (
              <EmptyStatePanel
                title="Your itinerary will appear here"
                description="Kick off a chat to unlock day-by-day schedules, bookings, and pacing suggestions."
              />
            )}
          </div>
          <div className="flex flex-col gap-6">
            <HighlightsSection hasPlan={hasPlan} />
            <InstantActionsCard hasPlan={hasPlan} />
            <MapView isActive={hasPlan} />
            {hasPlan ? (
              <CalendarButton />
            ) : (
              <EmptyStatePanel
                title="Calendar export unlocks later"
                description="Once WanderGenie drafts a trip, you'll be able to push it to Google or Outlook."
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

type HighlightsProps = {
  hasPlan: boolean;
};

type HighlightCard = {
  heading: string;
  value: string;
  description?: string;
};

function HighlightsSection({ hasPlan }: HighlightsProps) {
  const placeholderCards: HighlightCard[] = [
    {
      heading: "Awaiting prompt",
      value: "Origin city",
      description: "Tell us where you're starting from.",
    },
    {
      heading: "Awaiting prompt",
      value: "Dream destination",
      description: "Share the city, vibe, or region.",
    },
    {
      heading: "Awaiting prompt",
      value: "Trip window",
      description: "Rough dates or season help us pace it.",
    },
  ];

  const cards: HighlightCard[] = hasPlan
    ? highlights.map((item) => ({
        heading: item.label,
        value: item.value,
      }))
    : placeholderCards;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {cards.map((item, idx) => (
        <div
          key={`${item.value}-${idx}`}
          className="rounded-3xl border border-white/10 bg-white/5 p-4 text-left shadow-lg backdrop-blur"
        >
          <p className="text-xs uppercase tracking-[0.3em] text-white/60">
            {item.heading}
          </p>
          <p className="mt-2 text-xl font-semibold text-white">
            {item.value}
          </p>
          {item.description ? (
            <p className="mt-1 text-sm text-white/70">{item.description}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function InstantActionsCard({ hasPlan }: HighlightsProps) {
  return (
    <div className="rounded-3xl border border-white/10 bg-gradient-to-r from-orange-500 to-pink-500 p-4 text-left shadow-xl">
      <p className="text-xs uppercase tracking-[0.3em] text-white/70">
        Instant actions
      </p>
      {hasPlan ? (
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
            <span className="text-base">Near {hotelsLink.landmark}</span>
          </a>
        </div>
      ) : (
        <p className="mt-3 text-sm text-white/80">
          We will drop flight and stay shortcuts once the itinerary is
          generated.
        </p>
      )}
    </div>
  );
}

type EmptyProps = {
  title: string;
  description: string;
};

function EmptyStatePanel({ title, description }: EmptyProps) {
  return (
    <div className="rounded-3xl border border-dashed border-white/20 bg-white/5 p-6 text-left text-white/80">
      <p className="text-sm font-semibold uppercase tracking-[0.3em] text-white/60">
        Waiting on copilot
      </p>
      <h3 className="mt-2 text-xl font-semibold text-white">{title}</h3>
      <p className="mt-2 text-sm text-white/70">{description}</p>
    </div>
  );
}

import {
  CalendarDaysIcon,
  ClockIcon,
  LinkIcon,
  MapPinIcon,
} from "@heroicons/react/24/outline";
import { Trip } from "../utils/calendarExport";

const dateFormatter = new Intl.DateTimeFormat("en-US", {
  weekday: "long",
  month: "short",
  day: "numeric",
});

const longDateFormatter = new Intl.DateTimeFormat("en-US", {
  month: "long",
  day: "numeric",
  year: "numeric",
});

const durationLabel = (duration?: number) => {
  if (!duration) return null;
  const hours = Math.floor(duration / 60);
  const minutes = duration % 60;
  if (hours && minutes) return `${hours}h ${minutes}m`;
  if (hours) return `${hours}h`;
  return `${minutes}m`;
};

interface ItineraryTimelineProps {
  trip: Trip;
}

export default function ItineraryTimeline({ trip }: ItineraryTimelineProps) {
  const tripStart = new Date(trip.start_date);
  const tripEnd = new Date(trip.end_date ?? trip.start_date);
  const tripNights = Math.max(
    1,
    Math.round(
      (tripEnd.getTime() - tripStart.getTime()) / (1000 * 60 * 60 * 24)
    )
  );
  return (
    <section className="rounded-3xl border border-white/10 bg-white/90 p-6 text-slate-900 shadow-2xl shadow-indigo-900/5 backdrop-blur">
      <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-500">
            Curated route
          </p>
          <h2 className="text-2xl font-bold text-slate-900">
            {trip.city} itinerary overview
          </h2>
        </div>
        <div className="flex items-center gap-4 rounded-2xl bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-600">
          <CalendarDaysIcon className="h-5 w-5 text-indigo-500" />
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">
              Trip window
            </p>
            <p>
              {longDateFormatter.format(tripStart)} –{" "}
              {longDateFormatter.format(tripEnd)} · {tripNights} nights
            </p>
          </div>
        </div>
      </header>

      <div className="mt-6 space-y-6">
        {trip.days.map((day, dayIndex) => (
          <article
            key={day.date}
            className="rounded-2xl border border-slate-100 bg-white/80 p-4 shadow-sm"
          >
            <div className="flex flex-col gap-3 border-b border-slate-100 pb-4 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-600/10 text-indigo-600">
                  Day {dayIndex + 1}
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-400">
                    {dateFormatter.format(new Date(day.date))}
                  </p>
                  <p className="text-base font-semibold text-slate-900">
                    {trip.city} experiences
                  </p>
                </div>
              </div>
              <span className="text-sm font-medium text-slate-500">
                {day.activities.length} curated moments
              </span>
            </div>

            <ol className="mt-4 space-y-4">
              {day.activities.map((activity, activityIndex) => (
                <li
                  key={`${activity.name}-${activityIndex}`}
                  className="relative rounded-2xl border border-slate-100 bg-white/90 p-4 shadow-sm md:flex md:items-center md:gap-6"
                >
                  <div className="flex items-center gap-3 md:w-40">
                    <div className="text-sm font-semibold text-indigo-600">
                      {activity.time}
                    </div>
                    <div className="hidden h-10 w-px bg-gradient-to-b from-indigo-200 to-transparent md:block" />
                  </div>

                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <MapPinIcon className="h-4 w-4 text-slate-400" />
                      <p className="text-base font-semibold text-slate-900">
                        {activity.name}
                      </p>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-slate-500">
                        {activity.type}
                      </span>
                      {activity.duration_min && (
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500">
                          <ClockIcon className="h-4 w-4 text-slate-400" />
                          {durationLabel(activity.duration_min)}
                        </span>
                      )}
                    </div>
                    {activity.booking_required && (
                      <a
                        href={activity.booking_url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-indigo-600 hover:text-indigo-700"
                      >
                        <LinkIcon className="h-4 w-4" />
                        Reserve spot
                      </a>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </article>
        ))}
      </div>
    </section>
  );
}

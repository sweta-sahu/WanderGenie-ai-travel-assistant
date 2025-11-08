type TripActivity = {
  time: string;
  type: string;
  name: string;
  lat: number;
  lon: number;
  duration_min?: number;
  booking_required?: boolean;
  booking_url?: string;
  notes?: string;
};

type TripDay = {
  date: string;
  activities: TripActivity[];
};

export type Trip = {
  trip_id?: string;
  status?: string;
  city: string;
  origin?: string;
  start_date: string;
  end_date: string;
  days: TripDay[];
  booking_links?: {
    flights?: string;
    hotels?: string;
  };
};

const DEFAULT_DURATION_MIN = 90;

const pad = (value: number) => value.toString().padStart(2, "0");

const formatICSDate = (date: Date) => {
  return (
    date.getUTCFullYear().toString() +
    pad(date.getUTCMonth() + 1) +
    pad(date.getUTCDate()) +
    "T" +
    pad(date.getUTCHours()) +
    pad(date.getUTCMinutes()) +
    pad(date.getUTCSeconds()) +
    "Z"
  );
};

const sanitize = (value?: string) => {
  if (!value) return "";
  return value
    .replace(/\\/g, "\\\\")
    .replace(/,/g, "\\,")
    .replace(/;/g, "\\;")
    .replace(/\n/g, "\\n");
};

const buildEvent = (
  activity: TripActivity,
  day: TripDay,
  city: string,
  stamp: string,
  index: number
) => {
  const [hours, minutes] = activity.time.split(":").map(Number);
  const start = new Date(`${day.date}T00:00:00`);
  start.setHours(hours ?? 0, minutes ?? 0, 0, 0);

  const eventDuration = activity.duration_min ?? DEFAULT_DURATION_MIN;
  const end = new Date(start.getTime() + eventDuration * 60 * 1000);

  const descriptionParts = [
    `Type: ${activity.type}`,
    activity.booking_required ? "Booking required" : null,
    activity.booking_url ? `Link: ${activity.booking_url}` : null,
    activity.notes ?? null,
  ].filter(Boolean);

  return [
    "BEGIN:VEVENT",
    `UID:${stamp}-${index}@wandergenie`,
    `DTSTAMP:${stamp}`,
    `DTSTART:${formatICSDate(start)}`,
    `DTEND:${formatICSDate(end)}`,
    `SUMMARY:${sanitize(activity.name)}`,
    `LOCATION:${sanitize(`${activity.name}, ${city}`)}`,
    descriptionParts.length
      ? `DESCRIPTION:${sanitize(descriptionParts.join(" | "))}`
      : null,
    activity.booking_url ? `URL:${sanitize(activity.booking_url)}` : null,
    "END:VEVENT",
  ]
    .filter(Boolean)
    .join("\n");
};

export const generateICS = (trip: Trip) => {
  const stamp = formatICSDate(new Date());

  const events = trip.days.flatMap((day, dayIndex) =>
    day.activities.map((activity, activityIndex) =>
      buildEvent(
        activity,
        day,
        trip.city,
        stamp,
        dayIndex * 100 + activityIndex
      )
    )
  );

  return [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//WanderGenie//Trip Export//EN",
    "CALSCALE:GREGORIAN",
    ...events,
    "END:VCALENDAR",
  ].join("\n");
};

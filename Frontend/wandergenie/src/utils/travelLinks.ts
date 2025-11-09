import { Trip } from "./calendarExport";

const pad = (value: number) => value.toString().padStart(2, "0");

const formatIsoDate = (date: Date) =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

const formatRangeLabel = (start: Date, end: Date) =>
  `${start.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  })} – ${end.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  })}`;

const getAllActivities = (trip: Trip) =>
  trip.days.flatMap((day) => day.activities ?? []);

const getPrimaryPOI = (trip: Trip) =>
  getAllActivities(trip).find(
    (activity) =>
      typeof activity.lat === "number" &&
      typeof activity.lon === "number" &&
      !Number.isNaN(activity.lat) &&
      !Number.isNaN(activity.lon)
  ) ?? getAllActivities(trip)[0];

const getStartDate = (trip: Trip) => new Date(trip.start_date);
const getEndDate = (trip: Trip) => new Date(trip.end_date ?? trip.start_date);

export const buildHotelsLink = (trip: Trip) => {
  const anchor = getPrimaryPOI(trip);
  const checkin = getStartDate(trip);
  const checkout = getEndDate(trip);

  const params = new URLSearchParams({
    ss: `${trip.city} near ${anchor?.name ?? "city center"}`,
    checkin: formatIsoDate(checkin),
    checkout: formatIsoDate(checkout),
    group_adults: "2",
    no_rooms: "1",
    group_children: "0",
  });

  if (anchor?.lat && anchor?.lon) {
    params.set("selected_latitude", anchor.lat.toString());
    params.set("selected_longitude", anchor.lon.toString());
    params.set("radius", "5");
    params.set("order", "distance_from_landmark");
  }

  const generatedUrl = `https://www.booking.com/searchresults.html?${params.toString()}`;

  return {
    url: trip.booking_links?.hotels ?? generatedUrl,
    landmark: anchor?.name ?? trip.city,
  };
};

export const buildFlightsLink = (trip: Trip) => {
  const depart = getStartDate(trip);
  const returnDate = getEndDate(trip);

  const query = `Flights to ${trip.city} ${formatRangeLabel(
    depart,
    returnDate
  )}`;

  const generatedUrl = `https://www.google.com/travel/flights?q=${encodeURIComponent(
    query
  )}`;

  return {
    url: trip.booking_links?.flights ?? generatedUrl,
    window: formatRangeLabel(depart, returnDate),
  };
};

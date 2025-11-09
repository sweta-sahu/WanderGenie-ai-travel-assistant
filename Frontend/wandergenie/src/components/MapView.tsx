import { useEffect, useMemo, useRef, useState } from "react";
import "mapbox-gl/dist/mapbox-gl.css";
import Map, {
  MapRef,
  Marker,
  NavigationControl,
  Popup,
} from "react-map-gl/mapbox";
import { Trip } from "../utils/calendarExport";

const MAPBOX_TOKEN =
  process.env.REACT_APP_MAPBOX_TOKEN ?? "YOUR_MAPBOX_ACCESS_TOKEN";

export interface MapViewProps {
  isActive: boolean;
  trip: Trip | null;
}

export default function MapView({ isActive, trip }: MapViewProps) {
  const [selected, setSelected] = useState<any>(null);
  const mapRef = useRef<MapRef | null>(null);
  const allPoints = useMemo(
    () => trip ? trip.days.flatMap((d) => d.activities) : [],
    [trip]
  );
  const points = useMemo(
    () => (isActive ? allPoints : []),
    [isActive, allPoints]
  );

  useEffect(() => {
    if (!isActive) setSelected(null);
  }, [isActive]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (!isActive || points.length === 0) {
      map.flyTo({
        center: [0, 20],
        zoom: 1.2,
        duration: 1200,
        essential: true,
      });
      return;
    }

    const bounds = points.reduce(
      (acc, poi) => {
        return {
          minLon: Math.min(acc.minLon, poi.lon),
          maxLon: Math.max(acc.maxLon, poi.lon),
          minLat: Math.min(acc.minLat, poi.lat),
          maxLat: Math.max(acc.maxLat, poi.lat),
        };
      },
      {
        minLon: Infinity,
        maxLon: -Infinity,
        minLat: Infinity,
        maxLat: -Infinity,
      }
    );

    if (
      !Number.isFinite(bounds.minLon) ||
      !Number.isFinite(bounds.maxLon) ||
      !Number.isFinite(bounds.minLat) ||
      !Number.isFinite(bounds.maxLat)
    ) {
      return;
    }

    map.fitBounds(
      [
        [bounds.minLon, bounds.minLat],
        [bounds.maxLon, bounds.maxLat],
      ],
      {
        padding: { top: 80, bottom: 80, left: 80, right: 80 },
        duration: 1500,
      }
    );
  }, [isActive, points]);

  const initialViewState = { longitude: 0, latitude: 20, zoom: 1.2 };

  return (
    <div className="relative mt-6 overflow-hidden rounded-3xl border border-white/10 bg-slate-900/70 shadow-2xl">
      <div className="absolute inset-0 pointer-events-none bg-gradient-to-br from-indigo-600/10 via-transparent to-fuchsia-500/10" />
      <div className="absolute left-6 top-6 z-10 rounded-2xl bg-white/90 p-4 text-slate-900 shadow-lg">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-500">
          {isActive ? "Live map" : "World view"}
        </p>
        <p className="text-base font-semibold">
          {isActive
            ? "Tap a pin to preview each moment"
            : "Start a chat to drop curated pins"}
        </p>
      </div>
      <Map
        ref={mapRef}
        reuseMaps
        mapboxAccessToken={MAPBOX_TOKEN}
        initialViewState={initialViewState}
        mapStyle={
          isActive
            ? "mapbox://styles/mapbox/light-v11"
            : "mapbox://styles/mapbox/dark-v11"
        }
        style={{ height: 420 }}
      >
        <NavigationControl position="top-right" />
        {points.map((poi, i) => (
          <Marker
            key={`${poi.name}-${i}`}
            longitude={poi.lon}
            latitude={poi.lat}
            anchor="bottom"
          >
            <div
              onClick={() => setSelected(poi)}
              className="h-4 w-4 cursor-pointer rounded-full border-2 border-white bg-indigo-600 shadow-lg transition hover:scale-110"
            />
          </Marker>
        ))}
        {isActive && selected && (
          <Popup
            longitude={selected.lon}
            latitude={selected.lat}
            onClose={() => setSelected(null)}
            closeOnClick={false}
            offset={25}
            className="rounded-2xl !p-0 !shadow-xl"
          >
            <div className="rounded-2xl bg-white p-4 text-slate-900">
              <p className="text-sm font-semibold text-indigo-600">
                {selected.time}
              </p>
              <p className="text-base font-bold">{selected.name}</p>
              {selected.booking_required && (
                <a
                  href={selected.booking_url}
                  className="text-sm font-semibold text-indigo-600 underline"
                  target="_blank"
                  rel="noreferrer"
                >
                  Book here
                </a>
              )}
            </div>
          </Popup>
        )}
      </Map>
    </div>
  );
}

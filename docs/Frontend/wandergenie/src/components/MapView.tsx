import "mapbox-gl/dist/mapbox-gl.css";
import Map, { Marker, NavigationControl, Popup } from "react-map-gl/mapbox";
import trip from "../data/sampleTrip.json";
import { useMemo, useState } from "react";

const MAPBOX_TOKEN =
  process.env.REACT_APP_MAPBOX_TOKEN ?? "YOUR_MAPBOX_ACCESS_TOKEN"; // Replace with token

export default function MapView() {
  const [selected, setSelected] = useState<any>(null);
  const points = useMemo(
    () => trip.days.flatMap((d) => d.activities),
    []
  );

  return (
    <div className="relative mt-6 overflow-hidden rounded-3xl border border-white/10 bg-slate-900/70 shadow-2xl">
      <div className="absolute inset-0 pointer-events-none bg-gradient-to-br from-indigo-600/10 via-transparent to-fuchsia-500/10" />
      <div className="absolute left-6 top-6 z-10 rounded-2xl bg-white/90 p-4 text-slate-900 shadow-lg">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-500">
          Live map
        </p>
        <p className="text-base font-semibold">
          Tap a pin to preview each moment
        </p>
      </div>
      <Map
        reuseMaps
        mapboxAccessToken={MAPBOX_TOKEN}
        initialViewState={{
          longitude: -73.9857,
          latitude: 40.7484,
          zoom: 11,
        }}
        mapStyle="mapbox://styles/mapbox/light-v11"
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
        {selected && (
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

import {
  ArrowUpTrayIcon,
  CalendarDaysIcon,
  ShareIcon,
} from "@heroicons/react/24/outline";
import trip from "../data/sampleTrip.json";
import { generateICS } from "../utils/calendarExport";

export default function CalendarButton() {
  const downloadICS = (fileName: string) => {
    const ics = generateICS(trip);
    const blob = new Blob([ics], { type: "text/calendar;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const handleGoogleExport = () => {
    downloadICS("wander-genie-google.ics");
    window.open(
      "https://calendar.google.com/calendar/u/0/r/settings/export",
      "_blank",
      "noopener"
    );
  };

  const handleOutlookExport = () => {
    downloadICS("wander-genie-outlook.ics");
  };

  return (
    <div className="rounded-[32px] bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-500 p-6 text-white shadow-2xl">
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-4">
          <div className="rounded-2xl bg-white/20 p-3">
            <CalendarDaysIcon className="h-8 w-8" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-white/80">
              Final step
            </p>
            <p className="text-xl font-semibold">
              Sync WanderGenie with your real calendar
            </p>
            <p className="text-sm text-white/80">
              Export as .ics or share with your travel crew in one tap.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            onClick={handleGoogleExport}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-[24px] bg-white/90 px-4 py-3 text-base font-semibold text-indigo-700 shadow-lg shadow-indigo-900/20 transition hover:bg-white"
          >
            <ArrowUpTrayIcon className="h-5 w-5" />
            Google Calendar
          </button>
          <button
            onClick={handleOutlookExport}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-[24px] border border-white/40 bg-white/5 px-4 py-3 text-base font-semibold text-white transition hover:border-white/60"
          >
            <ShareIcon className="h-5 w-5" />
            Outlook (.ics)
          </button>
        </div>
      </div>
    </div>
  );
}

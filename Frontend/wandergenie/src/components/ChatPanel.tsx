import { useMemo, useState } from "react";
import { PaperAirplaneIcon, SparklesIcon } from "@heroicons/react/24/outline";

const INITIAL_SUGGESTIONS = [
  "Plan a foodie tour in Queens",
  "Add a cozy winter activity",
  "Balance outdoors and museums",
  "Find hidden cocktail bars",
];

const MODIFY_SUGGESTIONS = [
  "Add more food experiences",
  "Replace day 2 with museums",
  "Make it more relaxed",
  "Add teen-friendly activities",
];

type ChatPanelProps = {
  onPlan?: (prompt: string) => void;
  onModify?: (instruction: string) => void;
  isPlanning?: boolean;
  hasExistingTrip?: boolean;
};

export default function ChatPanel({ onPlan, onModify, isPlanning, hasExistingTrip }: ChatPanelProps) {
  const [prompt, setPrompt] = useState("");

  const isDisabled = prompt.trim().length === 0;

  const helperText = useMemo(() => {
    if (prompt.length > 120) {
      return "Long prompts work great — keep describing your vibe!";
    }
    if (prompt.length > 0) {
      return `${prompt.length}/200 characters`;
    }
    if (hasExistingTrip) {
      return "Modify your trip: 'Add more museums', 'Replace day 2 with beach', etc.";
    }
    return "Describe the mood, travel pace, or must-do experiences.";
  }, [prompt, hasExistingTrip]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isDisabled) return;
    
    // If there's an existing trip, call onModify, otherwise call onPlan
    if (hasExistingTrip && onModify) {
      onModify(prompt.trim());
    } else {
      onPlan?.(prompt.trim());
    }
    
    setPrompt("");
  };

  const handleSuggestion = (text: string) => {
    setPrompt(text);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-3xl border border-white/10 bg-white/80 p-5 shadow-xl shadow-indigo-900/10 backdrop-blur dark:bg-slate-900/60"
    >
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-indigo-600/10 p-3 text-indigo-600">
          <SparklesIcon className="h-6 w-6" />
        </div>
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            WanderGenie Copilot
          </p>
          <p className="text-lg font-semibold text-slate-900 dark:text-white">
            Tell me how you want this trip to feel ✨
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {(hasExistingTrip ? MODIFY_SUGGESTIONS : INITIAL_SUGGESTIONS).map((suggestion) => (
          <button
            type="button"
            key={suggestion}
            onClick={() => handleSuggestion(suggestion)}
            className="rounded-full border border-indigo-100 bg-white px-3 py-1 text-sm font-medium text-indigo-600 transition hover:border-indigo-400 hover:text-indigo-700 dark:border-slate-700 dark:bg-slate-800 dark:text-indigo-300"
          >
            {suggestion}
          </button>
        ))}
      </div>

      <div className="mt-5 flex flex-col gap-3 md:flex-row md:items-end">
        <div className="flex-1 rounded-2xl border border-slate-200 bg-white/90 px-4 py-3 focus-within:border-indigo-500 dark:border-slate-700 dark:bg-slate-800/60">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value.slice(0, 200))}
            rows={3}
            placeholder="E.g. 5 days in NYC with holiday markets, rooftop dinners, and wellness breaks."
            className="h-full w-full resize-none bg-transparent text-base text-slate-900 outline-none placeholder:text-slate-400 dark:text-slate-100"
          />
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            {helperText}
          </p>
        </div>

        <button
          type="submit"
          disabled={isDisabled || isPlanning}
          className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-indigo-600 to-fuchsia-500 px-6 py-3 font-semibold text-white shadow-lg shadow-indigo-500/30 transition hover:gap-3 disabled:cursor-not-allowed disabled:opacity-60 md:w-48"
        >
          {isPlanning 
            ? (hasExistingTrip ? "Updating..." : "Planning...") 
            : (hasExistingTrip ? "Modify trip" : "Send plan")}
          <PaperAirplaneIcon className="h-5 w-5" />
        </button>
      </div>
    </form>
  );
}

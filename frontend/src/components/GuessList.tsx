import type { GuessEntry } from "../types/api";

interface Props {
  guesses: GuessEntry[];
}

export function GuessList({ guesses }: Props) {
  const wrong = guesses.filter((g) => !g.correct);
  if (wrong.length === 0) return null;

  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-[11px] font-bold uppercase tracking-widest text-grass">
        Tentativi errati
      </p>
      <div className="flex flex-wrap gap-1.5">
        {wrong.map((g, i) => (
          <span
            key={i}
            className="px-3 py-1 rounded-full text-xs font-semibold
                       bg-[#fef0ef] border border-[#f5c4c0] text-[#9b3028] line-through"
          >
            {g.input}
          </span>
        ))}
      </div>
    </div>
  );
}

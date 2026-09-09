import { useState } from "react";
import { crestUrl } from "../api/client";
import { formatSeasonRange } from "../utils/format";
import type { CareerEntry } from "../types/api";

interface Props {
  career: CareerEntry[];
}

export function CareerTable({ career }: Props) {
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        {/* Header oro con gradiente — l'anima Panini della scheda */}
        <thead>
          <tr
            className="text-[#1a2e18] font-bold text-xs uppercase tracking-wide"
            style={{ background: "linear-gradient(135deg, #f5c518 0%, #fad54a 100%)" }}
          >
            <th className="text-left px-3 py-2.5 rounded-tl-xl font-display font-bold">Club</th>
            <th className="text-center px-2 py-2.5 whitespace-nowrap">Anni</th>
            <th className="text-right px-2 py-2.5">Pr.</th>
            <th className="text-right px-3 py-2.5 rounded-tr-xl">⚽</th>
          </tr>
        </thead>
        <tbody>
          {career.map((entry, i) => (
            <CareerRow key={i} entry={entry} index={i} total={career.length} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CareerRow({
  entry, index, total,
}: {
  entry: CareerEntry;
  index: number;
  total: number;
}) {
  const isLast = index === total - 1;
  const isEven = index % 2 === 0;

  return (
    <tr
      className={[
        isEven ? "bg-crema" : "bg-white/80",
        !isLast ? "border-b border-bordo/40" : "",
        "transition-colors duration-150 hover:bg-oro/10",
        isLast ? "rounded-b-xl" : "",
      ].join(" ")}
    >
      {/* Club: stemma + nome */}
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <Crest clubId={entry.club_id} clubName={entry.club_name} />
          <span className="truncate font-semibold text-loam text-sm">{entry.club_name}</span>
        </div>
      </td>

      {/* Anni */}
      <td className="px-2 py-2.5 text-center text-grass whitespace-nowrap font-mono text-xs tabular-nums">
        {formatSeasonRange(entry.season_start, entry.season_end)}
      </td>

      {/* Presenze */}
      <td className="px-2 py-2.5 text-right tabular-nums font-bold text-loam">
        {entry.appearances}
      </td>

      {/* Gol */}
      <td className="px-3 py-2.5 text-right tabular-nums font-bold text-verde">
        {entry.goals}
      </td>
    </tr>
  );
}

function Crest({ clubId, clubName }: { clubId: number; clubName: string }) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <span
        className="flex-shrink-0 w-7 h-7 rounded-full bg-bordo/40 flex items-center justify-center
                   text-xs font-bold text-verde border border-bordo/60"
      >
        {clubName[0]?.toUpperCase() ?? "?"}
      </span>
    );
  }

  return (
    <img
      src={crestUrl(clubId)}
      alt={clubName}
      width={28}
      height={28}
      className="flex-shrink-0 w-7 h-7 object-contain drop-shadow-sm"
      onError={() => setFailed(true)}
    />
  );
}

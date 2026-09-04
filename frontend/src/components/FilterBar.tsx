export interface FilterOption {
  value: string;
  label: string;
}

export function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: FilterOption[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="min-w-[170px]">
      <label className="mb-2 block text-[11px] uppercase tracking-[0.26em] text-slate-500">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-2xl border border-abyss-600/80 bg-black/20 px-3 py-2.5 text-sm text-slate-200 outline-none transition focus:border-cyan-accent focus:shadow-glow-cyan"
      >
        <option value="">All</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

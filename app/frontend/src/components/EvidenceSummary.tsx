function humanizeKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Unavailable";
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(formatValue).join(", ");
  return JSON.stringify(value);
}

/** Renders the backend's free-form AI evidence dict as labeled rows instead
 * of a raw JSON dump. The AI adapter's key set isn't fixed (Member 1's real
 * model may return different evidence keys than the mock), so this only
 * ever shows what the backend actually sent - it never invents field names
 * or values that weren't returned. */
export function EvidenceSummary({ evidence }: { evidence: Record<string, unknown> | null | undefined }) {
  const entries = Object.entries(evidence ?? {});
  if (entries.length === 0) {
    return <p className="text-sm text-slate-500">No AI evidence detail was provided for this detection.</p>;
  }
  return (
    <div className="space-y-1.5">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-start justify-between gap-4 text-sm">
          <span className="text-slate-500">{humanizeKey(key)}</span>
          <span className="max-w-[60%] text-right text-slate-200">{formatValue(value)}</span>
        </div>
      ))}
    </div>
  );
}

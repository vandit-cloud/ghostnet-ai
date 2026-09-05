export function formatConfidence(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
}

export function formatCoordinate(value: number | null | undefined, digits = 5): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(digits);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}


/** Human labels for the DETECTOR's five training classes.
 *
 * These are not the contract's classes and must not be confused with them.
 * The model separates wreck / plane / debris / ghost_pot / ghost_net; the
 * database contract stores only ghost_net / debris / natural / unknown, and
 * `TRAINING_TO_CONTRACT` in the AI package collapses the first four into
 * `debris`. So a submerged aircraft is stored as `debris` -- correctly, per a
 * frozen contract -- and the detector's own call survives only in
 * `evidence_summary.notes`.
 */
const DETECTOR_CLASS_LABELS: Record<string, string> = {
  wreck: "Wreck",
  plane: "Aircraft",
  debris: "Debris",
  ghost_pot: "Crab Pot",
  ghost_net: "Ghost Net",
};

/** The detector's finer class, or null when it is the same as the contract's.
 *
 * The AI package writes "detector class: wreck" into `notes`, sometimes after
 * a data-quality note and a pipe ("partial: 2% of the rows ... | detector
 * class: wreck"), and omits it entirely when the two agree. Parsed rather than
 * carried as its own column because the contract is frozen; adding a field is
 * a major version bump for the backend.
 */
export function detectorClass(evidence: Record<string, unknown> | null | undefined): string | null {
  const notes = evidence?.notes;
  if (typeof notes !== "string") return null;
  const match = notes.match(/detector class:\s*([a-z_]+)/i);
  return match ? match[1].toLowerCase() : null;
}

/** "Debris · Wreck" when the detector was more specific, "Debris" when not.
 *
 * Showing both is more honest than either alone: the contract class is what
 * the system stores and reports, and the detector class is what it actually
 * saw. Showing only the contract class makes a model that separates five
 * things look like it knows one word.
 */
export function formatDetectionClassWithDetector(
  contractClass: string,
  evidence: Record<string, unknown> | null | undefined
): string {
  const contract = contractClass
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  const detector = detectorClass(evidence);
  if (!detector || detector === contractClass) return contract;
  return `${contract} · ${DETECTOR_CLASS_LABELS[detector] ?? detector.replace(/_/g, " ")}`;
}

import clsx from "clsx";

import type { JobStatus, Priority, ReviewStatus, SurveyStatus, Uncertainty } from "@/types";

/* Badges, in Atlantic.
 *
 * The mockup's chips are square, mono, and distinguished by TREATMENT before
 * colour: filled imperial for the loud case, filled atlantic for the ordinary
 * one, an outline for the neutral, a dashed outline for the unknown. That
 * ordering is deliberate and is kept here -- a reviewer should be able to sort
 * a queue by glancing at chip weight, without relying on hue.
 *
 * Colour is the secondary cue, and it is the one place the palette goes past
 * the four hexes (see the `alert` note in tailwind.config.ts): the console has
 * to let an operator tell a FAILED job from a COMPLETED one, and the Atlantic
 * mockup contains no failure state to copy. */
const BADGE_BASE =
  "inline-block border px-2 py-1 font-mono text-[9.5px] uppercase tracking-[0.12em] align-middle";

const PRIORITY_STYLES: Record<Priority, string> = {
  critical: "border-alert-critical bg-alert-critical text-paper",
  high: "border-alert-high text-alert-high",
  medium: "border-ink-4 text-ink-2",
  low: "border-ink-4 border-dashed text-ink-3",
};

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <span className={clsx(BADGE_BASE, PRIORITY_STYLES[priority])}>{priority}</span>;
}

const REVIEW_LABELS: Record<ReviewStatus, string> = {
  pending: "Pending",
  unknown: "Unknown",
  accepted_artificial: "Accepted — Artificial",
  rejected_natural: "Rejected — Natural",
};

const REVIEW_STYLES: Record<ReviewStatus, string> = {
  // Pending is the state that needs a human, so it is the filled one.
  pending: "border-imperial bg-imperial text-paper",
  unknown: "border-alert-unknown border-dashed text-alert-unknown",
  accepted_artificial: "border-emerald-500 text-emerald-500",
  rejected_natural: "border-ink-4 text-ink-3",
};

export function ReviewStatusBadge({ status }: { status: ReviewStatus }) {
  return <span className={clsx(BADGE_BASE, REVIEW_STYLES[status])}>{REVIEW_LABELS[status]}</span>;
}

const UNCERTAINTY_STYLES: Record<Uncertainty, string> = {
  low: "text-emerald-500",
  medium: "text-alert-high",
  high: "text-alert-critical",
};

export function UncertaintyLabel({ level }: { level: Uncertainty | null }) {
  if (!level) return <span className="text-ink-4">—</span>;
  return <span className={clsx("font-medium capitalize", UNCERTAINTY_STYLES[level])}>{level}</span>;
}

const SURVEY_STATUS_STYLES: Record<SurveyStatus, string> = {
  UPLOADED: "border-ink-4 text-ink-2",
  VALIDATING: "border-atlantic text-atlantic",
  PROCESSING: "border-imperial bg-imperial text-paper",
  PARTIAL: "border-alert-high text-alert-high",
  COMPLETED: "border-emerald-500 text-emerald-500",
  FAILED: "border-alert-critical bg-alert-critical text-paper",
  ARCHIVED: "border-ink-4 border-dashed text-ink-3",
};

export function SurveyStatusBadge({ status }: { status: SurveyStatus }) {
  return <span className={clsx(BADGE_BASE, SURVEY_STATUS_STYLES[status])}>{status}</span>;
}

const JOB_STATUS_STYLES: Record<JobStatus, string> = {
  QUEUED: "border-ink-4 text-ink-2",
  VALIDATING: "border-atlantic text-atlantic",
  PROCESSING: "border-imperial bg-imperial text-paper",
  PARTIAL: "border-alert-high text-alert-high",
  COMPLETED: "border-emerald-500 text-emerald-500",
  FAILED: "border-alert-critical bg-alert-critical text-paper",
  CANCELLED: "border-ink-4 border-dashed text-ink-3",
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return <span className={clsx(BADGE_BASE, JOB_STATUS_STYLES[status])}>{status}</span>;
}

/* The detection class chip. The mockup gives ghost_net the imperial fill and
 * everything else the quieter atlantic, because ghost_net is the class that
 * carries the segmentation head and the review gate -- it is the one the whole
 * project is about, and the palette says so. */
const CLASS_STYLES: Record<string, string> = {
  ghost_net: "border-imperial bg-imperial text-paper",
  ghost_pot: "border-atlantic bg-atlantic text-paper",
  wreck: "border-atlantic bg-atlantic text-paper",
  plane: "border-atlantic bg-atlantic text-paper",
  debris: "border-ink-4 text-ink-2",
};

export function DetectionClassBadge({ detectionClass }: { detectionClass: string }) {
  const style = CLASS_STYLES[detectionClass] ?? "border-ink-4 border-dashed text-ink-3";
  return <span className={clsx(BADGE_BASE, style)}>{detectionClass.replace(/_/g, " ")}</span>;
}

import clsx from "clsx";

import type { JobStatus, Priority, ReviewStatus, SurveyStatus, Uncertainty } from "@/types";

const BADGE_BASE = "rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.22em]";

const PRIORITY_STYLES: Record<Priority, string> = {
  critical: "bg-alert-critical/15 text-alert-critical border-alert-critical/40 shadow-glow-critical",
  high: "bg-alert-high/15 text-alert-high border-alert-high/40",
  medium: "bg-alert-medium/15 text-alert-medium border-alert-medium/40",
  low: "bg-alert-low/15 text-alert-low border-alert-low/40",
};

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <span className={clsx(BADGE_BASE, PRIORITY_STYLES[priority])}>{priority}</span>;
}

const REVIEW_LABELS: Record<ReviewStatus, string> = {
  pending: "Pending",
  unknown: "Unknown",
  accepted_artificial: "Accepted - Artificial",
  rejected_natural: "Rejected - Natural",
};

const REVIEW_STYLES: Record<ReviewStatus, string> = {
  pending: "bg-cyan-accent/10 text-cyan-accent border-cyan-accent/40",
  unknown: "bg-alert-unknown/10 text-alert-unknown border-alert-unknown/40",
  accepted_artificial: "bg-emerald-500/10 text-emerald-300 border-emerald-500/40",
  rejected_natural: "bg-slate-600/20 text-slate-400 border-slate-600/40",
};

export function ReviewStatusBadge({ status }: { status: ReviewStatus }) {
  return <span className={clsx(BADGE_BASE, REVIEW_STYLES[status])}>{REVIEW_LABELS[status]}</span>;
}

const UNCERTAINTY_STYLES: Record<Uncertainty, string> = {
  low: "text-emerald-300",
  medium: "text-alert-medium",
  high: "text-alert-critical",
};

export function UncertaintyLabel({ level }: { level: Uncertainty | null }) {
  if (!level) return <span className="text-slate-500">-</span>;
  return <span className={clsx("font-medium capitalize", UNCERTAINTY_STYLES[level])}>{level}</span>;
}

const SURVEY_STATUS_STYLES: Record<SurveyStatus, string> = {
  UPLOADED: "bg-slate-500/10 text-slate-300 border-slate-500/40",
  VALIDATING: "bg-cyan-accent/10 text-cyan-accent border-cyan-accent/40",
  PROCESSING: "bg-cyan-accent/10 text-cyan-accent border-cyan-accent/40",
  PARTIAL: "bg-alert-medium/10 text-alert-medium border-alert-medium/40",
  COMPLETED: "bg-emerald-500/10 text-emerald-300 border-emerald-500/40",
  FAILED: "bg-alert-critical/10 text-alert-critical border-alert-critical/40",
  ARCHIVED: "bg-slate-700/30 text-slate-400 border-slate-700/50",
};

export function SurveyStatusBadge({ status }: { status: SurveyStatus }) {
  return <span className={clsx(BADGE_BASE, SURVEY_STATUS_STYLES[status])}>{status}</span>;
}

const JOB_STATUS_STYLES: Record<JobStatus, string> = {
  QUEUED: "bg-slate-500/10 text-slate-300 border-slate-500/40",
  VALIDATING: "bg-cyan-accent/10 text-cyan-accent border-cyan-accent/40 shadow-glow-cyan",
  PROCESSING: "bg-cyan-accent/10 text-cyan-accent border-cyan-accent/40 shadow-glow-cyan",
  PARTIAL: "bg-alert-medium/10 text-alert-medium border-alert-medium/40",
  COMPLETED: "bg-emerald-500/10 text-emerald-300 border-emerald-500/40",
  FAILED: "bg-alert-critical/10 text-alert-critical border-alert-critical/40 shadow-glow-critical",
  CANCELLED: "bg-slate-700/30 text-slate-400 border-slate-700/50",
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return <span className={clsx(BADGE_BASE, JOB_STATUS_STYLES[status])}>{status}</span>;
}

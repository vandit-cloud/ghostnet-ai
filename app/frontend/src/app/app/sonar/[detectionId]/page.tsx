"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { PriorityBadge, UncertaintyLabel } from "@/components/Badges";
import { EvidenceSummary } from "@/components/EvidenceSummary";
import { SonarViewer } from "@/components/SonarViewer";
import { ErrorState, LoadingSkeleton } from "@/components/States";
import { useDetection } from "@/features/detections/hooks";
import {
  formatConfidence,
  formatCoordinate,
  formatDetectionClassWithDetector,
} from "@/utils/format";

export default function SonarInvestigationPage() {
  const params = useParams<{ detectionId: string }>();
  const { data: detection, isLoading, isError, refetch } = useDetection(params.detectionId);

  if (isLoading) {
    return (
      <AppShell title="Sonar Investigation">
        <LoadingSkeleton rows={4} label="Loading sonar workspace…" />
      </AppShell>
    );
  }

  if (isError || !detection) {
    return (
      <AppShell title="Sonar Investigation">
        <ErrorState message="Unable to load detection." onRetry={() => refetch()} />
      </AppShell>
    );
  }

  return (
    <AppShell title={`Sonar Investigation — ${detection.detection_ref}`}>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Sonar Image (bounding box overlay)</h3>
          <SonarViewer frameId={detection.frame_id} bbox={detection.bbox} />
        </div>

        <div className="space-y-4 panel p-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Class</p>
            <p className="text-slate-100">
              {formatDetectionClassWithDetector(detection.detection_class, detection.evidence_summary)}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Confidence</p>
            <p className="text-slate-100">{formatConfidence(detection.calibrated_confidence)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Uncertainty</p>
            <UncertaintyLabel level={detection.uncertainty} />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Priority</p>
            <PriorityBadge priority={detection.priority} />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Location</p>
            <p className="text-slate-100">
              {formatCoordinate(detection.latitude)}, {formatCoordinate(detection.longitude)}
            </p>
            {detection.latitude !== null && (
              <Link
                href={`/app/map?survey_id=${detection.survey_id}&focus=${detection.id}`}
                className="mt-1 inline-block text-xs text-cyan-accent hover:underline"
              >
                View on GIS Map →
              </Link>
            )}
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Mask</p>
            <p className="text-slate-400">{detection.mask_reference ?? "Not available for this detection."}</p>
          </div>

          {/* "Why did the system flag this?" is the question this workspace
              exists to answer (master plan E7/E14), and it was the one thing
              the panel did not say -- the detector's own finer class, the
              artificial-vs-natural verification and the shadow reasoning were
              all being computed and then shown only on the detections page.
              EvidenceSummary renders exactly what the backend sent and nothing
              else, so an item that was not computed says so rather than being
              filled in. */}
          <div className="border-t border-abyss-700 pt-4">
            <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">AI Evidence</p>
            <EvidenceSummary evidence={detection.evidence_summary} />
          </div>

          <div className="space-y-1.5 border-t border-abyss-700 pt-4 text-sm">
            <Row label="Localization" value={detection.localization_method ?? "Unavailable"} />
            <Row
              label="Position error"
              value={
                detection.position_error_m !== null
                  ? `±${detection.position_error_m} m`
                  : "Unavailable"
              }
            />
            <Row
              label="Dimensions"
              value={
                detection.dimensions.width && detection.dimensions.length
                  ? `${detection.dimensions.width} × ${detection.dimensions.length} m (${detection.dimensions.status ?? "estimated"})`
                  : "Unavailable"
              }
            />
            <Row label="Model" value={detection.model_version ?? "Unavailable"} />
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-slate-500">{label}</span>
      <span className="max-w-[60%] text-right text-slate-200">{value}</span>
    </div>
  );
}

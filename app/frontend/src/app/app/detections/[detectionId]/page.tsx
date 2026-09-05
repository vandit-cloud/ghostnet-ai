"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ExpandableSection } from "@/components/Accordion";
import { PriorityBadge, ReviewStatusBadge, UncertaintyLabel } from "@/components/Badges";
import { EvidenceSummary } from "@/components/EvidenceSummary";
import { ErrorState, LoadingSkeleton } from "@/components/States";
import { SonarViewer } from "@/components/SonarViewer";
import { useDetection, useDetectionReviews } from "@/features/detections/hooks";
import { formatConfidence, formatCoordinate, formatDateTime, formatDetectionClassWithDetector } from "@/utils/format";

export default function DetectionDetailPage() {
  const params = useParams<{ detectionId: string }>();
  const { data: detection, isLoading, isError, refetch } = useDetection(params.detectionId);
  const { data: reviews } = useDetectionReviews(params.detectionId);

  if (isLoading) {
    return (
      <AppShell title="Detection Detail">
        <LoadingSkeleton rows={5} label="Loading detection…" />
      </AppShell>
    );
  }

  if (isError || !detection) {
    return (
      <AppShell title="Detection Detail">
        <ErrorState message="Unable to load detection." onRetry={() => refetch()} />
      </AppShell>
    );
  }

  return (
    <AppShell title={detection.detection_ref}>
      {/* primary focus: what / confidence / priority, immediately visible */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <span className="text-xl font-semibold capitalize text-slate-100">
          {formatDetectionClassWithDetector(detection.detection_class, detection.evidence_summary)}
        </span>
        <span className="text-xl font-semibold text-slate-100">{formatConfidence(detection.calibrated_confidence)}</span>
        <PriorityBadge priority={detection.priority} />
        <ReviewStatusBadge status={detection.review_status} />
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        {detection.latitude !== null && (
          <Link
            href={`/app/map?survey_id=${detection.survey_id}&focus=${detection.id}`}
            className="rounded-md border border-abyss-600 px-3 py-1.5 text-sm text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
          >
            View on Map
          </Link>
        )}
        <Link
          href={`/app/sonar/${detection.id}`}
          className="rounded-md border border-abyss-600 px-3 py-1.5 text-sm text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
        >
          View Sonar
        </Link>
        <Link
          href={`/app/review/${detection.id}`}
          className="rounded-md border border-abyss-600 px-3 py-1.5 text-sm text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
        >
          Open Review
        </Link>
        <Link
          href={`/app/reports?survey_id=${detection.survey_id}&detection_id=${detection.id}`}
          className="rounded-md border border-abyss-600 px-3 py-1.5 text-sm text-slate-200 hover:border-cyan-accent/50 hover:text-cyan-accent"
        >
          Include in Report
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Sonar Evidence</h3>
          <SonarViewer frameId={detection.frame_id} bbox={detection.bbox} />
        </div>

        {/* everything else: progressively disclosed, one section open by default */}
        <div className="space-y-3">
          <ExpandableSection title="AI Evidence" defaultOpen>
            <Row label="AI Confidence (raw)" value={formatConfidence(detection.raw_score)} />
            <Row label="Calibrated Confidence" value={formatConfidence(detection.calibrated_confidence)} />
            <Row label="Uncertainty" value={<UncertaintyLabel level={detection.uncertainty} />} />
            <div className="mt-2 border-t border-abyss-700 pt-2">
              <EvidenceSummary evidence={detection.evidence_summary} />
            </div>
          </ExpandableSection>

          <ExpandableSection title="Geospatial Details">
            <Row label="Latitude" value={formatCoordinate(detection.latitude)} />
            <Row label="Longitude" value={formatCoordinate(detection.longitude)} />
            <Row label="Position Error" value={detection.position_error_m ? `±${detection.position_error_m} m` : "Unavailable"} />
            <Row label="Localization" value={detection.localization_method ?? "Unavailable"} />
          </ExpandableSection>

          <ExpandableSection title="Sonar Quality">
            <Row label="Width" value={detection.dimensions.width ? `${detection.dimensions.width} m (${detection.dimensions.status ?? "estimated"})` : "Unavailable"} />
            <Row label="Length" value={detection.dimensions.length ? `${detection.dimensions.length} m (${detection.dimensions.status ?? "estimated"})` : "Unavailable"} />
            <Row label="Area" value={detection.dimensions.area ? `${detection.dimensions.area} m²` : "Unavailable"} />
            <Row label="Depth" value={detection.depth ? `${detection.depth} m` : "Unavailable"} />
          </ExpandableSection>

          <ExpandableSection title="Model Information">
            <Row label="Model Version" value={detection.model_version ?? "Unavailable"} />
            <Row label="Detected At" value={formatDateTime(detection.created_at)} />
          </ExpandableSection>

          <ExpandableSection title="Technical Metadata">
            <Row label="Detection ID" value={<span className="font-mono text-xs">{detection.id}</span>} />
            <Row label="Detection Ref" value={<span className="font-mono text-xs">{detection.detection_ref}</span>} />
            <Row label="Frame ID" value={<span className="font-mono text-xs">{detection.frame_id}</span>} />
            <Row label="Survey ID" value={<span className="font-mono text-xs">{detection.survey_id}</span>} />
            <Row label="Last Updated" value={formatDateTime(detection.updated_at)} />
          </ExpandableSection>

          <ExpandableSection title="Review History">
            {!reviews || reviews.length === 0 ? (
              <p className="text-sm text-slate-500">No review decisions recorded yet.</p>
            ) : (
              <div className="space-y-3">
                {reviews.map((r) => (
                  <div key={r.id} className="border-b border-abyss-700 pb-2 last:border-0 last:pb-0">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium capitalize text-slate-200">{r.decision.replace("_", " ")}</span>
                      <span className="text-xs text-slate-500">{formatDateTime(r.created_at)}</span>
                    </div>
                    {r.reviewer && <p className="text-xs text-slate-500">by {r.reviewer}</p>}
                    {r.note && <p className="mt-1 text-sm text-slate-400">{r.note}</p>}
                  </div>
                ))}
              </div>
            )}
          </ExpandableSection>
        </div>
      </div>
    </AppShell>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-200">{value}</span>
    </div>
  );
}

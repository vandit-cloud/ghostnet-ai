"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { PriorityBadge, UncertaintyLabel } from "@/components/Badges";
import { SonarViewer } from "@/components/SonarViewer";
import { ErrorState, LoadingSkeleton } from "@/components/States";
import { useDetection } from "@/features/detections/hooks";
import { formatConfidence, formatCoordinate } from "@/utils/format";

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
            <p className="capitalize text-slate-100">{detection.detection_class.replace("_", " ")}</p>
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
        </div>
      </div>
    </AppShell>
  );
}

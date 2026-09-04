"use client";

import dynamic from "next/dynamic";
import { useParams, useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { EvidenceSummary } from "@/components/EvidenceSummary";
import { ReviewPanel } from "@/components/ReviewPanel";
import { SonarViewer } from "@/components/SonarViewer";
import { ErrorState, LoadingSkeleton } from "@/components/States";
import { useToastStore } from "@/components/Toast";
import { useDetection, useDetectionReviews, useReviewDetection } from "@/features/detections/hooks";
import type { ReviewStatus } from "@/types";
import { formatConfidence } from "@/utils/format";

const MapView = dynamic(() => import("@/components/MapView").then((mod) => mod.MapView), {
  ssr: false,
  loading: () => <LoadingSkeleton rows={1} />,
});

export default function ReviewWorkspacePage() {
  const params = useParams<{ detectionId: string }>();
  const router = useRouter();
  const push = useToastStore((s) => s.push);

  const { data: detection, isLoading, isError, refetch } = useDetection(params.detectionId);
  const { data: reviews } = useDetectionReviews(params.detectionId);
  const reviewMutation = useReviewDetection(params.detectionId);

  async function handleSubmit(decision: ReviewStatus, note: string) {
    try {
      await reviewMutation.mutateAsync({ decision, note: note || undefined });
      push("Review saved.", "success");
      router.push("/app/review");
    } catch {
      push("Unable to save review.", "error");
    }
  }

  if (isLoading) {
    return (
      <AppShell title="Review">
        <LoadingSkeleton rows={4} label="Loading detection…" />
      </AppShell>
    );
  }

  if (isError || !detection) {
    return (
      <AppShell title="Review">
        <ErrorState message="Unable to load detection." onRetry={() => refetch()} />
      </AppShell>
    );
  }

  const hasLocation = detection.latitude !== null && detection.longitude !== null;

  return (
    <AppShell title={`Review — ${detection.detection_ref}`}>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Sonar Image</h3>
          <SonarViewer frameId={detection.frame_id} bbox={detection.bbox} />
        </div>

        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Map Location</h3>
          {hasLocation ? (
            <div className="h-64 overflow-hidden rounded-lg border border-abyss-600">
              <MapView
                markers={[
                  {
                    detection_id: detection.id,
                    detection_ref: detection.detection_ref,
                    detection_class: detection.detection_class,
                    latitude: detection.latitude as number,
                    longitude: detection.longitude as number,
                    priority: detection.priority,
                    review_status: detection.review_status,
                    calibrated_confidence: detection.calibrated_confidence,
                    uncertainty: detection.uncertainty,
                    position_error_m: detection.position_error_m,
                    depth: detection.depth,
                    created_at: detection.created_at,
                  },
                ]}
                bounds={null}
              />
            </div>
          ) : (
            <div className="flex h-64 items-center justify-center panel text-sm text-slate-500">
              No location available for this detection.
            </div>
          )}

          <div className="mt-4 space-y-1 panel p-4 text-sm">
            <p className="text-slate-400">
              Confidence: <span className="text-slate-100">{formatConfidence(detection.calibrated_confidence)}</span>
            </p>
            <p className="text-slate-400">
              Uncertainty: <span className="capitalize text-slate-100">{detection.uncertainty ?? "—"}</span>
            </p>
            <div className="border-t border-abyss-700 pt-2">
              <p className="mb-1.5 text-xs uppercase tracking-wide text-slate-500">Evidence</p>
              <EvidenceSummary evidence={detection.evidence_summary} />
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <ReviewPanel onSubmit={handleSubmit} isSubmitting={reviewMutation.isPending} />

          {reviews && reviews.length > 0 && (
            <div className="panel p-4">
              <h3 className="mb-2 text-sm font-semibold text-slate-200">Review History</h3>
              <div className="space-y-2">
                {reviews.map((r) => (
                  <div key={r.id} className="border-t border-abyss-700 pt-2 text-xs text-slate-400">
                    <p className="capitalize text-slate-200">{r.decision.replace("_", " ")}</p>
                    {r.note && <p className="mt-0.5">{r.note}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}

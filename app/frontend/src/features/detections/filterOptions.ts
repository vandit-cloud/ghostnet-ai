import type { FilterOption } from "@/components/FilterBar";

// One list per filter, shared by the Detections, Map and Reports pages so a
// report built from a filter offers exactly the values the queue does.

export const CLASS_OPTIONS: FilterOption[] = [
  { value: "ghost_net", label: "Ghost Net" },
  { value: "debris", label: "Debris" },
  { value: "natural_object", label: "Natural Object" },
  { value: "unknown", label: "Unknown" },
];

export const PRIORITY_OPTIONS: FilterOption[] = [
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

export const REVIEW_OPTIONS: FilterOption[] = [
  { value: "pending", label: "Pending" },
  { value: "unknown", label: "Unknown" },
  { value: "accepted_artificial", label: "Accepted — Artificial" },
  { value: "rejected_natural", label: "Rejected — Natural" },
];

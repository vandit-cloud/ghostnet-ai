import { describe, expect, it } from "vitest";

import { formatBytes, formatConfidence, formatCoordinate, formatDateTime } from "@/utils/format";

describe("formatConfidence", () => {
  it("renders a placeholder for null/undefined", () => {
    expect(formatConfidence(null)).toBe("—");
    expect(formatConfidence(undefined)).toBe("—");
  });

  it("renders a rounded percentage", () => {
    expect(formatConfidence(0.934)).toBe("93%");
  });
});

describe("formatCoordinate", () => {
  it("renders a placeholder for missing coordinates", () => {
    expect(formatCoordinate(null)).toBe("—");
  });

  it("formats with the requested precision", () => {
    expect(formatCoordinate(20.123456789, 4)).toBe("20.1235");
  });
});

describe("formatDateTime", () => {
  it("renders a placeholder for missing/invalid dates", () => {
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime("not-a-date")).toBe("—");
  });
});

describe("formatBytes", () => {
  it("formats bytes below 1KB directly", () => {
    expect(formatBytes(500)).toBe("500 B");
  });

  it("formats larger sizes with units", () => {
    expect(formatBytes(1024 * 1024 * 2)).toBe("2.0 MB");
  });
});

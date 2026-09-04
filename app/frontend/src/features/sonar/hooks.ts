"use client";

import { useEffect, useState } from "react";

import { apiFetchBlob } from "@/api/client";

export function useFrameImage(frameId: string | undefined) {
  const [url, setUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    if (!frameId) return;
    let objectUrl: string | null = null;
    let cancelled = false;

    setIsLoading(true);
    setIsError(false);

    apiFetchBlob(`/frames/${frameId}/image`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setIsError(true);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [frameId]);

  return { url, isLoading, isError };
}

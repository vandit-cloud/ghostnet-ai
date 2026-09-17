"use client";

import { Component, Suspense, type ReactNode } from "react";
import { useGLTF } from "@react-three/drei";

/** Swallows a failed GLTF fetch/parse and renders the primitive stand-in.
 *
 * This is what makes the scene work BEFORE any .glb exists: drop a file into
 * public/models and it is picked up on the next load with no code change, and
 * if it is missing or malformed the hero degrades to the box-and-cone vessel
 * instead of blanking the page with an error. */
class ModelBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    if (process.env.NODE_ENV !== "production") {
      console.info("[hero] model unavailable, using primitive stand-in:", error);
    }
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function GltfModel({ url }: { url: string }) {
  const { scene } = useGLTF(url, true);
  return <primitive object={scene.clone(true)} />;
}

/** Renders `url` if it loads, otherwise `fallback`. */
export function ModelSlot({ url, fallback }: { url: string; fallback: ReactNode }) {
  return (
    <ModelBoundary fallback={fallback}>
      <Suspense fallback={fallback}>
        <GltfModel url={url} />
      </Suspense>
    </ModelBoundary>
  );
}

export const VESSEL_MODEL_URL = "/models/vessel.glb";
export const TOWFISH_MODEL_URL = "/models/towfish.glb";

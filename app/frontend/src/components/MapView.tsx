"use client";

import L from "leaflet";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Circle,
  MapContainer,
  Marker,
  Polygon,
  Polyline,
  Popup,
  Rectangle,
  ScaleControl,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";

import { MAP_CLUSTER_DISABLED_KEY } from "@/utils/settings";
import type { MapMarker as MapMarkerType, Priority, TrackPoint } from "@/types";
import { formatConfidence, formatCoordinate, formatDateTime } from "@/utils/format";
import { bearingDeg, destinationPoint, haversineMeters } from "@/utils/geo";
import { ALERT, ATLANTIC, IMPERIAL, PAPER } from "@/utils/palette";
import clsx from "clsx";

const PRIORITY_COLORS: Record<Priority, string> = {
  critical: ALERT.critical,
  high: ALERT.high,
  medium: ALERT.medium,
  low: ALERT.low,
};

const CLASS_LABELS: Record<string, string> = {
  ghost_net: "G",
  debris: "D",
  natural_object: "O",
  unknown: "?",
};

const FOCUS_NEARBY_RADIUS_M = 200;
const BASEMAP_STORAGE_KEY = "ghostnet_map_basemap";

const BASEMAPS = {
  standard: {
    label: "Standard",
    layers: [
      {
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
    ],
  },
  marine: {
    label: "Marine",
    layers: [
      {
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
      {
        url: "https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openseamap.org">OpenSeaMap</a> contributors',
        maxZoom: 18,
        opacity: 0.88,
      },
    ],
  },
  dark: {
    label: "Dark",
    layers: [
      {
        // Free OSM tiles with an in-app dark treatment so the UI can keep a
        // sonar-style mode without depending on paid dark basemap providers.
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
    ],
  },
} as const;

type BasemapKey = keyof typeof BASEMAPS;

function markerIcon(detectionClass: string, priority: Priority, selected: boolean, critical: boolean, focused: boolean) {
  const color = PRIORITY_COLORS[priority] ?? PRIORITY_COLORS.low;
  const label = CLASS_LABELS[detectionClass] ?? "?";
  const size = selected ? 28 : critical ? 20 : 18;
  const pulse =
    critical && !selected
      ? `<div style="position:absolute;inset:-6px;border-radius:50%;border:2px solid ${color};opacity:0.55;animation:ghostnet-pulse 1.6s ease-out infinite;"></div>`
      : "";
  const opacity = focused ? 1 : 0.35;

  return L.divIcon({
    className: "",
    html: `
      <div style="position:relative;width:${size}px;height:${size}px;opacity:${opacity};">
        ${pulse}
        <div style="
          width:${size}px;height:${size}px;border-radius:50%;
          background:${color};
          border:2px solid ${selected ? IMPERIAL : ATLANTIC};
          box-shadow:0 1px 4px rgba(0,0,0,0.6);
          display:flex;align-items:center;justify-content:center;
          font:700 ${Math.round(size * 0.46)}px/1 ui-sans-serif,system-ui;
          color:${PAPER};
        ">${label}</div>
      </div>
      <style>
        @keyframes ghostnet-pulse {
          0% { transform: scale(0.8); opacity: 0.6; }
          100% { transform: scale(1.6); opacity: 0; }
        }
      </style>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function clusterIcon(cluster: { getChildCount: () => number }) {
  const count = cluster.getChildCount();
  const size = count < 10 ? 34 : count < 50 ? 42 : 50;

  return L.divIcon({
    className: "",
    html: `<div style="
      width:${size}px;height:${size}px;border-radius:50%;
      background:${PAPER};
      border:2px solid ${IMPERIAL};
      display:flex;align-items:center;justify-content:center;
      font:700 13px ui-sans-serif,system-ui;color:${IMPERIAL};
      backdrop-filter:blur(1px);
    ">${count}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function vesselIcon(headingDeg: number) {
  return L.divIcon({
    className: "",
    html: `
      <div style="transform: rotate(${headingDeg}deg); width:22px; height:22px;">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <path d="M12 2 L19 20 L12 16 L5 20 Z" fill="${IMPERIAL}" stroke="${PAPER}" stroke-width="1.4" />
        </svg>
      </div>
    `,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function buildCorridor(track: TrackPoint[]): [number, number][] | null {
  const usable = track.filter((point): point is TrackPoint & { range: number } => typeof point.range === "number" && point.range > 0);
  if (usable.length < 2) return null;

  const left: [number, number][] = [];
  const right: [number, number][] = [];

  for (let i = 0; i < usable.length; i++) {
    const current = usable[i];
    const previous = usable[i - 1] ?? current;
    const next = usable[i + 1] ?? current;
    const heading = bearingDeg(previous.latitude, previous.longitude, next.latitude, next.longitude);

    left.push(destinationPoint(current.latitude, current.longitude, heading - 90, current.range));
    right.push(destinationPoint(current.latitude, current.longitude, heading + 90, current.range));
  }

  return [...left, ...right.reverse()];
}

function NorthArrow() {
  return (
    <div className="pointer-events-none absolute right-3 top-3 z-[1000] flex h-9 w-9 items-center justify-center rounded-full border border-abyss-600 bg-abyss-900/85 backdrop-blur">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
        <path d="M12 2 L17 22 L12 17 L7 22 Z" fill={IMPERIAL} />
      </svg>
    </div>
  );
}

function BasemapSwitcher({ value, onChange }: { value: BasemapKey; onChange: (next: BasemapKey) => void }) {
  return (
    <div className="pointer-events-auto absolute right-3 top-14 z-[1000] flex overflow-hidden rounded-md border border-abyss-600 bg-abyss-900/90 text-xs backdrop-blur">
      {(Object.keys(BASEMAPS) as BasemapKey[]).map((key) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          className={
            value === key
              ? "bg-cyan-accent/15 px-2.5 py-1.5 text-cyan-accent"
              : "px-2.5 py-1.5 text-slate-400 hover:text-slate-200"
          }
        >
          {BASEMAPS[key].label}
        </button>
      ))}
    </div>
  );
}

function CursorReadout({
  onChange,
}: {
  onChange: (value: { latitude: number; longitude: number } | null) => void;
}) {
  useMapEvents({
    mousemove(event) {
      onChange({ latitude: event.latlng.lat, longitude: event.latlng.lng });
    },
    mouseout() {
      onChange(null);
    },
  });

  return null;
}

function FitAndFocus({
  bounds,
  focusPoint,
}: {
  bounds: [[number, number], [number, number]] | null;
  focusPoint: [number, number] | null;
}) {
  const map = useMap();
  const hasFitOnce = useRef(false);

  useEffect(() => {
    if (focusPoint) {
      map.flyTo(focusPoint, Math.max(map.getZoom(), 14), { duration: 0.8 });
    } else if (bounds && !hasFitOnce.current) {
      map.fitBounds(bounds, { padding: [48, 48] });
      hasFitOnce.current = true;
    }
  }, [bounds, focusPoint, map]);

  return null;
}

/** Keeps a single-marker view (no bounds/focusPoint to fit against) centred on
 * that marker even if the panel around the map resizes after the map first
 * mounts -- Leaflet caches the container size at init and otherwise leaves
 * the view (and the marker) drifted off, sometimes past the clipped edge. */
function RecenterOnResize({ center, zoom, active }: { center: [number, number]; zoom: number; active: boolean }) {
  const map = useMap();

  useEffect(() => {
    if (!active) return undefined;

    const container = map.getContainer();
    map.invalidateSize();
    map.setView(center, zoom, { animate: false });

    const observer = new ResizeObserver(() => {
      map.invalidateSize();
      map.setView(center, zoom, { animate: false });
    });
    observer.observe(container);

    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, center[0], center[1], zoom, map]);

  return null;
}

export function MapView({
  markers,
  bounds,
  track = [],
  selectedId,
  onSelect,
  vesselPosition,
  compact = false,
}: {
  markers: MapMarkerType[];
  bounds: { min_lat: number; min_lon: number; max_lat: number; max_lon: number } | null;
  track?: TrackPoint[];
  selectedId?: string;
  onSelect?: (detectionId: string) => void;
  vesselPosition?: { latitude: number; longitude: number; headingDeg: number } | null;
  /** Small, single-purpose embed (e.g. a detail panel's "Map Location" card):
   * drops the cursor readout and basemap switcher so they stop crowding the
   * native zoom control, and guarantees the lone marker stays centred. */
  compact?: boolean;
}) {
  const leafletBounds = useMemo<[[number, number], [number, number]] | null>(() => {
    if (!bounds) return null;
    return [
      [bounds.min_lat, bounds.min_lon],
      [bounds.max_lat, bounds.max_lon],
    ];
  }, [bounds]);

  const trackLine = useMemo<[number, number][]>(
    () => track.map((point) => [point.latitude, point.longitude] as [number, number]),
    [track]
  );

  const corridor = useMemo(() => buildCorridor(track), [track]);

  const focusPoint = useMemo<[number, number] | null>(() => {
    if (!selectedId) return null;
    const marker = markers.find((item) => item.detection_id === selectedId);
    return marker ? [marker.latitude, marker.longitude] : null;
  }, [selectedId, markers]);

  const selectedMarker = useMemo(
    () => markers.find((item) => item.detection_id === selectedId) ?? null,
    [markers, selectedId]
  );

  function isFocused(marker: MapMarkerType): boolean {
    if (!selectedMarker) return true;
    if (marker.detection_id === selectedMarker.detection_id) return true;

    return (
      haversineMeters(selectedMarker.latitude, selectedMarker.longitude, marker.latitude, marker.longitude) <=
      FOCUS_NEARBY_RADIUS_M
    );
  }

  const center: [number, number] = markers.length
    ? [markers[0].latitude, markers[0].longitude]
    : trackLine.length
      ? trackLine[0]
      : [15, 75];

  const zoom = markers.length || trackLine.length ? 12 : 4;

  // The one-marker, no-bounds, no-track case (a detail panel's small "Map
  // Location" card) is the one nothing else re-centres for -- FitAndFocus
  // only acts on `bounds` or a `focusPoint` from `selectedId`, neither of
  // which this shape provides.
  const isSingleMarkerFocus = markers.length === 1 && !leafletBounds && !focusPoint;

  const [clusteringDisabled, setClusteringDisabled] = useState(false);
  const [basemap, setBasemap] = useState<BasemapKey>("marine");
  const [cursorPosition, setCursorPosition] = useState<{ latitude: number; longitude: number } | null>(null);

  useEffect(() => {
    setClusteringDisabled(window.localStorage.getItem(MAP_CLUSTER_DISABLED_KEY) === "true");

    const stored = window.localStorage.getItem(BASEMAP_STORAGE_KEY);
    if (stored === "standard" || stored === "marine" || stored === "dark") {
      setBasemap(stored);
    } else if (stored === "satellite") {
      setBasemap("marine");
      window.localStorage.setItem(BASEMAP_STORAGE_KEY, "marine");
    }
  }, []);

  function handleBasemapChange(value: BasemapKey) {
    setBasemap(value);
    window.localStorage.setItem(BASEMAP_STORAGE_KEY, value);
  }

  const markerPins = markers.map((marker) => {
    const focused = isFocused(marker);

    return (
      <Marker
        key={marker.detection_id}
        position={[marker.latitude, marker.longitude]}
        icon={markerIcon(
          marker.detection_class,
          marker.priority,
          marker.detection_id === selectedId,
          marker.priority === "critical",
          focused
        )}
        eventHandlers={{
          click: () => onSelect?.(marker.detection_id),
        }}
      >
        <Popup>
          <div className="min-w-[200px] space-y-1 text-xs text-slate-800">
            <p className="text-sm font-semibold">{marker.detection_ref}</p>
            <p className="capitalize text-slate-600">{marker.detection_class.replace("_", " ")}</p>
            <dl className="grid grid-cols-2 gap-x-2 gap-y-0.5 pt-1">
              <dt className="text-slate-500">Confidence</dt>
              <dd>{formatConfidence(marker.calibrated_confidence)}</dd>
              <dt className="text-slate-500">Uncertainty</dt>
              <dd className="capitalize">{marker.uncertainty ?? "--"}</dd>
              <dt className="text-slate-500">Priority</dt>
              <dd className="capitalize">{marker.priority}</dd>
              <dt className="text-slate-500">Review</dt>
              <dd className="capitalize">{marker.review_status.replace("_", " ")}</dd>
              <dt className="text-slate-500">Position +/-</dt>
              <dd>{marker.position_error_m ? `${marker.position_error_m} m` : "--"}</dd>
              <dt className="text-slate-500">Depth</dt>
              <dd>{marker.depth ? `${marker.depth} m` : "--"}</dd>
            </dl>
            <p className="pt-1 text-[10px] text-slate-500">
              {formatCoordinate(marker.latitude)}, {formatCoordinate(marker.longitude)}
            </p>
            <p className="text-[10px] text-slate-500">{formatDateTime(marker.created_at)}</p>
            <Link
              href={`/app/detections/${marker.detection_id}`}
              className="mt-2 inline-block rounded bg-cyan-700 px-2 py-1 text-[11px] font-medium text-paper hover:bg-cyan-600"
            >
              View Detail -&gt;
            </Link>
          </div>
        </Popup>
      </Marker>
    );
  });

  const uncertaintyCircles = markers
    .filter((marker) => typeof marker.position_error_m === "number" && marker.position_error_m > 0)
    .map((marker) => (
      <Circle
        key={`unc-${marker.detection_id}`}
        center={[marker.latitude, marker.longitude]}
        radius={marker.position_error_m as number}
        pathOptions={{
          color: PRIORITY_COLORS[marker.priority] ?? PRIORITY_COLORS.low,
          weight: 1,
          fillOpacity: isFocused(marker) ? 0.08 : 0.03,
          opacity: isFocused(marker) ? 0.4 : 0.15,
        }}
      />
    ));

  return (
    /* The dark-basemap class lives on this WRAPPER, not on MapContainer.
       react-leaflet passes `className` to Leaflet only when the map is first
       created, so switching basemap after mount never applied it: picking
       "Dark" left the tile filter in globals.css as dead code and rendered
       identically to Standard. The filter targets `.leaflet-tile-pane`, which
       is a descendant either way. */
    <div className={clsx("relative h-full w-full", basemap === "dark" && "map-dark-mode")}>
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: "100%", width: "100%" }}
        scrollWheelZoom
      >
        {BASEMAPS[basemap].layers.map((layer, index) => (
          <TileLayer
            key={`${basemap}-${index}`}
            url={layer.url}
            attribution={layer.attribution}
            maxZoom={"maxZoom" in layer ? layer.maxZoom : 19}
            opacity={"opacity" in layer ? layer.opacity : undefined}
          />
        ))}

        <ScaleControl position="bottomleft" imperial={false} />
        <FitAndFocus bounds={leafletBounds} focusPoint={focusPoint} />
        <RecenterOnResize center={center} zoom={zoom} active={isSingleMarkerFocus} />
        {!compact && <CursorReadout onChange={setCursorPosition} />}

        {leafletBounds && (
          <Rectangle
            bounds={leafletBounds}
            pathOptions={{ color: IMPERIAL, weight: 1, fillOpacity: 0.02, dashArray: "6 6" }}
          />
        )}

        {corridor && (
          <Polygon
            positions={corridor}
            pathOptions={{ color: ATLANTIC, weight: 1, opacity: 0.35, fillOpacity: 0.1 }}
          />
        )}

        {trackLine.length > 1 && (
          <Polyline positions={trackLine} pathOptions={{ color: IMPERIAL, weight: 2.5, opacity: 0.8 }} />
        )}

        {uncertaintyCircles}

        {vesselPosition && (
          <Marker
            position={[vesselPosition.latitude, vesselPosition.longitude]}
            icon={vesselIcon(vesselPosition.headingDeg)}
            interactive={false}
          />
        )}

        {clusteringDisabled ? (
          markerPins
        ) : (
          <MarkerClusterGroup
            chunkedLoading
            iconCreateFunction={clusterIcon}
            maxClusterRadius={50}
            spiderfyOnMaxZoom
            showCoverageOnHover={false}
          >
            {markerPins}
          </MarkerClusterGroup>
        )}
      </MapContainer>

      {compact ? (
        isSingleMarkerFocus && (
          // Top-right, below the north arrow -- top-left is the native Leaflet
          // zoom control, which the old cursor-readout box used to sit on top
          // of and hide.
          <div className="pointer-events-none absolute right-3 top-14 z-[1000] rounded-md border border-abyss-600 bg-abyss-900/85 px-2.5 py-1.5 text-[11px] text-slate-300 backdrop-blur">
            <div className="font-semibold uppercase tracking-[0.18em] text-slate-500">Detection</div>
            <div className="mt-0.5 whitespace-nowrap">
              {formatCoordinate(markers[0].latitude)}, {formatCoordinate(markers[0].longitude)}
            </div>
            {typeof markers[0].position_error_m === "number" && (
              <div className="whitespace-nowrap text-slate-400">± {markers[0].position_error_m} m</div>
            )}
          </div>
        )
      ) : (
        <>
          <div className="pointer-events-none absolute left-3 top-3 z-[1000] rounded-md border border-abyss-600 bg-abyss-900/85 px-2.5 py-1.5 text-[11px] text-slate-300 backdrop-blur">
            <div className="font-semibold uppercase tracking-[0.18em] text-slate-500">Cursor</div>
            <div className="mt-0.5 whitespace-nowrap">
              {cursorPosition
                ? `${formatCoordinate(cursorPosition.latitude)}, ${formatCoordinate(cursorPosition.longitude)}`
                : "Move on map"}
            </div>
          </div>
          <BasemapSwitcher value={basemap} onChange={handleBasemapChange} />
        </>
      )}

      <NorthArrow />
    </div>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { AppShell } from "@/components/AppShell";
import { useCurrentUser } from "@/features/auth/hooks";
import { useSystemConfig } from "@/features/system/hooks";
import { useAuthStore } from "@/state/auth-store";
import { REDUCED_MOTION_OVERRIDE_KEY } from "@/hooks/useReducedMotion";
import { getBoolSetting, MAP_CLUSTER_DISABLED_KEY, setBoolSetting } from "@/utils/settings";

function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 panel p-4">
      <div>
        <p className="text-sm font-medium text-slate-100">{label}</p>
        <p className="mt-0.5 text-xs text-slate-500">{description}</p>
      </div>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-5 w-9 shrink-0 cursor-pointer appearance-none rounded-full bg-abyss-700 outline-none transition checked:bg-cyan-accent before:block before:h-4 before:w-4 before:translate-x-0.5 before:translate-y-0.5 before:rounded-full before:bg-slate-300 before:transition-transform checked:before:translate-x-4 checked:before:bg-abyss-950"
      />
    </label>
  );
}

function SettingsGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h2>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const { data: user } = useCurrentUser();
  const { data: config } = useSystemConfig();
  const clearSession = useAuthStore((s) => s.clearSession);

  const [reducedMotion, setReducedMotion] = useState(false);
  const [clusterDisabled, setClusterDisabled] = useState(false);

  useEffect(() => {
    setReducedMotion(getBoolSetting(REDUCED_MOTION_OVERRIDE_KEY));
    setClusterDisabled(getBoolSetting(MAP_CLUSTER_DISABLED_KEY));
  }, []);

  return (
    <AppShell title="Settings">
      <SettingsGroup title="Application">
        <Toggle
          label="Reduce motion"
          description="Pauses ambient ocean, sonar sweep and vessel animation across the app. Takes effect on your next visit to a page with 3D/animated content."
          checked={reducedMotion}
          onChange={(v) => {
            setReducedMotion(v);
            setBoolSetting(REDUCED_MOTION_OVERRIDE_KEY, v);
          }}
        />
      </SettingsGroup>

      <SettingsGroup title="Map">
        <Toggle
          label="Disable marker clustering"
          description="Show every detection as an individual pin on the GIS map instead of grouping nearby detections into clusters."
          checked={clusterDisabled}
          onChange={(v) => {
            setClusterDisabled(v);
            setBoolSetting(MAP_CLUSTER_DISABLED_KEY, v);
          }}
        />
      </SettingsGroup>

      <SettingsGroup title="Processing">
        <div className="panel p-4 text-sm text-slate-300">
          {config ? (
            <dl className="grid grid-cols-2 gap-y-2">
              <dt className="text-slate-500">Max upload size</dt>
              <dd>{config.max_upload_size_mb} MB</dd>
              <dt className="text-slate-500">Accepted file types</dt>
              <dd className="font-mono text-xs">{config.allowed_upload_extensions.join(", ")}</dd>
            </dl>
          ) : (
            <p className="text-slate-500">Loading configuration…</p>
          )}
        </div>
      </SettingsGroup>

      <SettingsGroup title="Account">
        <div className="panel p-4">
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <dt className="text-slate-500">Username</dt>
            <dd className="text-slate-200">{user?.username ?? "—"}</dd>
            <dt className="text-slate-500">Display name</dt>
            <dd className="text-slate-200">{user?.display_name ?? "—"}</dd>
          </dl>
          <button
            onClick={() => {
              clearSession();
              router.push("/auth/login");
            }}
            className="mt-4 rounded-md border border-abyss-600 px-4 py-1.5 text-sm text-slate-300 hover:border-cyan-accent/50 hover:text-cyan-accent"
          >
            Log out
          </button>
        </div>
      </SettingsGroup>

      <SettingsGroup title="Security">
        <div className="panel p-4 text-sm text-slate-400">
          <p>
            This build uses a single seeded operator account with JWT authentication. Self-service password reset
            and multi-user role-based access control are part of the company-grade upgrade and are not available
            in this build.
          </p>
        </div>
      </SettingsGroup>

      <SettingsGroup title="System">
        <div className="panel p-4 text-sm text-slate-300">
          <p>{config?.app_name ?? "GhostNet-AI Backend"}</p>
          <Link href="/app/system-status" className="mt-2 inline-block text-sm text-cyan-accent hover:underline">
            View live system status →
          </Link>
        </div>
      </SettingsGroup>
    </AppShell>
  );
}

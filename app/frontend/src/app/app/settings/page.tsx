"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AppShell } from "@/components/AppShell";
import { Panel } from "@/components/Panel";
import { useToastStore } from "@/components/Toast";
import { useChangePassword, useCurrentUser } from "@/features/auth/hooks";
import { useAuthStore } from "@/state/auth-store";

const schema = z
  .object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: z.string().min(8, "New password must be at least 8 characters"),
    confirm_password: z.string().min(1, "Confirm the new password"),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type FormValues = z.infer<typeof schema>;

export default function SettingsPage() {
  const { data: currentUser } = useCurrentUser();
  const role = useAuthStore((s) => s.role);
  const changePassword = useChangePassword();
  const push = useToastStore((s) => s.push);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    try {
      await changePassword.mutateAsync({ current_password: values.current_password, new_password: values.new_password });
      push("Password changed.", "success");
      reset();
    } catch {
      push("Unable to change password -- check your current password.", "error");
    }
  }

  return (
    <AppShell title="Settings">
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel className="p-6">
          <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/85">Profile</p>
          <h2 className="mt-3 font-display text-2xl font-semibold text-slate-100">{currentUser?.display_name ?? "—"}</h2>
          <dl className="mt-5 space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Username</dt>
              <dd className="text-slate-200">{currentUser?.username ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Role</dt>
              <dd className="uppercase tracking-[0.1em] text-slate-200">{role ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Account status</dt>
              <dd className={currentUser?.is_active ? "text-emerald-400" : "text-alert-critical"}>
                {currentUser?.is_active ? "Active" : "Deactivated"}
              </dd>
            </div>
          </dl>
          <p className="mt-5 text-xs leading-5 text-slate-500">
            Roles and account status for other users are managed directly at the database level; there is no
            in-app user management surface.
          </p>
        </Panel>

        <Panel className="p-6">
          <p className="text-[11px] uppercase tracking-[0.32em] text-cyan-accent/85">Security</p>
          <h2 className="mt-3 font-display text-2xl font-semibold text-slate-100">Change password</h2>
          <p className="mt-2 text-sm text-slate-400">Changing your password signs out any other active sessions.</p>

          <form onSubmit={handleSubmit(onSubmit)} className="mt-5 space-y-4">
            <div>
              <label htmlFor="current_password" className="mb-1 block text-xs font-medium text-slate-400">
                Current password
              </label>
              <input
                id="current_password"
                type="password"
                {...register("current_password")}
                className="w-full rounded-md border border-abyss-600 bg-abyss-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
              />
              {errors.current_password && <p className="mt-1 text-xs text-alert-critical">{errors.current_password.message}</p>}
            </div>

            <div>
              <label htmlFor="new_password" className="mb-1 block text-xs font-medium text-slate-400">
                New password
              </label>
              <input
                id="new_password"
                type="password"
                {...register("new_password")}
                className="w-full rounded-md border border-abyss-600 bg-abyss-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
              />
              {errors.new_password && <p className="mt-1 text-xs text-alert-critical">{errors.new_password.message}</p>}
            </div>

            <div>
              <label htmlFor="confirm_password" className="mb-1 block text-xs font-medium text-slate-400">
                Confirm new password
              </label>
              <input
                id="confirm_password"
                type="password"
                {...register("confirm_password")}
                className="w-full rounded-md border border-abyss-600 bg-abyss-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
              />
              {errors.confirm_password && <p className="mt-1 text-xs text-alert-critical">{errors.confirm_password.message}</p>}
            </div>

            <button
              type="submit"
              disabled={changePassword.isPending}
              className="w-full rounded-md bg-cyan-accent py-2 text-sm font-medium text-abyss-950 hover:bg-cyan-accent/90 disabled:opacity-60"
            >
              {changePassword.isPending ? "Changing…" : "Change Password"}
            </button>
          </form>
        </Panel>
      </div>
    </AppShell>
  );
}

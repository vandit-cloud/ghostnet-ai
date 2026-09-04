"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AppShell } from "@/components/AppShell";
import { useToastStore } from "@/components/Toast";
import { useCreateSurvey } from "@/features/surveys/hooks";

const AmbientOceanBackground = dynamic(
  () => import("@/components/three/AmbientOceanBackground").then((m) => m.AmbientOceanBackground),
  { ssr: false }
);

const schema = z.object({
  name: z.string().min(1, "Survey name is required").max(200),
  source: z.string().max(200).optional().or(z.literal("")),
  sonar_type: z.string().max(100).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

export default function NewSurveyPage() {
  const router = useRouter();
  const createSurvey = useCreateSurvey();
  const push = useToastStore((s) => s.push);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    try {
      const survey = await createSurvey.mutateAsync({
        name: values.name,
        source: values.source || undefined,
        sonar_type: values.sonar_type || undefined,
      });
      push("Survey created.", "success");
      router.push(`/app/surveys/${survey.id}`);
    } catch {
      push("Unable to create survey.", "error");
    }
  }

  return (
    <AppShell title="New Survey">
      <div className="relative isolate min-h-[560px] overflow-hidden rounded-lg">
        <div className="absolute inset-0 -z-10 opacity-70">
          <AmbientOceanBackground dim />
        </div>
        <form onSubmit={handleSubmit(onSubmit)} className="max-w-lg space-y-4 panel p-6">
        <div>
          <label htmlFor="name" className="mb-1 block text-xs font-medium text-slate-400">
            Survey Name
          </label>
          <input
            id="name"
            {...register("name")}
            className="w-full rounded-md border border-abyss-600 bg-abyss-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
          />
          {errors.name && <p className="mt-1 text-xs text-alert-critical">{errors.name.message}</p>}
        </div>

        <div>
          <label htmlFor="source" className="mb-1 block text-xs font-medium text-slate-400">
            Source (vessel / mission)
          </label>
          <input
            id="source"
            {...register("source")}
            className="w-full rounded-md border border-abyss-600 bg-abyss-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
          />
        </div>

        <div>
          <label htmlFor="sonar_type" className="mb-1 block text-xs font-medium text-slate-400">
            Sonar Type
          </label>
          <input
            id="sonar_type"
            {...register("sonar_type")}
            placeholder="side-scan, multibeam, ..."
            className="w-full rounded-md border border-abyss-600 bg-abyss-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-accent focus:shadow-glow-cyan"
          />
        </div>

        <button
          type="submit"
          disabled={createSurvey.isPending}
          className="w-full rounded-md bg-cyan-accent py-2 text-sm font-medium text-abyss-950 hover:bg-cyan-accent/90 disabled:opacity-60"
        >
          {createSurvey.isPending ? "Creating…" : "Create Survey"}
        </button>
        </form>
      </div>
    </AppShell>
  );
}

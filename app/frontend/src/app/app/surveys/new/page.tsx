"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AppShell } from "@/components/AppShell";
import { Panel } from "@/components/Panel";
import { useToastStore } from "@/components/Toast";
import { useCreateSurvey } from "@/features/surveys/hooks";

const HeroWaterBackdrop = dynamic(
  () => import("@/components/three/HeroWaterBackdrop").then((m) => m.HeroWaterBackdrop),
  {
    ssr: false,
    // ssr:false means nothing at all renders here until the three.js chunk has
    // downloaded and the shader has compiled. Without a fallback that gap is
    // the PAGE BACKGROUND showing through -- a white flash on every cold load,
    // for as long as the chunk takes. Painting the shader's own deep-water
    // colour makes the wait read as the backdrop still loading rather than as
    // a broken page. Matches the pattern HeroSonar already used.
    loading: () => <div aria-hidden className="absolute inset-0 bg-[#072639]" />,
  }
);

const schema = z.object({
  name: z.string().min(1, "Survey name is required").max(200),
  source: z.string().max(200).optional().or(z.literal("")),
  sonar_type: z.string().max(100).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

/* Same glyph set as the survey inventory table's SonarTypeIcon (see
 * app/surveys/page.tsx), pulled out to standalone components so the quick-
 * select chips here can recolor them per state (currentColor). */
function SideScanGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 3v18M4 8l8-5 8 5M4 16l8 5 8-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MultibeamGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 20c2-6 4-9 8-9s6 3 8 9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M6 20c1.5-4 3-6 6-6s4.5 2 6 6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity="0.6" />
    </svg>
  );
}

function GenericSonarGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="2.4" fill="currentColor" />
    </svg>
  );
}

const SONAR_PRESETS: { label: string; value: string; icon: () => JSX.Element }[] = [
  { label: "Side-scan", value: "Side-scan sonar", icon: SideScanGlyph },
  { label: "Multibeam", value: "Multibeam sonar", icon: MultibeamGlyph },
  { label: "Synthetic aperture", value: "Synthetic aperture sonar", icon: GenericSonarGlyph },
];

const STEPS = [
  { title: "Create", detail: "Register the mission with a name and source vessel." },
  { title: "Upload", detail: "Add geotagged sonar frames or a raw survey archive." },
  { title: "Validate", detail: "Confirm coverage, sonar type, and track continuity." },
  { title: "Process", detail: "Run detection and review results on the map and in 3D." },
];

const INPUT_CLASS =
  "w-full border border-abyss-600/80 bg-skytint/42 px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-cyan-accent focus:shadow-glow-cyan";
const LABEL_CLASS = "mb-2 block text-[11px] font-medium uppercase tracking-[0.26em] text-slate-500";

export default function NewSurveyPage() {
  const router = useRouter();
  const createSurvey = useCreateSurvey();
  const push = useToastStore((s) => s.push);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { name: "", source: "", sonar_type: "" } });

  const values = watch();

  async function onSubmit(formValues: FormValues) {
    try {
      const survey = await createSurvey.mutateAsync({
        name: formValues.name,
        source: formValues.source || undefined,
        sonar_type: formValues.sonar_type || undefined,
      });
      push("Survey created.", "success");
      router.push(`/app/surveys/${survey.id}`);
    } catch {
      push("Unable to create survey.", "error");
    }
  }

  return (
    <AppShell title="New Survey">
      <div className="space-y-6">
        <Link
          href="/app/surveys"
          className="inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.24em] text-slate-500 transition hover:text-cyan-accent"
        >
          <span aria-hidden>&larr;</span> Surveys
        </Link>

        <Panel className="relative min-h-[260px] overflow-hidden p-6 sm:p-8">
          <div className="absolute inset-0">
            <HeroWaterBackdrop />
          </div>
          <div className="absolute inset-0 bg-gradient-to-t from-atlantic-deep via-atlantic/55 to-atlantic/10" />
          <div className="relative z-10">
            <p className="text-[11px] uppercase tracking-[0.32em] text-skytint/85">Field Operations</p>
            <h1 className="mt-3 font-display text-3xl font-semibold tracking-wide text-paper sm:text-4xl">New Survey</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-paper/74">
              Register a mission to begin staging sonar uploads. You can add coverage detail and start processing once files are attached.
            </p>
          </div>
        </Panel>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.95fr)]">
          <Panel className="p-6 sm:p-7">
            <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-accent/80">Mission Details</p>
            <form onSubmit={handleSubmit(onSubmit)} className="mt-5 space-y-5">
              <div>
                <label htmlFor="name" className={LABEL_CLASS}>
                  Survey Name
                </label>
                <input id="name" {...register("name")} placeholder="e.g., Gulf of Mannar Trawl Sweep" className={INPUT_CLASS} />
                <p className="mt-1.5 text-xs text-slate-500">A short, identifiable mission name analysts will see in every list.</p>
                {errors.name && <p className="mt-1.5 text-xs text-alert-critical">{errors.name.message}</p>}
              </div>

              <div>
                <label htmlFor="source" className={LABEL_CLASS}>
                  Source (vessel / mission)
                </label>
                <input id="source" {...register("source")} placeholder="e.g., R/V Sagar Kanya, Cruise SK-412" className={INPUT_CLASS} />
                <p className="mt-1.5 text-xs text-slate-500">Optional. Helps trace a survey back to its vessel or cruise later.</p>
              </div>

              <div>
                <span className={LABEL_CLASS}>Sonar Type</span>
                <div className="flex flex-wrap gap-2">
                  {SONAR_PRESETS.map((preset) => {
                    const active = values.sonar_type === preset.value;
                    const Icon = preset.icon;
                    return (
                      <button
                        key={preset.value}
                        type="button"
                        onClick={() => setValue("sonar_type", preset.value, { shouldDirty: true })}
                        className={`inline-flex items-center gap-1.5 border px-3 py-1.5 text-xs font-medium uppercase tracking-[0.14em] transition ${
                          active
                            ? "border-imperial bg-imperial text-paper"
                            : "border-abyss-600/80 text-slate-300 hover:border-cyan-accent/50 hover:text-cyan-accent"
                        }`}
                      >
                        <Icon /> {preset.label}
                      </button>
                    );
                  })}
                </div>
                <input
                  id="sonar_type"
                  {...register("sonar_type")}
                  placeholder="Or type a custom sonar type..."
                  className={`${INPUT_CLASS} mt-2.5`}
                />
                <p className="mt-1.5 text-xs text-slate-500">Pick a preset above or describe the equipment used.</p>
              </div>

              <button
                type="submit"
                disabled={createSurvey.isPending}
                className="flex w-full items-center justify-center gap-2 border border-imperial bg-imperial py-2.5 text-sm font-medium uppercase tracking-[0.22em] text-paper transition hover:bg-imperial-deep disabled:opacity-60"
              >
                {createSurvey.isPending && (
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden>
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                    <path className="opacity-80" d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                  </svg>
                )}
                {createSurvey.isPending ? "Creating…" : "Create Survey"}
              </button>
            </form>
          </Panel>

          <div className="space-y-6">
            <Panel tone="tint" className="p-6">
              <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-accent/80">Preview</p>
              <h3 className="mt-3 font-display text-xl font-semibold text-slate-100">{values.name || "Untitled survey"}</h3>
              <dl className="mt-4 space-y-2.5 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500">Source</dt>
                  <dd className="truncate text-right text-slate-100">{values.source || "Not set"}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500">Sonar type</dt>
                  <dd className="inline-flex items-center gap-1.5 text-right text-slate-100">
                    {values.sonar_type ? <GenericSonarGlyph /> : null}
                    {values.sonar_type || "Not set"}
                  </dd>
                </div>
              </dl>
            </Panel>

            <Panel className="p-6">
              <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-accent/80">What Happens Next</p>
              <ol className="mt-4 space-y-4">
                {STEPS.map((step, i) => (
                  <li key={step.title} className="flex gap-3">
                    <span
                      className={`flex h-6 w-6 shrink-0 items-center justify-center border font-mono text-[11px] ${
                        i === 0 ? "border-imperial bg-imperial text-paper" : "border-abyss-600/80 text-slate-500"
                      }`}
                    >
                      {i + 1}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-slate-200">{step.title}</p>
                      <p className="text-xs leading-5 text-slate-500">{step.detail}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </Panel>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

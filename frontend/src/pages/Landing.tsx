import { Link } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { useHealth } from "@/hooks/use-health";
import { isoWeek, TierBadge } from "@/components/editorial";
import { cn } from "@/lib/utils";

const capabilities = [
  {
    name: "Predict",
    line: "Which zones are most likely to see measles next.",
    body: "Estimates how many children are unprotected in each zone from births, two-dose vaccination coverage and past campaigns, then weighs infection pressure from neighbouring zones.",
    status: "Phase 1",
  },
  {
    name: "Detect",
    line: "Which woredas crossed an outbreak threshold this week.",
    body: "Applies the measles outbreak thresholds EPHI uses, plus early-rise checks for counts that are climbing but not yet over the line.",
    status: "Phase 1",
  },
  {
    name: "Fuse",
    line: "One alert per place and week, with its evidence.",
    body: "Combines routine counts, field reports and official bulletins. A confirmed threshold crossing is never downgraded for lack of other signals.",
    status: "Phase 1",
  },
  {
    name: "Explain",
    line: "Why this place, why now — in plain language.",
    body: "Drafts the reasoning and situation-report text from the stored evidence only, with every statement traceable to a record.",
    status: "Partly built",
  },
];

const today = [
  ["Reads messy reports", "Text, CSV, PDF and photographed documents are turned into structured case records.", "Built"],
  ["Human review", "Every record waits for an officer to approve or reject it before it counts.", "Built"],
  ["Ask the data", "Questions in plain language over the stored records.", "Built"],
  ["Outbreak thresholds and early-rise detection", "Weekly checks on routine counts per woreda.", "In development"],
  ["Measles risk ranking", "Monthly zone ranking from immunity gaps and nearby infection.", "In development"],
  ["DHIS2 connection", "Reads PHEM weekly and EPI monthly data once EPHI approves access.", "In development"],
];

const ladder = [
  { tier: "RED", when: "Confirmed-outbreak threshold crossed", action: "Outbreak response" },
  { tier: "ORANGE", when: "Suspected-outbreak threshold crossed, or a verified field cluster", action: "Investigate within 48 hours" },
  { tier: "YELLOW", when: "Early rise, an unverified field report, or a bulletin mention", action: "Verify" },
];

export default function Landing() {
  const { isAuthenticated } = useAuthStore();
  const health = useHealth();
  const { week, year } = isoWeek();
  const enterHref = isAuthenticated ? "/dashboard" : "/login";

  return (
    <div className="min-h-screen bg-background">
      {/* Masthead */}
      <header className="border-b border-foreground">
        <div className="mx-auto max-w-[1200px] px-4 md:px-8">
          <div className="flex items-center justify-between h-12 text-[0.8125rem]">
            <span className="num text-muted-foreground">
              Week {week} · {year}
            </span>
            <span className="hidden sm:inline-flex items-center gap-2 text-muted-foreground" role="status">
              <span
                aria-hidden
                className={cn("h-1.5 w-1.5", health.isLoading ? "bg-muted-foreground" : health.isSuccess ? "bg-tier-clear" : "bg-tier-red")}
              />
              {health.isLoading ? "Checking service" : health.isSuccess ? "Service online" : "Service unreachable"}
            </span>
            <Link to={enterHref} className="underline underline-offset-4 decoration-1 hover:decoration-2">
              {isAuthenticated ? "Open the console" : "Sign in"}
            </Link>
          </div>
          <div className="border-t border-border py-6 md:py-8 flex flex-col md:flex-row md:items-end md:justify-between gap-2">
            <p className="font-serif text-[2.25rem] md:text-[3.25rem] leading-none">Empowered Care</p>
            <p className="label-caps md:text-right">Outbreak intelligence for Ethiopia</p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1200px] px-4 md:px-8">
        {/* Lead */}
        <section className="grid md:grid-cols-12 gap-8 py-12 md:py-16 border-b border-border">
          <div className="md:col-span-8">
            <p className="label-caps mb-4">The brief</p>
            <h1 className="text-[2.25rem] md:text-[3.5rem] leading-[1.05] font-medium max-w-[18ch]">
              Measles outbreaks are found weeks after they start. We are building the system that finds them sooner.
            </h1>
          </div>
          <div className="md:col-span-4 md:pt-10">
            <p className="prose-brief">
              Ethiopia already collects the data: weekly PHEM reports, immunization records, field reports from health
              extension workers. What is missing is a layer that reads it all every week and tells epidemiologists where
              to look first.
            </p>
            <p className="prose-brief mt-4">
              Empowered Care sits on top of DHIS2 and existing reporting. It does not replace them, and it never acts
              without a person deciding.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to={enterHref}
                className="inline-flex h-10 items-center px-5 bg-primary text-primary-foreground text-sm font-medium rounded-sm hover:bg-primary/90"
              >
                {isAuthenticated ? "Open the console" : "Sign in"}
              </Link>
              <a href="#status" className="inline-flex h-10 items-center px-5 border border-foreground/70 text-sm rounded-sm hover:bg-muted">
                What works today
              </a>
            </div>
          </div>
        </section>

        {/* Capabilities */}
        <section className="py-12 md:py-16 border-b border-border" aria-labelledby="how">
          <div className="flex items-baseline justify-between border-t border-foreground pt-2 mb-8">
            <h2 id="how" className="text-2xl font-medium">How it works</h2>
            <span className="label-caps">Pilot disease · measles</span>
          </div>
          <ol className="grid sm:grid-cols-2 lg:grid-cols-4 border-l border-border">
            {capabilities.map((c, i) => (
              <li key={c.name} className="border-r border-b sm:border-b-0 border-border px-5 py-2">
                <p className="num text-xs text-muted-foreground">0{i + 1}</p>
                <h3 className="text-[1.75rem] font-medium mt-1">{c.name}</h3>
                <p className="mt-3 font-serif text-[1.0625rem] leading-snug">{c.line}</p>
                <p className="mt-3 text-sm text-muted-foreground leading-relaxed">{c.body}</p>
                <p className="label-caps mt-5 mb-3">{c.status}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* Alert ladder */}
        <section className="py-12 md:py-16 border-b border-border grid md:grid-cols-12 gap-8" aria-labelledby="ladder">
          <div className="md:col-span-4">
            <div className="border-t border-foreground pt-2">
              <h2 id="ladder" className="text-2xl font-medium">Three tiers, one rule</h2>
            </div>
            <p className="prose-brief mt-4">
              Clinical and laboratory thresholds set the floor. Risk and context can raise an alert's priority; nothing
              can lower it.
            </p>
          </div>
          <div className="md:col-span-8 overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="w-32">Tier</th>
                  <th>Raised when</th>
                  <th className="w-56">Expected action</th>
                </tr>
              </thead>
              <tbody>
                {ladder.map((l) => (
                  <tr key={l.tier}>
                    <td>
                      <TierBadge level={l.tier} showRaw={false} />
                    </td>
                    <td>{l.when}</td>
                    <td className="text-muted-foreground">{l.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-muted-foreground mt-3">
              Thresholds follow WHO AFRO measles guidance and are configurable to the current EPHI guideline.
            </p>
          </div>
        </section>

        {/* Status */}
        <section id="status" className="py-12 md:py-16 border-b border-border" aria-labelledby="today">
          <div className="flex items-baseline justify-between border-t border-foreground pt-2 mb-6">
            <h2 id="today" className="text-2xl font-medium">What works today</h2>
            <span className="label-caps">Updated as features ship</span>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Capability</th>
                  <th>What it does</th>
                  <th className="w-36">Status</th>
                </tr>
              </thead>
              <tbody>
                {today.map(([name, desc, status]) => (
                  <tr key={name}>
                    <td className="font-medium min-w-[9rem]">{name}</td>
                    <td className="text-muted-foreground min-w-[12rem]">{desc}</td>
                    <td>
                      <span className={cn("label-caps", status === "Built" && "text-foreground")}>{status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Audience */}
        <section className="py-12 md:py-16 grid md:grid-cols-3 gap-8" aria-labelledby="who">
          <div className="border-t border-foreground pt-2">
            <h2 id="who" className="text-2xl font-medium">Who it is for</h2>
          </div>
          <div>
            <p className="label-caps">National</p>
            <p className="prose-brief mt-2">
              EPHI epidemiologists who need the country picture each week and the evidence behind every alert.
            </p>
          </div>
          <div>
            <p className="label-caps">Regional</p>
            <p className="prose-brief mt-2">
              Regional health bureau PHEM teams who decide which zones and woredas to investigate first.
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t border-foreground">
        <div className="mx-auto max-w-[1200px] px-4 md:px-8 py-6 flex flex-col sm:flex-row justify-between gap-2 text-[0.8125rem] text-muted-foreground">
          <span>Empowered Care · Addis Ababa</span>
          <span>Decision support for public health officers. It does not replace clinical or government authority.</span>
        </div>
      </footer>
    </div>
  );
}

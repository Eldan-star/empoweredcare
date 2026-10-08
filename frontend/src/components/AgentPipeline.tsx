import { useEffect, useState } from "react";

/** What the backend does to a report, in order. Shown as a description, not as fake progress. */
const STAGES = [
  ["Extract", "Split the text into one record per place and condition."],
  ["Check", "Look for missing fields and implausible counts."],
  ["Rate", "Four prompts rate the record from different angles."],
  ["Draft", "Write the summary and suggested actions."],
];

interface Props {
  isProcessing?: boolean;
  /** Kept for compatibility with older callers; ignored. */
  currentStep?: unknown;
  completedSteps?: unknown;
}

export function AgentPipeline({ isProcessing = false }: Props) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isProcessing) return;
    setElapsed(0);
    const started = Date.now();
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(t);
  }, [isProcessing]);

  return (
    <div>
      <div className="flex items-baseline justify-between border-t border-foreground pt-2 mb-3">
        <h2 className="text-lg font-medium">What happens next</h2>
        <span className="label-caps" role="status" aria-live="polite">
          {isProcessing ? (
            <>
              Processing · <span className="num">{elapsed}s</span>
            </>
          ) : (
            "Idle"
          )}
        </span>
      </div>
      <ol className="text-sm">
        {STAGES.map(([name, desc], i) => (
          <li key={name} className="grid grid-cols-[1.5rem_4.5rem_1fr] gap-2 py-2 border-b border-border">
            <span className="num text-xs text-muted-foreground pt-0.5">{i + 1}</span>
            <span className="font-medium">{name}</span>
            <span className="text-muted-foreground">{desc}</span>
          </li>
        ))}
      </ol>
      <p className="text-xs text-muted-foreground mt-3">
        Usually 20–90 seconds, depending on length. The stages run on the server; this page does not track them individually.
      </p>
    </div>
  );
}

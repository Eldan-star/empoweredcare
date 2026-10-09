import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { api, apiErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface Message {
  role: "user" | "assistant";
  content: string;
  agent?: string;
  error?: boolean;
}

const AGENT_LABEL: Record<string, string> = {
  location: "Location specialist",
  infection: "Infection specialist",
  history: "History specialist",
  general: "General assistant",
};

export const SUGGESTIONS = [
  "Which locations have the most cases?",
  "Summarise the records received this week",
  "Which records are still waiting for review?",
  "What conditions appear most often?",
];

/** Conversation state shared by the full page and the side panel. */
export function useConversation() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || loading) return;
    setMessages((m) => [...m, { role: "user", content: q }]);
    setLoading(true);
    try {
      const resp = await api.chat(q, sessionId);
      setSessionId(resp.session_id);
      setMessages((m) => [...m, { role: "assistant", content: resp.response, agent: resp.agent_used }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: apiErrorMessage(e, "The assistant could not answer."), error: true }]);
    } finally {
      setLoading(false);
    }
  };

  const clear = async () => {
    if (sessionId) await api.clearChat(sessionId).catch(() => undefined);
    setMessages([]);
    setSessionId(undefined);
  };

  return { messages, loading, send, clear };
}

const markdown =
  "font-serif text-[1rem] leading-relaxed space-y-3 [&_h1]:text-lg [&_h2]:text-lg [&_h3]:text-base [&_h1,&_h2,&_h3]:font-medium " +
  "[&_ul]:list-disc [&_ol]:list-decimal [&_ul,&_ol]:pl-5 [&_li]:mt-1 [&_strong]:font-semibold " +
  "[&_code]:font-mono [&_code]:text-[0.8125rem] [&_code]:bg-muted [&_code]:px-1 " +
  "[&_table]:w-full [&_table]:text-sm [&_th]:text-left [&_th]:border-b [&_th]:border-foreground [&_td]:border-b [&_td]:border-border [&_td,&_th]:py-1 [&_td,&_th]:pr-3";

export function Transcript({
  messages,
  loading,
  onSuggest,
  compact = false,
}: {
  messages: Message[];
  loading: boolean;
  onSuggest: (q: string) => void;
  compact?: boolean;
}) {
  const end = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState<number | null>(null);
  useEffect(() => {
    // Braces matter: newer browsers return a Promise from scrollIntoView, and React
    // would treat a returned value as a cleanup function.
    end.current?.scrollIntoView({ block: "end" });
  }, [messages, loading]);

  if (!messages.length && !loading) {
    return (
      <div className={cn(compact ? "p-4" : "py-6")}>
        <p className="text-sm text-muted-foreground mb-3">
          Answers are drawn from the stored records only. Try one of these:
        </p>
        <ul className="space-y-1">
          {SUGGESTIONS.map((s) => (
            <li key={s}>
              <button onClick={() => onSuggest(s)} className="text-left text-sm underline underline-offset-4 decoration-border hover:decoration-foreground">
                {s}
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className={cn("space-y-6", compact ? "p-4" : "py-6")}>
      {messages.map((m, i) =>
        m.role === "user" ? (
          <div key={i} className="border-l-2 border-foreground pl-3">
            <p className="label-caps text-[0.625rem]">You asked</p>
            <p className="text-[0.9375rem] mt-1">{m.content}</p>
          </div>
        ) : (
          <div key={i}>
            <div className={cn(markdown, m.error && "text-destructive")}>
              <ReactMarkdown>{m.content}</ReactMarkdown>
            </div>
            <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
              {m.agent && <span className="label-caps text-[0.625rem]">{AGENT_LABEL[m.agent] || m.agent}</span>}
              <button
                onClick={() => {
                  navigator.clipboard.writeText(m.content);
                  setCopied(i);
                  setTimeout(() => setCopied(null), 1500);
                }}
                className="underline underline-offset-2"
              >
                {copied === i ? "Copied" : "Copy"}
              </button>
            </div>
          </div>
        ),
      )}
      {loading && (
        <p className="label-caps" role="status">
          Reading the records…
        </p>
      )}
      <div ref={end} />
    </div>
  );
}

export function Composer({ onSend, disabled, autoFocus }: { onSend: (q: string) => void; disabled?: boolean; autoFocus?: boolean }) {
  const [value, setValue] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSend(value);
        setValue("");
      }}
      className="flex gap-2"
    >
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask about locations, cases, conditions…"
        disabled={disabled}
        autoFocus={autoFocus}
        aria-label="Question"
        className="flex-1 h-10 bg-card border border-input rounded-sm px-3 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
      />
      <Button type="submit" disabled={disabled || !value.trim()}>
        Ask
      </Button>
    </form>
  );
}

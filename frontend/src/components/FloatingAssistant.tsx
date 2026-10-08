import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { X } from "lucide-react";
import { Composer, Transcript, useConversation } from "@/components/Conversation";

/** Side panel version of "Ask the data", available on every console page. */
export function FloatingAssistant() {
  const [open, setOpen] = useState(false);
  const { messages, loading, send, clear } = useConversation();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  if (pathname === "/query") return null;

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-5 right-5 z-40 h-10 px-4 bg-primary text-primary-foreground text-sm rounded-sm hover:bg-primary/90"
      >
        Ask the data
      </button>
    );
  }

  return (
    <aside
      className="fixed inset-y-0 right-0 z-50 w-full sm:w-[400px] bg-background border-l border-foreground flex flex-col"
      aria-label="Ask the data"
    >
      <div className="h-12 px-4 flex items-center justify-between border-b border-border">
        <p className="font-serif text-lg">Ask the data</p>
        <div className="flex items-center gap-3 text-xs">
          {messages.length > 0 && (
            <button onClick={clear} className="underline underline-offset-2 text-muted-foreground hover:text-foreground">
              Clear
            </button>
          )}
          <button
            onClick={() => {
              setOpen(false);
              navigate("/query");
            }}
            className="underline underline-offset-2 text-muted-foreground hover:text-foreground"
          >
            Full page
          </button>
          <button onClick={() => setOpen(false)} className="p-1 text-muted-foreground hover:text-foreground" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        <Transcript messages={messages} loading={loading} onSuggest={send} compact />
      </div>
      <div className="p-4 border-t border-border">
        <Composer onSend={send} disabled={loading} autoFocus />
      </div>
    </aside>
  );
}

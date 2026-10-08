import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/editorial";
import { Composer, Transcript, useConversation } from "@/components/Conversation";

export default function QueryPage() {
  const { messages, loading, send, clear } = useConversation();

  return (
    <div className="max-w-3xl">
      <PageHeader
        kicker="Ask the data"
        title="Questions about the stored records"
        lede="The assistant reads the current records and answers in plain language. It can be wrong; check figures against the records before acting."
        actions={
          messages.length > 0 ? (
            <Button variant="outline" size="sm" onClick={clear}>
              Clear conversation
            </Button>
          ) : undefined
        }
      />
      <Transcript messages={messages} loading={loading} onSuggest={send} />
      <div className="sticky bottom-0 bg-background border-t border-foreground pt-4 pb-2 mt-6">
        <Composer onSend={send} disabled={loading} autoFocus />
      </div>
    </div>
  );
}

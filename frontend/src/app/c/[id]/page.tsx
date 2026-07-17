import { ConversationView } from "@/components/ConversationView";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  // Keyed so navigating between conversations remounts fresh state instead
  // of resetting it inside an effect.
  return <ConversationView key={id} conversationId={id} />;
}

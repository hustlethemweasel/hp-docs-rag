export type Role = "user" | "assistant";

export interface Source {
  chunk_id: number;
  document: string;
  pages: string;
  score: number;
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  sources: Source[] | null;
  provider: string | null;
  model: string | null;
  latency_ms: number | null;
  status: string;
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string;
  messages: Message[];
}

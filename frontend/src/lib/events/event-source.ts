import { SSE_EVENT_TYPES, type SSEEvent, type SSEEventType } from "./types";

type EventHandler<T extends SSEEvent = SSEEvent> = (event: T) => void;

type SubscriptionOptions<T extends SSEEventType> = {
  topic?: string;
  eventTypes?: readonly T[];
  onEvent: EventHandler<Extract<SSEEvent, { type: T }>>;
  onError?: (event: Event) => void;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function subscribeToEvents<T extends SSEEventType>({
  topic,
  eventTypes,
  onEvent,
  onError,
}: SubscriptionOptions<T>): () => void {
  const url = new URL(`${API_BASE}/api/v1/events/stream`);
  if (topic) url.searchParams.set("topic", topic);

  const source = new EventSource(url.toString());

  const handleMessage = (message: MessageEvent<string>) => {
    const parsed = JSON.parse(message.data) as SSEEvent;
    if (eventTypes && !eventTypes.includes(parsed.type as T)) return;
    onEvent(parsed as Extract<SSEEvent, { type: T }>);
  };

  const names = eventTypes?.length ? eventTypes : SSE_EVENT_TYPES;
  for (const name of names) {
    source.addEventListener(name, handleMessage);
  }
  source.addEventListener("message", handleMessage);
  if (onError) source.addEventListener("error", onError);

  return () => {
    for (const name of names) {
      source.removeEventListener(name, handleMessage);
    }
    source.removeEventListener("message", handleMessage);
    if (onError) source.removeEventListener("error", onError);
    source.close();
  };
}

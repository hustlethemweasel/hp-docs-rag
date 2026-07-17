"""Load-test scenario for the chat flow (R12, SPEC §12).

Exercises the real flow a browser client drives: create a conversation, then
send a message and consume the SSE stream to its terminal event. The same
script serves both scenarios in SPEC §12 — which one you're running is a
property of the `api` instance under test, not of this file:

  (a) `api` started with LLM_PROVIDER=scripted — isolates API + retrieval +
      DB scalability from LLM throughput.
  (b) `api` started with the real configured provider (e.g. anthropic) —
      realistic end-to-end throughput.

Per the constitution (SPEC §2), this is load-test scenario scripting, not
application logic — it has no dedicated unit tests, same as eval/run.py.

Run headless, e.g.:
    locust -f loadtest/locustfile.py --host http://localhost:8000 \\
        --headless --users 20 --spawn-rate 2 --run-time 3m --csv results/scenario_a
"""

import random
import time
import uuid

from locust import HttpUser, between, events, task

QUESTIONS = [
    "How do I replace the ink cartridge?",
    "What does the blinking amber light mean?",
    "How do I remove the OMEN laptop's battery?",
    "What is the maximum paper size supported?",
    "How do I reset the printer to factory defaults?",
    "How do I connect the printer to wifi?",
    "What torque should I use on the laptop's screws?",
    "How do I clean the printhead?",
]

# SSE frames are newline-delimited "event: <name>" / "data: <json>" pairs
# (app/api/sse.py); a blank line separates frames. These are the two names
# that terminate a stream (app/rag/chat_service.py).
_TERMINAL_EVENTS = (b"event: done", b"event: error")


class ChatUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.user_id = str(uuid.uuid4())
        response = self.client.post(
            "/api/conversations",
            headers=self._headers(),
            name="/api/conversations [create]",
        )
        self.conversation_id = response.json()["id"]

    def _headers(self) -> dict[str, str]:
        return {"X-User-Id": self.user_id}

    @task(6)
    def send_message(self) -> None:
        question = random.choice(QUESTIONS)
        url = f"/api/conversations/{self.conversation_id}/messages"
        started = time.perf_counter()
        exception: Exception | None = None
        try:
            with self.client.post(
                url,
                json={"content": question},
                headers=self._headers(),
                stream=True,
                catch_response=True,
                name="/api/conversations/[id]/messages [ttfb]",
            ) as response:
                saw_terminal_event = False
                for line in response.iter_lines():
                    if line.startswith(_TERMINAL_EVENTS):
                        saw_terminal_event = True
                if saw_terminal_event:
                    response.success()
                else:
                    response.failure("stream ended without a terminal event")
        except Exception as exc:  # noqa: BLE001 — reported to Locust, not swallowed
            exception = exc
        # The automatic "[ttfb]" sample above times the connection/headers
        # only (requests returns as soon as headers arrive for stream=True);
        # this one reports the full answer latency a real user waits for.
        events.request.fire(
            request_type="SSE",
            name="/api/conversations/[id]/messages [full answer]",
            response_time=(time.perf_counter() - started) * 1000,
            response_length=0,
            exception=exception,
        )

    @task(2)
    def list_conversations(self) -> None:
        self.client.get(
            "/api/conversations",
            headers=self._headers(),
            name="/api/conversations [list]",
        )

    @task(1)
    def start_new_conversation(self) -> None:
        response = self.client.post(
            "/api/conversations",
            headers=self._headers(),
            name="/api/conversations [create]",
        )
        self.conversation_id = response.json()["id"]

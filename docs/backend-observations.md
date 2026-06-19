# Backend Observations & Todo List

Collected observations from manual testing. Each item includes the problem, desired behavior, and implementation notes.

---

## [ ] 1. Dynamic Chat Thread Naming via LLM

**Observation:** Chat threads have no auto-generated title. The title must either be set manually or defaults to a placeholder.

**Desired behavior:** After the user's first message is received, the backend should trigger a lightweight LLM call to generate a short, descriptive thread title (4–8 words) and persist it to the `chats` table.

**Notes:**
- Run the title-generation call asynchronously after the main agent response is kicked off — it should not block the response stream.
- Prompt: pass only the user's first message and ask for a concise, specific title (e.g. "AAPL Revenue Q4 2024", "Tesla 10-K Risk Factors").
- Save the result to the `title` column on the `chats` table.
- Expose the updated title back to the frontend — either via the existing SSE/WebSocket stream as a metadata event, or as a separate endpoint the frontend polls/calls after first message.
- Fallback: if the LLM call fails, truncate the first 40 characters of the user's message and use that as the title.

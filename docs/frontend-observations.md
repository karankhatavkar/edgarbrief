# Frontend Observations & Todo List

Collected observations from manual testing. Each item includes the problem, desired behavior, and implementation notes.

---

## [x] 1. Markdown Rendering for LLM Output

**Observation:** LLM responses are returned as raw markdown strings but are rendered as plain text in the chat window.

**Desired behavior:** All assistant messages should be rendered as formatted markdown — headings, bold/italic, bullet lists, numbered lists, code blocks, blockquotes, tables, etc.

**Notes:**
- Use a markdown rendering library (e.g. `react-markdown` + `remark-gfm` for GitHub-flavored markdown).
- Code blocks should have monospace font and ideally syntax highlighting.
- Ensure rendered markdown doesn't break the chat bubble layout.

---

## [ ] 2. "New Brief" Button Creates Duplicate Chats on Double-Click

**Observation:** Clicking "New Brief" correctly opens a new chat. But clicking it a second time while already on a blank new chat opens another empty chat, resulting in duplicate blank sessions.

**Desired behavior:** If the user is already on a new, unsaved/empty chat, clicking "New Brief" again should be a no-op (or navigate to the existing new chat rather than creating another one).

**Notes:**
- Guard the handler: check if the current chat is already a new/empty session before creating another.
- Optionally disable or visually suppress the button while on an empty new chat.

---

## [ ] 3. Live Agent Progress — Show What the Agent Is Doing in Real Time

**Observation:** While the agent is working, the UI only shows a static or generic status message (e.g. "Retrieving files…"). The user has no visibility into what is actually happening step-by-step.

**Desired behavior:** Show a live, updating stream of agent activity steps as they happen — e.g.:
- "Searching for relevant filings…"
- "Reading AAPL 10-K (2024)…"
- "Extracting revenue figures…"
- "Composing answer…"

**Notes:**
- Backend should emit step events (SSE or WebSocket) as the agent progresses through its workflow.
- Frontend should display these as a live feed inside the chat — either below the user message or in a collapsible "Agent working…" panel.
- On completion, the step feed can collapse/fade and the final answer takes over.
- This is a significant UX trust-builder — users should feel like the agent is working, not frozen.

---

## [ ] 4. Adjustable Side Panel Width

**Observation:** The side panel (chat list / navigation) has a fixed width with no way for the user to resize it.

**Desired behavior:** The user should be able to drag the panel edge to resize it within reasonable bounds (e.g. min 180px, max 400px).

**Notes:**
- Implement a drag handle on the right edge of the side panel.
- Persist the chosen width to `localStorage` so it survives page refreshes.
- Ensure the chat area reflows correctly as the panel resizes.

---

## [ ] 5. Logout Button Is Not Clearly Labeled

**Observation:** The logout action is represented only by an icon with no label, making it unclear to users — especially new ones.

**Desired behavior:** Add a visible text label ("Log out") alongside the icon, or show a tooltip on hover at minimum.

**Notes:**
- Prefer a visible label if there is space in the layout.
- If space is tight, a clear tooltip (`title` attribute or custom tooltip component) is acceptable.
- Consider placing it in a user menu/avatar dropdown for a more conventional pattern.

---

## [x] 6. Markdown Rendering for Citation Document Preview

**Observation:** When a citation/source document is surfaced in the citations panel, its content is displayed as raw text without any formatting.

**Desired behavior:** The citation document preview should render markdown properly — headings, lists, bold/italic, etc. — so the sourced content is readable and scannable at a glance.

**Notes:**
- Reuse the same markdown renderer chosen for item #1 (LLM output).
- The citation panel likely has a narrower width — ensure the renderer handles constrained layouts gracefully (wrapping, no horizontal overflow).
- If the source content is very long, consider a truncated preview with a "Show more" expand.

# AI Interface Design (Proposed)

**Status:** Proposed design for developer review<br>
**Scope:** Dashboard AI assistant and dedicated AI workspace<br>
**Design reference:** OpenCode-style chat composer shown in the supplied mockup

This document translates the mockup into a HomePot UI direction. It is a design
handoff, not a claim that the described experience is implemented. The goal is
to provide a quick AI entry point on the Dashboard and a larger workspace for
longer investigations, without creating two assistants with different behavior.

## Design principles

1. **One assistant, two surfaces.** The Dashboard assistant and AI workspace
   share conversation behavior, modes, provider state, trust presentation, and
   safety rules.
2. **Use space intentionally.** The Dashboard surface stays compact; the
   workspace uses the large conversation canvas and persistent composer from
   the reference.
3. **Name controls truthfully.** A label must describe a capability that exists.
   Do not present a provider as a model selector, a mode as an agent selector,
   or a prompt shortcut as an executable command.
4. **Keep safety and evidence visible.** Knowledge answers show their sources;
   diagnostic answers keep validation/trust information close to the answer.
   Chat must not imply device changes were approved or executed when they were
   not.
5. **Reuse the composer action slot.** The Send button becomes Stop while a
   query is running; do not add a second Stop button elsewhere in the composer.

## Product surfaces

### Dashboard assistant

The Dashboard assistant is for quick technician questions. It should remain
visibly part of the Dashboard rather than competing with its monitored-resource
and status panels.

- Show a clear **AI Assistant** identity and current provider/health information
  when available. For non-admin users, show provider/model status as read-only;
  hide the provider switcher.
- Provide a concise prompt field and a small set of suggested prompts.
- Show a compact answer preview or latest exchange when space permits.
- Provide an **Open AI Workspace** action for longer investigations.
- Carry the current draft into the workspace immediately. Carry the visible
  conversation too, once conversation history is actually wired and persisted
  (see [AI Memory](ai-memory.md)); until then, carry the draft only.
- Only display site, device, or fleet context when that context is actually
  supplied to the AI request.

The current `AskAIWidget` is rendered in the Dashboard's right column below
System Pulse and Active Alerts (`frontend/src/pages/Dashboard.jsx`). The compact
surface should respect that constrained space and offer a clear path to the
larger workspace.

### Dedicated AI workspace

The workspace is the primary surface for multi-turn investigations and follows
the reference image's overall composition:

```text
┌ AI identity / provider status / clear conversation ──────────────────┐
│                                                                      │
│                 Scrollable conversation canvas                       │
│                                                                      │
│                                                                      │
│                                                                      │ 
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│ Multi-line prompt composer                                           │
│ [Mode] [Provider] [optional menu]                    [Send / Stop]   │
│ Note                                     Enter / Shift+Enter hint    │
└──────────────────────────────────────────────────────────────────────┘
```

- Use the majority of the available height for the conversation canvas.
- Keep the composer anchored at the bottom while the conversation scrolls.
- Include a useful empty state with a short introduction and suggested prompts;
  do not leave the canvas as a large blank area.
- Display user and assistant messages as distinct turns.
- Opening the workspace from the Dashboard preserves the draft or thread.
- The exact route and navigation placement are implementation decisions; the
  proposed navigation label is **AI Workspace**. A suggested route is
  `/ai-workspace`.

## Composer controls

The reference mockup shows Task, Agent, Model, and Commands controls. Map these
to HomePot's actual capabilities rather than copying the labels literally.

| Reference control | Proposed HomePot control | Behavior and constraints |
|---|---|---|
| Task | **Mode** | Auto, Knowledge, Diagnostic. Keep Auto as the default; selecting a mode is an explicit user override. |
| Agent | Omit initially | There is no independent agent selector in the current Dashboard assistant. Add one only when users can choose between real agents. |
| Model | **Provider** | Ollama, OpenAI, or Anthropic. Show the configured model name/status where available; provider switching remains Admin-only. See [LLM Providers](ai-llm-providers.md). |
| Commands | **Suggested prompts** or omit | Use for inserting a prompt template only. Do not imply that it executes a device command. Link to proposal review separately if that is useful. |
| Send | **Send / Stop** | Reuse one button and one footprint; behavior is specified below. |

Do not add a command-execution menu to the chat until its actions, permissions,
confirmation, and result reporting are implemented and documented. AI action
proposals are reviewed through the separate
[AI Delegation Plan — Review UI](ai-delegation-plan.md#review-ui-ai-proposals);
a chat answer alone is not an approval or an execution.

## Send / Stop button behavior

The primary composer button occupies the same location in both states:

| State | Appearance | Action |
|---|---|---|
| Idle, empty prompt | Send icon, disabled | No action |
| Idle, prompt has text | Send icon, enabled | Submit the prompt |
| Query running | Stop-square icon, enabled | Cancel the active query using the existing cancellation flow |
| Query settled or cancelled | Return to Send state | Ready for the next prompt |

Requirements:

- The button changes from **Send** to **Stop** as soon as submission begins.
- While loading, clicking it calls the same cancellation behavior as the current
  Stop/Escape flow: notify the server using the query ID and abort the client
  request. Do not claim server-side cancellation is confirmed unless the server
  confirms it.
- Keep the input disabled while the query is running in the initial design; the
  Stop button remains enabled.
- Restore the Send state when the request settles, including after cancellation
  or failure.
- Expose an accessible name that changes with the state (`Send question` /
  `Stop response`) and a tooltip where supported. Preserve Escape as an alternate
  stop shortcut.
- Do not render an additional Stop button in the response area or composer row.

The current widget already has query IDs and cancellation handling in
`frontend/src/components/Dashboard/AskAIWidget.jsx`; this design moves the Stop
affordance into the existing submit-button position rather than defining a new
cancellation mechanism.

## Conversation and response presentation

- **Knowledge response:** show a Knowledge indicator and the real retrieved
  documentation sources.
- **Diagnostic response:** show the trust summary and allow gate details to be
  expanded in context with that answer.
- **Loading:** show truthful progress copy appropriate to the selected/resolved
  path, plus the Stop button. Avoid fake percentages or implying that a device
  action is running.
- **Slow response:** explain that the model is still working and retain the Stop
  option.
- **Error/cancellation:** show a clear outcome and recovery path. Distinguish a
  locally stopped wait from a server-confirmed discarded answer.
- **Conversation history:** a workspace should behave as a real multi-turn chat.
  The backend accepts `history`, but the Dashboard widget does not currently
  send it. Wiring and persistence policy must be included in implementation
  scope before presenting prior turns as model context. See [AI Memory](ai-memory.md).

## Safety and action review

Use a concise, accurate footer statement such as:

> Answers are advisory. Device actions require separate review.

The exact copy should be reviewed against the final action-proposal flow. The UI
must distinguish an AI recommendation, a proposal awaiting approval, an approved
plan, and queued/executed device commands. Never represent approval or execution
as complete based only on text in a chat response.

## Visual and responsive direction

- Use the mockup's deep navy canvas, subtle slate borders, rounded composer, and
  strong primary action hierarchy.
- Purple may identify AI actions; retain HomePot's teal as a supporting brand
  accent rather than recoloring the whole application.
- Keep text and controls legible against the dark background; provide visible
  keyboard focus and adequate contrast.
- At narrow widths, wrap or stack Mode/Provider/menu controls rather than
  compressing labels into unreadable buttons.
- Keep the keyboard hint visible when space permits: **Enter to send ·
  Shift+Enter for new line**. On mobile, rely on clear accessible labels instead
  of desktop-only shortcut instructions.

## Acceptance criteria for implementation

- Dashboard users can start a quick query and open the workspace without losing
  the draft or active conversation.
- The workspace has a scrollable conversation area and a composer anchored at
  the bottom.
- There is exactly one primary composer action: it sends when idle and stops
  while a query is running.
- Stop uses the existing query cancellation flow and does not falsely report
  server confirmation.
- Mode and provider controls use accurate names and respect permissions.
- Knowledge sources and diagnostic trust details remain visible and accurate.
- No control suggests arbitrary commands or device changes unless the
  corresponding capability and review flow are implemented.
- The layout works at Dashboard, workspace, and narrow/mobile widths, with
  keyboard operation and accessible control labels.

## Related implementation

- Dashboard entry point: `frontend/src/pages/Dashboard.jsx`
- Current assistant and query cancellation: `frontend/src/components/Dashboard/AskAIWidget.jsx`
- Provider behavior: [LLM Providers](ai-llm-providers.md)
- Trust presentation: [Trust & Validation Gates](ai-validation-gates.md)
- Conversation and long-term memory: [AI Memory](ai-memory.md)
- Proposal review: `frontend/src/pages/AIProposals/AIProposalsList.jsx`

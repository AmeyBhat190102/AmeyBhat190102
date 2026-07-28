# Template Studio — Agent Template Chat

A small chat application for **creating and updating voice-agent templates** through conversation. You describe the campaign you want; Claude drafts the template's flow (`Objective` / `Instruction` / `Other_instruction`), refines it with you, and persists it with the **`save_template`** tool on the vendor-calling MCP server — creating a new template, or updating an existing one by `template_id`.

## How it works

```
Browser (public/index.html)
   │  POST /api/chat { sessionId, message }
   ▼
Express server (server.js)
   │  Claude Messages API + MCP connector
   ▼
Claude (claude-opus-5) ──── calls tools server-side ────▶ vendor-calling MCP server
                                                          (save_template, get_template,
                                                           preview_turn, generate_scenarios)
```

The backend is intentionally thin: it keeps per-session conversation history in memory and makes one Messages API call per user message, passing the MCP server via the API's **MCP connector** (`mcp_servers` + `mcp_toolset`, beta `mcp-client-2025-11-20`). Anthropic's side connects to the MCP server and runs the tool loop — there is no MCP client or tool-execution code in this app.

The system prompt restricts the assistant to the template workflow: it may use `save_template`, `get_template`, `preview_turn`, and `generate_scenarios`, must show a draft and get an explicit "save it" before writing, and must never use `trigger_call` (this app never places phone calls).

## Setup

```bash
cd agent-template-chat
npm install
cp .env.example .env      # then put your ANTHROPIC_API_KEY in .env
npm start
```

Open http://localhost:3000.

## Configuration (`.env`)

| Variable            | Default                                                        | Purpose                              |
| ------------------- | -------------------------------------------------------------- | ------------------------------------ |
| `ANTHROPIC_API_KEY` | — (required)                                                   | Claude API key                       |
| `PORT`              | `3000`                                                         | HTTP port                            |
| `CLAUDE_MODEL`      | `claude-opus-5`                                                | Model used for the chat              |
| `MCP_SERVER_URL`    | `https://consumer-mcp-server.markytics.ai/vendor-calling/mcp`  | The templates MCP server             |
| `MCP_AUTH_TOKEN`    | —                                                              | Bearer token if the server needs one |

## Using it

- **Create:** *"Create a lead-qualification template for client `acme-realty` in Hindi."* → the assistant drafts the flow, you refine it, then say *"save it"* → it calls `save_template` and reports the new `template_id`.
- **Update:** *"Fetch the active template for `acme-realty` and make the tone more formal."* → it loads the template with `get_template`, shows the edit, and on your confirmation saves with the same `template_id` (an update, not a new template).
- **Test a draft:** *"Pretend I'm the callee — hello, who is this?"* → it dry-runs the draft with `preview_turn` (text only, no telephony), or generates test scenarios with `generate_scenarios`.

Tool calls made during a reply are shown as chips (e.g. `🔧 save_template ✓`) above the assistant's message.

## Testing the save seam directly

`npm run test:save` (or `node test-save-template.mjs`) exercises `save_template` end-to-end against the MCP server over plain HTTP — no API key needed. It creates a template for `bhavesh-api` (with `instas_ai_client_id: "65"`, no `template_id`, no campaign id), verifies it with `get_template`, updates the same `template_id` (attaching the `instas_ai_campaign_id` found in the create/get response, or `INSTAS_AI_CAMPAIGN_ID` from the env), and verifies the edits persisted. All values are overridable via env vars — see the header comment in the script.

## Notes

- Conversation history lives in server memory only — restarting the server clears all chats (capped at 200 sessions).
- Templates hold agent *behavior* only; per-call data (callee name, amounts, dates) is supplied at dial time by the calling system, so the assistant is instructed to keep drafts free of it.
- The tool restriction is enforced in the system prompt (the MCP connector executes tools on Anthropic's side, so the server cannot intercept individual calls).

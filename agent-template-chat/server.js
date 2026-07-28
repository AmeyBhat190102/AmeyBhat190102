import "dotenv/config";
import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Anthropic from "@anthropic-ai/sdk";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PORT = Number(process.env.PORT || 3000);
const MODEL = process.env.CLAUDE_MODEL || "claude-opus-5";
const MCP_SERVER_URL =
  process.env.MCP_SERVER_URL ||
  "https://consumer-mcp-server.markytics.ai/vendor-calling/mcp";
const MCP_SERVER_NAME = "vendor-calling";
const MAX_CONTINUATIONS = 8; // safety cap on pause_turn resumes per user message
const MAX_SESSIONS = 200;

const SYSTEM_PROMPT = `You are "Template Studio", an assistant that helps users create and update voice-agent templates for outbound calling campaigns. You are connected to the vendor-calling MCP server, which stores these templates.

## What a template is
- A template defines an agent's calling BEHAVIOR: the campaign goal, how to run the conversation, and the guardrails.
- Its core is \`flow_instructions\`: a list containing exactly ONE object with three keys:
  - "Objective": the campaign goal of the call
  - "Instruction": how the agent should run the conversation
  - "Other_instruction": guardrails and constraints (what never to say or do, language rules, escalation rules)
- Templates must NEVER contain per-call data (the callee's name, amounts, due dates, or the specific company/offer) — that data is supplied at dial time. Keep templates reusable at the vertical level.
- Other fields: \`client_id\` (the owning client), \`name\` (short kebab-case slug like "realty-lead-qual"), \`lang_code\` (bare code like "hi", "mr", "en"; defaults to "hi"), and optionally \`instas_ai_campaign_id\` and \`instas_ai_client_id\`.

## Tools you may use
- save_template — create a template (omit template_id) or update one (pass its template_id). The only tool that writes.
- get_template — fetch a template by template_id, or a client's active (latest) template by client_id.
- preview_turn — dry-run one conversational turn of a drafted flow (text only, no telephony). Use it to demo or refine a draft.
- generate_scenarios — author test scenarios for a drafted flow.

Do NOT use any other tool on the server. NEVER call trigger_call under any circumstances — this app does not place phone calls. If asked to place a call, explain that calling is out of scope here and the saved template will be used by the calling system separately.

## How to work
1. NEW template: gather the essentials conversationally (client_id, campaign goal, conversation flow, guardrails, language, name). Propose sensible drafts rather than interrogating — show a full flow_instructions draft early and refine it with the user.
2. UPDATE: fetch the current template first with get_template, show the relevant parts, then apply the requested edits to a new draft. Pass the template_id to save_template so it updates instead of creating.
3. Always show the exact draft (Objective / Instruction / Other_instruction) before saving.
4. Only call save_template after the user explicitly confirms (e.g. "save it", "yes, go ahead"). Never save silently, and never re-save unchanged content.
5. After saving, report the returned template_id (plus name and client_id) so the user can reference it later.
6. If the user wants to test a draft, use preview_turn (the user's message plays the callee) or generate_scenarios — these do not touch the template store.

Be concise and practical. Show drafts in small code blocks. Ask for missing required fields (client_id, name) before saving; ask for instas_ai_client_id / instas_ai_campaign_id only if the user wants them attached.`;

// ---------------------------------------------------------------------------

const app = express();
app.use(express.json({ limit: "1mb" }));
app.use(express.static(path.join(__dirname, "public")));

// sessionId -> full Claude message history (content blocks preserved verbatim,
// including thinking / mcp_tool_use / mcp_tool_result blocks)
const sessions = new Map();

let client = null;
function getClient() {
  if (!client) client = new Anthropic(); // throws a clear error if no credentials
  return client;
}

function createMessage(messages) {
  const mcpServer = {
    type: "url",
    url: MCP_SERVER_URL,
    name: MCP_SERVER_NAME,
  };
  if (process.env.MCP_AUTH_TOKEN) {
    mcpServer.authorization_token = process.env.MCP_AUTH_TOKEN;
  }
  return getClient().beta.messages.create({
    model: MODEL,
    max_tokens: 16000,
    betas: ["mcp-client-2025-11-20"],
    system: [
      {
        type: "text",
        text: SYSTEM_PROMPT,
        cache_control: { type: "ephemeral" },
      },
    ],
    mcp_servers: [mcpServer],
    tools: [{ type: "mcp_toolset", mcp_server_name: MCP_SERVER_NAME }],
    messages,
  });
}

// Collect which MCP tools ran in a response, pairing each call with its result.
function collectToolActivity(content, into) {
  const resultsById = new Map();
  for (const block of content) {
    if (block.type === "mcp_tool_result") resultsById.set(block.tool_use_id, block);
  }
  for (const block of content) {
    if (block.type !== "mcp_tool_use") continue;
    const result = resultsById.get(block.id);
    into.push({ name: block.name, ok: result ? result.is_error !== true : null });
  }
}

app.get("/api/health", (_req, res) => {
  res.json({
    ok: true,
    model: MODEL,
    mcpServer: MCP_SERVER_URL,
    keyConfigured: Boolean(
      process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN
    ),
  });
});

app.post("/api/chat", async (req, res) => {
  const { sessionId, message } = req.body ?? {};
  if (
    typeof sessionId !== "string" ||
    !sessionId.trim() ||
    typeof message !== "string" ||
    !message.trim()
  ) {
    return res
      .status(400)
      .json({ error: "sessionId and a non-empty message are required." });
  }

  // Work on a copy so a failed request leaves the stored history untouched.
  const history = [...(sessions.get(sessionId) ?? [])];
  history.push({ role: "user", content: message.trim() });

  const tools = [];
  try {
    let response = await createMessage(history);
    history.push({ role: "assistant", content: response.content });
    collectToolActivity(response.content, tools);

    // MCP tool loops can pause server-side; re-send to resume where it left off.
    let continuations = 0;
    while (
      response.stop_reason === "pause_turn" &&
      continuations < MAX_CONTINUATIONS
    ) {
      continuations++;
      response = await createMessage(history);
      history.push({ role: "assistant", content: response.content });
      collectToolActivity(response.content, tools);
    }

    if (!sessions.has(sessionId) && sessions.size >= MAX_SESSIONS) {
      sessions.delete(sessions.keys().next().value); // drop the oldest session
    }
    sessions.set(sessionId, history);

    let reply = response.content
      .filter((b) => b.type === "text")
      .map((b) => b.text)
      .join("\n")
      .trim();
    if (response.stop_reason === "refusal") {
      reply =
        reply ||
        "I can't help with that request. Let's get back to building your agent template.";
    } else if (response.stop_reason === "max_tokens") {
      reply += "\n\n_(Reply was cut off at the token limit — say \"continue\" to keep going.)_";
    }

    res.json({
      reply: reply || "(The model returned no text.)",
      tools,
      stopReason: response.stop_reason,
    });
  } catch (err) {
    console.error("Chat request failed:", err);
    let error;
    if (err instanceof Anthropic.AuthenticationError) {
      error =
        "Anthropic authentication failed — set a valid ANTHROPIC_API_KEY in .env and restart the server.";
    } else if (err instanceof Anthropic.RateLimitError) {
      error = "Rate limited by the Claude API — wait a moment and try again.";
    } else if (err instanceof Anthropic.APIConnectionError) {
      error = "Could not reach the Claude API — check your network and try again.";
    } else if (err instanceof Anthropic.APIError) {
      error = `Claude API error (${err.status}): ${err.message}`;
    } else {
      error = err?.message || "Unexpected server error.";
    }
    res.status(502).json({ error });
  }
});

app.post("/api/reset", (req, res) => {
  const { sessionId } = req.body ?? {};
  if (typeof sessionId === "string") sessions.delete(sessionId);
  res.json({ ok: true });
});

app.listen(PORT, () => {
  console.log(`Template Studio running on http://localhost:${PORT}`);
  console.log(`  model:      ${MODEL}`);
  console.log(`  mcp server: ${MCP_SERVER_URL}`);
  if (!process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_AUTH_TOKEN) {
    console.warn(
      "  ⚠ ANTHROPIC_API_KEY is not set — chat requests will fail until you add it to .env"
    );
  }
});

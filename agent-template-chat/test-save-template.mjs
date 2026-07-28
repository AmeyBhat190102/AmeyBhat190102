#!/usr/bin/env node
/**
 * End-to-end test of the vendor-calling MCP server's save_template seam.
 *
 * Flow:  create (no template_id, no campaign id)  →  get_template verify
 *        →  update (template_id + instas_ai_campaign_id)  →  get_template verify
 *
 * Talks MCP Streamable HTTP directly — no SDK, no API key, Node >= 18.
 *
 * Usage:
 *   node test-save-template.mjs
 *
 * Overrides (all optional):
 *   MCP_SERVER_URL          default https://consumer-mcp-server.markytics.ai/vendor-calling/mcp
 *   CLIENT_ID               default bhavesh-api
 *   TEMPLATE_NAME           default payment-reminder-test
 *   LANG_CODE               default hi
 *   INSTAS_AI_CLIENT_ID     default 65
 *   INSTAS_AI_CAMPAIGN_ID   default: auto-detected from the create/get response
 */

const BASE =
  process.env.MCP_SERVER_URL ||
  "https://consumer-mcp-server.markytics.ai/vendor-calling/mcp";
const CLIENT_ID = process.env.CLIENT_ID || "bhavesh-api";
const TEMPLATE_NAME = process.env.TEMPLATE_NAME || "payment-reminder-test";
const LANG_CODE = process.env.LANG_CODE || "hi";
const INSTAS_AI_CLIENT_ID = process.env.INSTAS_AI_CLIENT_ID || "65";
const PROTOCOL_VERSION = "2025-06-18";

const BASE_FLOW = {
  Objective:
    "Remind the customer about their pending payment and secure a clear commitment to pay, or capture the reason they cannot pay yet.",
  Instruction:
    "Greet politely and confirm you are speaking with the right person. State that the call is regarding their pending payment, using only the details provided at dial time. Ask when they will be able to make the payment. If they commit, confirm the date back to them. If they refuse or dispute, ask one clarifying question and note the reason. Close by summarizing the outcome and thanking them.",
  Other_instruction:
    "Speak only in the calling language with short, natural sentences suited to voice. Never threaten, pressure, or harass. Never invent amounts, dates, or company details beyond what is provided at dial time. If the customer asks to stop being called, acknowledge and end the call. If the customer disputes the dues, offer a callback from a human agent instead of arguing.",
};

const UPDATED_FLOW = {
  Objective: BASE_FLOW.Objective,
  Instruction:
    BASE_FLOW.Instruction +
    " If the customer commits to a date more than a week away, gently ask once if an earlier partial payment is possible.",
  Other_instruction:
    BASE_FLOW.Other_instruction + " Keep the total call under three minutes.",
};

// ---------------------------------------------------------------- MCP client

let sessionId = null;
let rpcId = 0;

async function post(body) {
  const res = await fetch(BASE, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
      "MCP-Protocol-Version": PROTOCOL_VERSION,
      ...(sessionId ? { "Mcp-Session-Id": sessionId } : {}),
    },
    body: JSON.stringify(body),
  });
  sessionId = res.headers.get("mcp-session-id") || sessionId;
  if (res.status === 202) return null; // notification accepted
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status} from server: ${text.slice(0, 500)}`);
  // Body is either plain JSON or SSE ("data: {...}" lines)
  const dataLines = text.split("\n").filter((l) => l.startsWith("data: "));
  const messages = dataLines.length
    ? dataLines.map((l) => JSON.parse(l.slice(6)))
    : [JSON.parse(text)];
  return messages.find((m) => m.id === body.id) ?? messages.at(-1);
}

async function connect() {
  const res = await post({
    jsonrpc: "2.0",
    id: ++rpcId,
    method: "initialize",
    params: {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: {},
      clientInfo: { name: "template-studio-test", version: "1.0" },
    },
  });
  if (res?.error) throw new Error("initialize failed: " + JSON.stringify(res.error));
  await post({ jsonrpc: "2.0", method: "notifications/initialized" });
  return res.result?.serverInfo;
}

async function callTool(name, args) {
  const res = await post({
    jsonrpc: "2.0",
    id: ++rpcId,
    method: "tools/call",
    params: { name, arguments: args },
  });
  if (res?.error) throw new Error(`${name} RPC error: ` + JSON.stringify(res.error));
  const result = res.result ?? {};
  if (result.isError) {
    throw new Error(`${name} tool error: ` + JSON.stringify(result.content));
  }
  // Prefer structuredContent; fall back to parsing the text block
  if (result.structuredContent) return result.structuredContent;
  const text = (result.content ?? []).find((c) => c.type === "text")?.text ?? "";
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

// Recursively find the first value whose key matches the pattern.
function findByKey(obj, pattern, seen = new Set()) {
  if (!obj || typeof obj !== "object" || seen.has(obj)) return undefined;
  seen.add(obj);
  for (const [k, v] of Object.entries(obj)) {
    if (pattern.test(k) && (typeof v === "string" || typeof v === "number") && v !== "") {
      return String(v);
    }
  }
  for (const v of Object.values(obj)) {
    const hit = findByKey(v, pattern, seen);
    if (hit !== undefined) return hit;
  }
  return undefined;
}

const show = (label, obj) =>
  console.log(`\n=== ${label} ===\n` + JSON.stringify(obj, null, 2));

// ------------------------------------------------------------------ the test

try {
  const server = await connect();
  console.log(`Connected to ${BASE}`);
  if (server) console.log(`Server: ${server.name} ${server.version ?? ""}`);

  // 1. CREATE — no template_id, no instas_ai_campaign_id
  const createPayload = {
    client_id: CLIENT_ID,
    name: TEMPLATE_NAME,
    lang_code: LANG_CODE,
    instas_ai_client_id: INSTAS_AI_CLIENT_ID,
    flow_instructions: [BASE_FLOW],
  };
  show("1. save_template (CREATE) — payload", createPayload);
  const created = await callTool("save_template", createPayload);
  show("1. save_template (CREATE) — response", created);

  const templateId = findByKey(created, /^template_id$/i);
  if (!templateId) throw new Error("Create response contained no template_id — stopping.");
  console.log(`\n✔ Created template_id: ${templateId}`);

  // 2. VERIFY the stored template (also our chance to find the campaign id)
  const fetched1 = await callTool("get_template", { template_id: templateId });
  show("2. get_template (verify create)", fetched1);

  const campaignId =
    process.env.INSTAS_AI_CAMPAIGN_ID ||
    findByKey(created, /campaign/i) ||
    findByKey(fetched1, /campaign/i);
  console.log(
    campaignId
      ? `\n✔ instas_ai_campaign_id resolved: ${campaignId}`
      : "\n⚠ No campaign id found in the responses — running the update without it. " +
        "If the server requires it, re-run with INSTAS_AI_CAMPAIGN_ID=<id>."
  );

  // 3. UPDATE — same template_id, campaign id attached
  const updatePayload = {
    client_id: CLIENT_ID,
    template_id: templateId,
    name: TEMPLATE_NAME,
    lang_code: LANG_CODE,
    instas_ai_client_id: INSTAS_AI_CLIENT_ID,
    ...(campaignId ? { instas_ai_campaign_id: campaignId } : {}),
    flow_instructions: [UPDATED_FLOW],
  };
  show("3. save_template (UPDATE) — payload", updatePayload);
  const updated = await callTool("save_template", updatePayload);
  show("3. save_template (UPDATE) — response", updated);

  // 4. VERIFY the update landed
  const fetched2 = await callTool("get_template", { template_id: templateId });
  show("4. get_template (verify update)", fetched2);

  const finalText = JSON.stringify(fetched2);
  const hasEdit =
    finalText.includes("partial payment") && finalText.includes("three minutes");
  const sameId = findByKey(fetched2, /^template_id$/i) === templateId;

  console.log("\n================ RESULT ================");
  console.log(`create:            ✔ template_id ${templateId}`);
  console.log(`update (same id):  ${sameId ? "✔" : "✘ id mismatch"}`);
  console.log(`edits persisted:   ${hasEdit ? "✔ new guardrail + instruction found" : "✘ NOT found in stored template"}`);
  process.exit(hasEdit && sameId ? 0 : 1);
} catch (err) {
  console.error("\n✘ TEST FAILED:", err.message);
  process.exit(1);
}

import { NextRequest, NextResponse } from "next/server";
import { getProvider } from "@/lib/payments/provider";
import { unlockProject } from "@/lib/engine";

/** Creates a payment session for a project. Market is chosen by the
 * client's country header (Vercel/CF set it; default global). With no
 * payment rails configured (local dev), unlocks immediately so the full
 * product loop is demoable end to end. */
export async function POST(req: NextRequest) {
  const { projectId, plan = "unlock" } = await req.json();
  if (!projectId) return NextResponse.json({ error: "projectId required" }, { status: 422 });

  const country = req.headers.get("x-vercel-ip-country")
    ?? req.headers.get("cf-ipcountry") ?? "";
  const market = country === "IN" ? "india" : "global";
  const origin = req.nextUrl.origin;

  const provider = await getProvider(market);
  if (!provider) {
    if (process.env.NODE_ENV === "production") {
      return NextResponse.json({ error: "payments not configured" }, { status: 503 });
    }
    await unlockProject(projectId);      // dev mode: instant unlock
    return NextResponse.json({ provider: "dev", unlocked: true });
  }

  const session = await provider.createCheckout({
    projectId,
    plan,
    successUrl: `${origin}/studio/${projectId}?paid=1`,
    cancelUrl: `${origin}/studio/${projectId}`,
  });
  return NextResponse.json(session);
}

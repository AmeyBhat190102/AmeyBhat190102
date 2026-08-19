import { NextRequest, NextResponse } from "next/server";
import { unlockProject } from "@/lib/engine";

export async function POST(req: NextRequest) {
  if (!process.env.STRIPE_SECRET_KEY) {
    return NextResponse.json({ error: "stripe not configured" }, { status: 503 });
  }
  const { StripeProvider } = await import("@/lib/payments/stripe");
  const raw = await req.text();
  try {
    const projectId = await new StripeProvider().verifyWebhook(raw, req.headers);
    if (projectId) await unlockProject(projectId);
    return NextResponse.json({ received: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 400 });
  }
}

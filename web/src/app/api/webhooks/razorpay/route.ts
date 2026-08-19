import { NextRequest, NextResponse } from "next/server";
import { unlockProject } from "@/lib/engine";

export async function POST(req: NextRequest) {
  if (!process.env.RAZORPAY_KEY_ID) {
    return NextResponse.json({ error: "razorpay not configured" }, { status: 503 });
  }
  const { RazorpayProvider } = await import("@/lib/payments/razorpay");
  const raw = await req.text();
  try {
    const projectId = await new RazorpayProvider().verifyWebhook(raw, req.headers);
    if (projectId) await unlockProject(projectId);
    return NextResponse.json({ received: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 400 });
  }
}

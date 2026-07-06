import "server-only";
import crypto from "node:crypto";
import Razorpay from "razorpay";
import { CheckoutSession, PLAN_PRICES, PaymentProvider } from "./provider";

export class RazorpayProvider implements PaymentProvider {
  readonly name = "razorpay" as const;
  private client = new Razorpay({
    key_id: process.env.RAZORPAY_KEY_ID!,
    key_secret: process.env.RAZORPAY_KEY_SECRET!,
  });

  async createCheckout(input: {
    projectId: string;
    plan: "standard" | "studio" | "unlock";
    successUrl: string;
    cancelUrl: string;
  }): Promise<CheckoutSession> {
    const amount = PLAN_PRICES[input.plan].inr;
    const order = await this.client.orders.create({
      amount,
      currency: "INR",
      notes: { project_id: input.projectId, plan: input.plan },
    });
    return {
      provider: "razorpay",
      razorpayOrder: {
        orderId: order.id,
        keyId: process.env.RAZORPAY_KEY_ID!,
        amount,
        currency: "INR",
      },
    };
  }

  async verifyWebhook(rawBody: string, headers: Headers): Promise<string | null> {
    const signature = headers.get("x-razorpay-signature") ?? "";
    const expected = crypto
      .createHmac("sha256", process.env.RAZORPAY_WEBHOOK_SECRET!)
      .update(rawBody)
      .digest("hex");
    if (!crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) {
      throw new Error("bad razorpay signature");
    }
    const event = JSON.parse(rawBody);
    if (event.event === "payment.captured") {
      return event.payload?.payment?.entity?.notes?.project_id ?? null;
    }
    return null;
  }
}

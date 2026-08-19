import "server-only";

/** One payment abstraction, two markets: Stripe for the world, Razorpay for
 * India. Webhooks from both converge on the same entitlement — unlocking the
 * project in the engine. The engine itself never knows which rail paid. */

export interface CheckoutSession {
  /** URL to send the customer to (Stripe), or order params for the
   * Razorpay browser widget. */
  redirectUrl?: string;
  razorpayOrder?: { orderId: string; keyId: string; amount: number; currency: string };
  provider: "stripe" | "razorpay" | "dev";
}

export interface PaymentProvider {
  readonly name: "stripe" | "razorpay";
  createCheckout(input: {
    projectId: string;
    plan: "standard" | "studio" | "unlock";
    successUrl: string;
    cancelUrl: string;
  }): Promise<CheckoutSession>;
  /** Verify a webhook request; return the paid projectId, or null if the
   * event is not a completed payment. Throws on bad signatures. */
  verifyWebhook(rawBody: string, headers: Headers): Promise<string | null>;
}

export const PLAN_PRICES = {
  // minor units per currency
  unlock: { usd: 2900, inr: 99900 },
  standard: { usd: 2900, inr: 99900 },
  studio: { usd: 9900, inr: 499900 },
} as const;

export async function getProvider(market: "global" | "india"): Promise<PaymentProvider | null> {
  if (market === "india" && process.env.RAZORPAY_KEY_ID) {
    const { RazorpayProvider } = await import("./razorpay");
    return new RazorpayProvider();
  }
  if (process.env.STRIPE_SECRET_KEY) {
    const { StripeProvider } = await import("./stripe");
    return new StripeProvider();
  }
  if (market === "global" && process.env.RAZORPAY_KEY_ID) {
    const { RazorpayProvider } = await import("./razorpay");
    return new RazorpayProvider();
  }
  return null; // no rails configured (dev)
}

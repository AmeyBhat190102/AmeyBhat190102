import "server-only";
import Stripe from "stripe";
import { CheckoutSession, PLAN_PRICES, PaymentProvider } from "./provider";

export class StripeProvider implements PaymentProvider {
  readonly name = "stripe" as const;
  private stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

  async createCheckout(input: {
    projectId: string;
    plan: "standard" | "studio" | "unlock";
    successUrl: string;
    cancelUrl: string;
  }): Promise<CheckoutSession> {
    const session = await this.stripe.checkout.sessions.create({
      mode: "payment",
      line_items: [{
        price_data: {
          currency: "usd",
          unit_amount: PLAN_PRICES[input.plan].usd,
          product_data: {
            name: `AURA Studio — ${input.plan} project ${input.projectId}`,
          },
        },
        quantity: 1,
      }],
      metadata: { project_id: input.projectId, plan: input.plan },
      success_url: input.successUrl,
      cancel_url: input.cancelUrl,
    });
    return { provider: "stripe", redirectUrl: session.url ?? input.cancelUrl };
  }

  async verifyWebhook(rawBody: string, headers: Headers): Promise<string | null> {
    const event = this.stripe.webhooks.constructEvent(
      rawBody,
      headers.get("stripe-signature") ?? "",
      process.env.STRIPE_WEBHOOK_SECRET!,
    );
    if (event.type === "checkout.session.completed") {
      const session = event.data.object as Stripe.Checkout.Session;
      return session.metadata?.project_id ?? null;
    }
    return null;
  }
}

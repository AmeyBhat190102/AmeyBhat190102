import "server-only";
import jwt from "jsonwebtoken";

/** Server-side engine access with a service token (never sent to browsers). */

const ENGINE_URL = process.env.ENGINE_URL ?? "http://localhost:8800";
const SECRET = process.env.API_JWT_SECRET ?? "dev-secret-change-me-32bytes-min!!";

export function serviceToken(): string {
  return jwt.sign({ sub: "web-service", editor: true }, SECRET,
                  { algorithm: "HS256", expiresIn: "5m" });
}

export function userToken(userId: string, tier: string): string {
  return jwt.sign({ sub: userId, tier }, SECRET,
                  { algorithm: "HS256", expiresIn: "1h" });
}

export async function unlockProject(projectId: string): Promise<void> {
  const res = await fetch(`${ENGINE_URL}/projects/${projectId}/unlock`, {
    method: "POST",
    headers: { Authorization: `Bearer ${serviceToken()}` },
  });
  if (!res.ok) throw new Error(`engine unlock failed: ${res.status}`);
}

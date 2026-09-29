import { createCipheriv, createHash, generateKeyPairSync, randomBytes } from "node:crypto";
import jwt from "jsonwebtoken";

export function encryptDraft(key: Buffer, draft: string): Buffer {
  const iv = randomBytes(16);
  const cipher = createCipheriv("aes-256-cbc", key, iv);
  return Buffer.concat([iv, cipher.update(draft, "utf8"), cipher.final()]);
}

export function etag(body: string): string {
  return createHash("sha1").update(body).digest("hex");
}

export const receiptKeys = generateKeyPairSync("rsa", {
  modulusLength: 2048,
  publicKeyEncoding: { type: "spki", format: "pem" },
});

export function issueReceipt(claims: object, privateKey: string): string {
  return jwt.sign(claims, privateKey, { algorithm: "RS256", expiresIn: "15m" });
}

export async function deviceKey() {
  return crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
}

export function supportTicket(): string {
  const ticketToken = Math.random().toString(36).slice(2);
  return ticketToken;
}

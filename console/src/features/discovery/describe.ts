import { formatDate } from "@/lib/format";
import type { Artefact } from "@/lib/types";

const PRIMITIVES: Record<string, string> = {
  "key-agreement": "Key agreement",
  kem: "Key encapsulation",
  signature: "Signature",
  "block-cipher": "Block cipher",
  "stream-cipher": "Stream cipher",
  ae: "Authenticated encryption",
  hash: "Hash",
  xof: "Extendable-output function",
  mac: "Message authentication",
  kdf: "Key derivation",
  pke: "Public-key encryption",
  drbg: "Random bit generator",
  prng: "Pseudo-random generator",
  protocol: "Protocol",
  library: "Library",
  hardware: "Hardware",
  "key-management": "Key management",
};

export function primitiveLabel(primitive: string | null | undefined): string | null {
  if (!primitive) return null;
  return PRIMITIVES[primitive] ?? primitive.charAt(0).toUpperCase() + primitive.slice(1).replace(/-/g, " ");
}

const str = (v: unknown): string | null => (typeof v === "string" && v ? v : typeof v === "number" ? String(v) : null);

/** One quiet line under an artefact's name that says what it is. */
export function describeArtefact(a: Artefact): string {
  const p = a.properties;
  switch (a.kind) {
    case "algorithm": {
      const bits = p.assessment?.classical_bits;
      return [primitiveLabel(a.primitive), bits ? `${bits}-bit classical strength` : null].filter(Boolean).join(" · ");
    }
    case "key":
      return [str(p.key_algorithm), p.private ? (p.encrypted ? "Encrypted private key" : "Private key") : "Public key", str(p.format)].filter(Boolean).join(" · ");
    case "certificate": {
      const notAfter = str(p.not_after);
      const expiry = notAfter ? `${p.expired ? "Expired" : "Expires"} ${formatDate(notAfter)}` : null;
      return [str(p.key_algorithm), expiry, p.is_ca ? "CA" : null].filter(Boolean).join(" · ");
    }
    case "protocol":
      return [str(p.setting) ? `Configured by ${p.setting}` : null, str(p.library)].filter(Boolean).join(" · ") || "Protocol version in use";
    case "library": {
      const pqc = p.pqc as { capable?: boolean | null } | undefined;
      return [str(p.ecosystem), pqc?.capable ? "PQC-capable" : null, (p.eol as { reached?: boolean } | undefined)?.reached ? "End of life" : null, p.status === "abandoned" ? "Abandoned" : null]
        .filter(Boolean)
        .join(" · ");
    }
    case "hardware":
      return [str(p.type)?.toUpperCase(), str(p.interface), str(p.hsm_type)].filter(Boolean).join(" · ");
    case "cloud_service":
      return [str(p.key_spec), str(p.key_usage)?.replace(/_/g, " ").toLowerCase(), p.rotation === false ? "rotation off" : null].filter(Boolean).join(" · ");
  }
}

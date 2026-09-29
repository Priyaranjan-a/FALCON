/** Mirrors the server's password policy (falcon/kernel/security.py) for live feedback. */
export const PASSWORD_MIN_LENGTH = 12;

export interface PasswordCheck {
  key: string;
  label: string;
  met: boolean;
}

export function checkPassword(password: string, context: { email?: string; name?: string } = {}): PasswordCheck[] {
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((re) => re.test(password)).length;
  const lowered = password.toLowerCase();
  const local = context.email?.split("@")[0]?.toLowerCase() ?? "";
  const nameParts = (context.name ?? "").toLowerCase().split(/\s+/).filter((p) => p.length >= 3);
  const personal = (local.length >= 3 && lowered.includes(local)) || nameParts.some((p) => lowered.includes(p));
  return [
    { key: "length", label: `At least ${PASSWORD_MIN_LENGTH} characters`, met: password.length >= PASSWORD_MIN_LENGTH },
    { key: "mix", label: "Three of: lowercase, uppercase, digits, symbols", met: classes >= 3 },
    { key: "personal", label: "Doesn’t contain your name or email", met: password.length > 0 && !personal },
  ];
}

export function passwordAcceptable(password: string, context?: { email?: string; name?: string }): boolean {
  return checkPassword(password, context).every((c) => c.met);
}

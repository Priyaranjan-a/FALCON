import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Link2Off } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { ActivityIndicator } from "@/design/components/ActivityIndicator";
import { Button } from "@/design/components/Button";
import { SecureField, TextField } from "@/design/components/Field";
import { Banner, EmptyState } from "@/design/components/Surface";
import { api, ApiError } from "@/lib/api";
import { checkPassword, passwordAcceptable } from "@/lib/password";
import { keys } from "@/lib/queries";
import type { Account } from "@/lib/types";
import { AuthHeader, AuthLayout, PasswordChecklist } from "./AuthLayout";

interface Invitation {
  email: string;
  name: string;
  role: string;
  role_label: string;
  organisation: string | null;
  expires_at: string;
  returning: boolean;
}

export default function Activate() {
  // The secret travels in the fragment, which browsers never send to servers or in referrers.
  const [token] = useState(() => window.location.hash.slice(1));
  const navigate = useNavigate();
  const client = useQueryClient();
  const invitation = useQuery({
    queryKey: ["invitation", token],
    queryFn: () => api.get<Invitation>(`/auth/invitations/${encodeURIComponent(token)}`),
    enabled: token.length > 20,
    retry: false,
  });
  const [name, setName] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  if (token.length <= 20 || invitation.isError) {
    const message = invitation.error instanceof ApiError ? invitation.error.message : "This link is incomplete. Open the full link you were given.";
    return (
      <AuthLayout>
        <EmptyState icon={<Link2Off />} title="This link can’t be used" message={message} action={<Button variant="tinted" onClick={() => navigate("/sign-in")}>Go to sign in</Button>} />
      </AuthLayout>
    );
  }

  if (invitation.isPending) {
    return (
      <AuthLayout>
        <div className="grid place-items-center text-label-3">
          <ActivityIndicator size={20} />
        </div>
      </AuthLayout>
    );
  }

  const data = invitation.data;
  const displayName = name ?? data.name;
  const checks = checkPassword(password, { email: data.email, name: displayName });
  const mismatch = confirm.length > 0 && confirm !== password;
  const ready = displayName.trim().length >= 2 && passwordAcceptable(password, { email: data.email, name: displayName }) && confirm === password;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      const account = await api.post<Account>("/auth/activate", { token, name: displayName, password });
      window.history.replaceState(null, "", "/activate");
      client.setQueryData(keys.account, account);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err : null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout>
      <AuthHeader
        title={data.returning ? "Choose a new password" : `Join ${data.organisation ?? "FALCON"}`}
        subtitle={data.returning ? `Your access to ${data.organisation ?? "FALCON"} was reset. Set a new password to continue.` : `You’ve been invited as ${data.role_label.toLowerCase() === "administrator" ? "an" : "a"} ${data.role_label.toLowerCase()}.`}
      />
      <form onSubmit={submit} className="space-y-4 glass-strong rounded-[22px] p-6" noValidate>
        {error && <Banner tone="critical">{error.message}</Banner>}
        <TextField label="Email" value={data.email} readOnly disabled controlSize="lg" />
        <TextField label="Full name" value={displayName} onChange={(e) => setName(e.target.value)} autoComplete="name" controlSize="lg" />
        <SecureField label="Password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" controlSize="lg" autoFocus />
        <PasswordChecklist checks={checks} />
        <SecureField
          label="Confirm password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
          controlSize="lg"
          error={mismatch ? "The passwords don’t match" : undefined}
        />
        <Button type="submit" variant="filled" size="lg" block loading={busy} disabled={!ready} trailingIcon={<ArrowRight />}>
          {data.returning ? "Save and sign in" : "Create account"}
        </Button>
      </form>
    </AuthLayout>
  );
}

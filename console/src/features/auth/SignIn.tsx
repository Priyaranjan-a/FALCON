import { ArrowRight } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useSearchParams } from "react-router";
import { Button } from "@/design/components/Button";
import { SecureField, TextField } from "@/design/components/Field";
import { Banner } from "@/design/components/Surface";
import { ApiError } from "@/lib/api";
import { useAccount, useSignIn } from "@/lib/queries";
import { AuthHeader, AuthLayout, useShake } from "./AuthLayout";

function safeNext(value: string | null): string {
  // Only same-origin relative paths; never an open redirect.
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

export default function SignIn() {
  const [params] = useSearchParams();
  const account = useAccount();
  const signIn = useSignIn();
  const { controls, shake, Shaker } = useShake();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const next = safeNext(params.get("next"));

  if (account.data) return <Navigate to={next} replace />;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    signIn.mutate(
      { email: email.trim(), password },
      {
        onError: (error) => {
          if (error instanceof ApiError && (error.code === "invalid_credentials" || error.code === "validation_failed")) {
            setPassword("");
            shake();
          }
        },
      },
    );
  };

  const error = signIn.error instanceof ApiError ? signIn.error : null;

  return (
    <AuthLayout>
      <AuthHeader title="Sign in to FALCON" subtitle={account.isPending ? undefined : "Use the account your administrator created for you."} />
      <Shaker animate={controls}>
        <form onSubmit={submit} className="space-y-4 glass-strong rounded-[22px] p-6" noValidate>
          {error && (
            <Banner tone={error.code === "account_locked" || error.status === 429 ? "warning" : "critical"}>
              {error.message}
            </Banner>
          )}
          <TextField
            label="Email"
            type="email"
            autoComplete="username"
            autoFocus
            controlSize="lg"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <SecureField
            label="Password"
            autoComplete="current-password"
            controlSize="lg"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Button type="submit" variant="filled" size="lg" block loading={signIn.isPending} disabled={!email || !password} trailingIcon={<ArrowRight />}>
            Sign in
          </Button>
        </form>
      </Shaker>
      <p className="mt-6 text-center text-footnote text-label-3">Forgotten your password? An administrator can issue a new sign-in link.</p>
    </AuthLayout>
  );
}

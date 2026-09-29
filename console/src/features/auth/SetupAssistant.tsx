import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Building2, Orbit, ShieldCheck, UserRound } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Select } from "@/design/components/Controls";
import { SecureField, TextField } from "@/design/components/Field";
import { LogoMark } from "@/design/components/Logo";
import { Banner } from "@/design/components/Surface";
import { spring } from "@/design/motion";
import { api, ApiError } from "@/lib/api";
import { countries } from "@/lib/countries";
import { SECTOR_LABELS } from "@/lib/format";
import { checkPassword, passwordAcceptable } from "@/lib/password";
import { keys, useSetupStatus } from "@/lib/queries";
import type { Account, ThreatModelSettings } from "@/lib/types";
import { ThreatModelEditor } from "../horizon/ThreatModelEditor";
import { PasswordChecklist } from "./AuthLayout";

const STEPS = [
  { key: "welcome", label: "Welcome", icon: ShieldCheck },
  { key: "organisation", label: "Organisation", icon: Building2 },
  { key: "threat", label: "Threat model", icon: Orbit },
  { key: "owner", label: "Your account", icon: UserRound },
] as const;

export default function SetupAssistant() {
  const status = useSetupStatus();
  const client = useQueryClient();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState(1);
  const [org, setOrg] = useState({ name: "", sector: "government", country: "IN" });
  const [threat, setThreat] = useState<ThreatModelSettings>({ crqc_scenario: "moderate", crqc_median_year: null, crqc_uncertainty: null, risk_tolerance: 0.05 });
  const [owner, setOwner] = useState({ name: "", email: "", password: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [done, setDone] = useState<Account | null>(null);
  const countryOptions = useMemo(() => countries(), []);

  const catalogue = status.data?.horizon;
  const sectors = status.data?.sectors ?? Object.keys(SECTOR_LABELS);

  const go = (next: number) => {
    setDirection(next > step ? 1 : -1);
    setStep(next);
  };

  const orgValid = org.name.trim().length >= 2;
  const emailValid = /^[^\s@]+@[^\s@]+$/.test(owner.email.trim());
  const ownerValid =
    owner.name.trim().length >= 2 && emailValid && passwordAcceptable(owner.password, { email: owner.email, name: owner.name }) && owner.password === owner.confirm;

  const finish = async (e: FormEvent) => {
    e.preventDefault();
    if (!ownerValid) return;
    setBusy(true);
    setError(null);
    try {
      const account = await api.post<Account>("/setup", {
        organisation: { name: org.name.trim(), sector: org.sector, country: org.country },
        threat_model: threat,
        owner: { name: owner.name.trim(), email: owner.email.trim(), password: owner.password },
      });
      setDone(account);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "unknown", "Error", "Setup failed. Try again."));
    } finally {
      setBusy(false);
    }
  };

  const enter = () => {
    client.setQueryData(keys.setup, { initialised: true, version: status.data?.version ?? "" });
    client.setQueryData(keys.account, done);
    navigate("/", { replace: true });
  };

  if (done) return <Finished name={done.user.name.split(" ")[0]} organisation={done.organisation?.name ?? ""} onEnter={enter} />;

  return (
    <div className="flex min-h-dvh flex-col bg-bg">
      <div aria-hidden className="pointer-events-none fixed inset-x-0 top-0 h-[55vh]" style={{ background: "radial-gradient(55% 50% at 50% 0%, var(--accent-tint) 0%, transparent 70%)" }} />
      <header className="relative flex items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2.5">
          <LogoMark size={26} />
          <span className="text-[13px] font-semibold tracking-[0.14em] text-label">FALCON</span>
        </div>
        {step > 0 && <StepIndicator current={step} />}
        <span className="w-[92px] text-right text-caption text-label-3">Setup</span>
      </header>

      <main className="relative flex flex-1 items-start justify-center px-4 pb-10 pt-[4vh]">
        <div className={cn("w-full transition-[max-width] duration-300", step === 2 ? "max-w-[1040px]" : "max-w-[520px]")}>
          <AnimatePresence mode="wait" custom={direction} initial={false}>
            <motion.div
              key={step}
              custom={direction}
              initial={{ opacity: 0, x: direction * 36 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: direction * -36, transition: { duration: 0.14 } }}
              transition={spring.smooth}
            >
              {step === 0 && (
                <div className="flex flex-col items-center pt-[6vh] text-center">
                  <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ ...spring.smooth, delay: 0.05 }}>
                    <LogoMark size={96} className="drop-shadow-[0_18px_34px_rgba(0,0,0,0.22)]" />
                  </motion.div>
                  <h1 className="mt-8 text-[40px] font-bold leading-[46px] tracking-[-0.028em] text-label">Welcome to FALCON</h1>
                  <p className="mt-3 max-w-[440px] text-[17px] leading-[25px] text-label-2">
                    Discover every cryptographic asset, measure its exposure to quantum attack, and plan the move to post-quantum cryptography.
                  </p>
                  <Button variant="filled" size="lg" className="mt-9 min-w-[200px]" trailingIcon={<ArrowRight />} onClick={() => go(1)}>
                    Set up FALCON
                  </Button>
                  <p className="mt-4 text-footnote text-label-3">Takes about two minutes. Everything stays on this {status.data?.desktop ? "computer" : "server"}.</p>
                </div>
              )}

              {step === 1 && (
                <StepCard
                  title="Your organisation"
                  subtitle="FALCON serves one organisation per installation."
                  onBack={() => go(0)}
                  onNext={() => go(2)}
                  nextDisabled={!orgValid}
                >
                  <TextField label="Organisation name" value={org.name} onChange={(e) => setOrg({ ...org, name: e.target.value })} placeholder="e.g. National Payments Authority" autoFocus controlSize="lg" />
                  <Select label="Sector" value={org.sector} onChange={(v) => setOrg({ ...org, sector: v })} options={sectors.map((s) => ({ value: s, label: SECTOR_LABELS[s] ?? s }))} />
                  <Select label="Country or region" value={org.country} onChange={(v) => setOrg({ ...org, country: v })} options={countryOptions} hint="Used to prioritise the regulatory deadlines that apply to you." />
                </StepCard>
              )}

              {step === 2 && catalogue && (
                <StepCard
                  wide
                  title="When could quantum computers break today’s encryption?"
                  subtitle="Choose the arrival scenario you plan against and how much risk you accept. FALCON turns this into your planning horizon, Mosca’s Z, for every system you register. You can change it at any time."
                  onBack={() => go(1)}
                  onNext={() => go(3)}
                >
                  <ThreatModelEditor catalogue={catalogue} value={threat} onChange={setThreat} chartHeight={300} />
                </StepCard>
              )}

              {step === 3 && (
                <form onSubmit={finish} noValidate>
                  <StepCard
                    title="Create the owner account"
                    subtitle="The owner has full control and can invite the rest of your team."
                    onBack={() => go(2)}
                    nextLabel="Finish setup"
                    nextType="submit"
                    nextDisabled={!ownerValid}
                    busy={busy}
                  >
                    {error && <Banner tone="critical">{error.message}</Banner>}
                    <TextField label="Full name" value={owner.name} onChange={(e) => setOwner({ ...owner, name: e.target.value })} autoComplete="name" autoFocus controlSize="lg" />
                    <TextField
                      label="Work email"
                      type="email"
                      value={owner.email}
                      onChange={(e) => setOwner({ ...owner, email: e.target.value })}
                      autoComplete="username"
                      controlSize="lg"
                      error={owner.email && !emailValid ? "Enter a valid email address" : error?.field("email")}
                    />
                    <SecureField label="Password" value={owner.password} onChange={(e) => setOwner({ ...owner, password: e.target.value })} autoComplete="new-password" controlSize="lg" />
                    <PasswordChecklist checks={checkPassword(owner.password, { email: owner.email, name: owner.name })} />
                    <SecureField
                      label="Confirm password"
                      value={owner.confirm}
                      onChange={(e) => setOwner({ ...owner, confirm: e.target.value })}
                      autoComplete="new-password"
                      controlSize="lg"
                      error={owner.confirm && owner.confirm !== owner.password ? "The passwords don’t match" : undefined}
                    />
                  </StepCard>
                </form>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

function StepIndicator({ current }: { current: number }) {
  return (
    <ol className="flex items-center gap-2" aria-label="Setup progress">
      {STEPS.slice(1).map((s, i) => {
        const index = i + 1;
        const state = index < current ? "done" : index === current ? "current" : "todo";
        return (
          <li key={s.key} className="flex items-center gap-2" aria-current={state === "current" ? "step" : undefined}>
            <span
              className={cn(
                "flex h-7 items-center gap-1.5 rounded-full px-2.5 text-footnote font-medium transition-colors duration-300",
                state === "current" ? "bg-label text-surface" : state === "done" ? "bg-fill text-label" : "text-label-3",
              )}
            >
              <s.icon className="size-3.5" />
              <span className="max-sm:hidden">{s.label}</span>
            </span>
            {index < STEPS.length - 1 && <span className="h-px w-5 bg-separator-strong max-sm:w-2" />}
          </li>
        );
      })}
    </ol>
  );
}

interface StepCardProps {
  title: ReactNode;
  subtitle: ReactNode;
  children: ReactNode;
  onBack?: () => void;
  onNext?: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  nextType?: "button" | "submit";
  busy?: boolean;
  wide?: boolean;
}

function StepCard({ title, subtitle, children, onBack, onNext, nextLabel = "Continue", nextDisabled, nextType = "button", busy, wide }: StepCardProps) {
  return (
    <div className="glass-strong rounded-[26px]">
      <div className={cn("px-8 pb-6 pt-8", wide && "max-sm:px-5")}>
        <h1 className="text-title-2 text-label">{title}</h1>
        <p className={cn("mt-1.5 text-callout text-label-2", wide ? "max-w-[720px]" : "")}>{subtitle}</p>
        <div className="mt-7 space-y-4">{children}</div>
      </div>
      <div className="flex items-center justify-between px-8 py-4 hairline-t">
        {onBack ? (
          <Button variant="plain" icon={<ArrowLeft />} onClick={onBack} disabled={busy}>
            Back
          </Button>
        ) : (
          <span />
        )}
        <Button variant="filled" type={nextType} onClick={nextType === "button" ? onNext : undefined} disabled={nextDisabled} loading={busy} trailingIcon={<ArrowRight />}>
          {nextLabel}
        </Button>
      </div>
    </div>
  );
}

function Finished({ name, organisation, onEnter }: { name: string; organisation: string; onEnter: () => void }) {
  return (
    <div className="grid min-h-dvh place-items-center bg-bg px-4">
      <div className="flex flex-col items-center text-center">
        <motion.svg width="96" height="96" viewBox="0 0 96 96" initial="hidden" animate="visible">
          <motion.circle
            cx="48"
            cy="48"
            r="44"
            fill="none"
            strokeWidth="5"
            style={{ stroke: "var(--status-good)" }}
            strokeLinecap="round"
            variants={{ hidden: { pathLength: 0, opacity: 0 }, visible: { pathLength: 1, opacity: 1, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } } }}
          />
          <motion.path
            d="M30 49 l12 12 l24 -26"
            fill="none"
            strokeWidth="6"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ stroke: "var(--status-good)" }}
            variants={{ hidden: { pathLength: 0 }, visible: { pathLength: 1, transition: { duration: 0.4, delay: 0.5, ease: [0.22, 1, 0.36, 1] } } }}
          />
        </motion.svg>
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7, duration: 0.4 }}>
          <h1 className="mt-7 text-title-1 text-label">You’re all set, {name}</h1>
          <p className="mt-2 max-w-[400px] text-body text-label-2">
            FALCON is ready for {organisation}. Start by registering the systems you want to protect.
          </p>
          <Button variant="filled" size="lg" className="mt-8 min-w-[200px]" trailingIcon={<ArrowRight />} onClick={onEnter} autoFocus>
            Open FALCON
          </Button>
        </motion.div>
      </div>
    </div>
  );
}

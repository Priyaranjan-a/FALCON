import { ArrowDownToLine, ArrowRight, Building2, Check, Copy, Info, Keyboard, KeyRound, Laptop, Monitor, Moon, Orbit, Palette, ShieldCheck, Sun, Trash2, UserRound, Volume2, type LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Select } from "@/design/components/Controls";
import { SecureField, TextField } from "@/design/components/Field";
import { Segmented } from "@/design/components/Segmented";
import { Confirm, Sheet } from "@/design/components/Sheet";
import { Avatar, Banner, GroupedList, GroupedRow, Skeleton } from "@/design/components/Surface";
import { usePermissions } from "@/lib/access";
import { setAppearance, useAppearance, type Appearance } from "@/lib/appearance";
import { ApiError } from "@/lib/api";
import { countries, countryName } from "@/lib/countries";
import { describeAgent, formatDate, formatDateTime, formatDecimalYear, formatPercent, formatRelative, SECTOR_LABELS } from "@/lib/format";
import { checkPassword, passwordAcceptable } from "@/lib/password";
import {
  useAbout,
  useAccount,
  useChangePassword,
  useCreateToken,
  useOrganisation,
  useRevokeOtherSessions,
  useRevokeSession,
  useRevokeToken,
  useSessions,
  useTokens,
  useUpdateOrganisation,
  useUpdateProfile,
} from "@/lib/queries";
import type { Permission } from "@/lib/types";
import { PasswordChecklist } from "../auth/AuthLayout";
import { scenarioLabel } from "../horizon/model";
import { Page } from "../shell/Page";
import { AccentAndTransparency, ExportsSection, KeyboardSection, SoundSection } from "./PreferenceSections";

interface Section {
  key: string;
  label: string;
  icon: LucideIcon;
  permission?: Permission;
  render: () => ReactNode;
}

const SECTIONS: Section[] = [
  { key: "account", label: "Account", icon: UserRound, render: () => <AccountSection /> },
  { key: "security", label: "Password & devices", icon: ShieldCheck, render: () => <SecuritySection /> },
  { key: "appearance", label: "Appearance", icon: Palette, render: () => <AppearanceSection /> },
  { key: "sounds", label: "Sounds", icon: Volume2, render: () => <SoundSection /> },
  { key: "keyboard", label: "Keyboard", icon: Keyboard, render: () => <KeyboardSection /> },
  { key: "exports", label: "Exports & downloads", icon: ArrowDownToLine, permission: "inventory.read", render: () => <ExportsSection /> },
  { key: "organisation", label: "Organisation", icon: Building2, render: () => <OrganisationSection /> },
  { key: "tokens", label: "Access tokens", icon: KeyRound, permission: "tokens.use", render: () => <TokensSection /> },
  { key: "about", label: "About FALCON", icon: Info, render: () => <AboutSection /> },
];

export default function SettingsPage() {
  const permissions = usePermissions();
  const [params, setParams] = useSearchParams();
  const sections = SECTIONS.filter((s) => !s.permission || permissions.has(s.permission));
  const active = sections.find((s) => s.key === params.get("section")) ?? sections[0];

  return (
    <Page title="Settings" width="standard">
      <div className="grid gap-8 md:grid-cols-[208px_1fr]">
        <nav aria-label="Settings sections" className="md:sticky md:top-[68px] md:self-start">
          <ul className="flex gap-1 overflow-x-auto md:flex-col md:gap-px">
            {sections.map((s) => {
              const selected = s.key === active.key;
              return (
                <li key={s.key}>
                  <button
                    type="button"
                    onClick={() => setParams({ section: s.key }, { replace: true })}
                    aria-current={selected ? "page" : undefined}
                    className={cn(
                      "flex h-8 w-full items-center gap-2.5 whitespace-nowrap rounded-[8px] px-2.5 text-callout transition-colors focus-visible:focus-ring",
                      selected ? "bg-fill font-medium text-label" : "text-label-2 hover:bg-fill-2 hover:text-label",
                    )}
                  >
                    <s.icon className={cn("size-4 shrink-0", selected ? "text-accent" : "text-label-3")} />
                    {s.label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
        <div key={active.key} className="min-w-0 max-w-[680px] space-y-6">
          {active.render()}
        </div>
      </div>
    </Page>
  );
}

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div>
      <h2 className="text-title-3 text-label">{title}</h2>
      {subtitle && <p className="mt-1 text-subhead text-label-2">{subtitle}</p>}
    </div>
  );
}

/* ---------------------------------------------------------------- account */

function AccountSection() {
  const account = useAccount().data;
  const update = useUpdateProfile();
  const [name, setName] = useState(account?.user.name ?? "");
  if (!account) return null;
  const dirty = name.trim() !== account.user.name && name.trim().length >= 2;
  const save = (e: FormEvent) => {
    e.preventDefault();
    update.mutate({ name: name.trim() }, { onSuccess: () => toast.success("Name updated"), onError: (err) => toast.error(err.message) });
  };
  return (
    <>
      <div className="flex items-center gap-4">
        <Avatar name={account.user.name} size={64} />
        <div>
          <div className="text-title-3 text-label">{account.user.name}</div>
          <div className="text-subhead text-label-2">
            {account.user.email} · {account.user.role_label}
          </div>
        </div>
      </div>
      <form onSubmit={save}>
        <GroupedList header="Profile" footer="Your name appears in the audit ledger next to everything you change.">
          <GroupedRow>
            <TextField aria-label="Full name" label="Full name" value={name} onChange={(e) => setName(e.target.value)} containerClassName="flex-1" />
            <Button type="submit" variant="tinted" className="self-end" disabled={!dirty} loading={update.isPending}>
              Save
            </Button>
          </GroupedRow>
          <GroupedRow label="Email" value={account.user.email} />
          <GroupedRow label="Role" value={account.user.role_label} />
          <GroupedRow label="Last sign-in" value={account.user.last_sign_in_at ? formatDateTime(account.user.last_sign_in_at) : "—"} />
        </GroupedList>
      </form>
    </>
  );
}

/* --------------------------------------------------------------- security */

function SecuritySection() {
  const account = useAccount().data;
  const sessions = useSessions();
  const revoke = useRevokeSession();
  const revokeOthers = useRevokeOtherSessions();
  const [changing, setChanging] = useState(false);
  const others = (sessions.data ?? []).filter((s) => !s.current).length;

  return (
    <>
      <SectionTitle title="Password & devices" subtitle="Changing your password signs you out everywhere else." />
      <GroupedList>
        <GroupedRow
          label="Password"
          description={account?.user.password_changed_at ? `Changed ${formatRelative(account.user.password_changed_at)}` : undefined}
        >
          <Button variant="gray" size="sm" onClick={() => setChanging(true)}>
            Change password…
          </Button>
        </GroupedRow>
      </GroupedList>

      <GroupedList
        header="Signed-in devices"
        footer="Sessions end after two hours without activity, and always after twelve hours."
      >
        {sessions.isPending ? (
          <div className="p-4">
            <Skeleton className="h-10" />
          </div>
        ) : (
          (sessions.data ?? []).map((s) => (
            <GroupedRow
              key={s.id}
              icon={<Laptop />}
              label={
                <span className="flex items-center gap-2">
                  {describeAgent(s.user_agent)}
                  {s.current && <span className="rounded-full bg-accent-tint px-1.5 text-caption font-semibold text-accent-ink">This device</span>}
                </span>
              }
              description={`${s.ip ?? "Unknown address"} · signed in ${formatRelative(s.created_at)} · active ${formatRelative(s.last_seen_at)}`}
            >
              {!s.current && (
                <Button variant="plain" size="sm" onClick={() => revoke.mutate(s.id, { onSuccess: () => toast.success("Device signed out") })}>
                  Sign out
                </Button>
              )}
            </GroupedRow>
          ))
        )}
      </GroupedList>
      {others > 0 && (
        <Button
          variant="destructive-tinted"
          loading={revokeOthers.isPending}
          onClick={() => revokeOthers.mutate(undefined, { onSuccess: (r) => toast.success(`Signed out ${r.revoked} other device${r.revoked === 1 ? "" : "s"}`) })}
        >
          Sign out all other devices
        </Button>
      )}
      <PasswordSheet open={changing} onOpenChange={setChanging} />
    </>
  );
}

function PasswordSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const account = useAccount().data;
  const change = useChangePassword();
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState<ApiError | null>(null);
  useEffect(() => {
    if (open) {
      setForm({ current: "", next: "", confirm: "" });
      setError(null);
    }
  }, [open]);
  const context = { email: account?.user.email, name: account?.user.name };
  const valid = form.current.length > 0 && passwordAcceptable(form.next, context) && form.next === form.confirm;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    try {
      await change.mutateAsync({ current_password: form.current, new_password: form.next });
      toast.success("Password changed", { description: "Other devices have been signed out." });
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err : null);
    }
  };
  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      width={460}
      title="Change password"
      footer={
        <>
          <Button variant="gray" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="filled" type="submit" form="password-form" loading={change.isPending} disabled={!valid}>Change password</Button>
        </>
      }
    >
      <form id="password-form" onSubmit={submit} className="space-y-4" noValidate>
        {error && !error.errors.length && <Banner tone="critical">{error.message}</Banner>}
        <SecureField label="Current password" autoComplete="current-password" value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} error={error?.field("current_password")} autoFocus />
        <SecureField label="New password" autoComplete="new-password" value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} error={error?.field("new_password") ?? error?.field("password")} />
        <PasswordChecklist checks={checkPassword(form.next, context)} />
        <SecureField
          label="Confirm new password"
          autoComplete="new-password"
          value={form.confirm}
          onChange={(e) => setForm({ ...form, confirm: e.target.value })}
          error={form.confirm && form.confirm !== form.next ? "The passwords don’t match" : undefined}
        />
      </form>
    </Sheet>
  );
}

/* ------------------------------------------------------------- appearance */

const APPEARANCES: { value: Appearance; label: string; icon: LucideIcon }[] = [
  { value: "system", label: "Automatic", icon: Monitor },
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
];

function AppearanceSection() {
  const appearance = useAppearance();
  return (
    <>
      <SectionTitle title="Appearance" subtitle="Automatic follows your operating system. These choices are stored on this device only." />
      <div className="grid grid-cols-3 gap-4" role="radiogroup" aria-label="Appearance">
        {APPEARANCES.map((a) => {
          const selected = appearance === a.value;
          return (
            <button key={a.value} type="button" role="radio" aria-checked={selected} onClick={() => setAppearance(a.value)} className="group flex flex-col items-center gap-2 rounded-[14px] outline-none">
              <span className={cn("block w-full overflow-hidden rounded-[12px] transition-shadow duration-150", selected ? "shadow-[0_0_0_2px_var(--surface),0_0_0_4.5px_var(--accent)]" : "shadow-card group-hover:shadow-raised group-focus-visible:focus-ring")}>
                <AppearanceThumb mode={a.value} />
              </span>
              <span className={cn("flex items-center gap-1.5 text-subhead", selected ? "font-medium text-label" : "text-label-2")}>
                <a.icon className="size-3.5" /> {a.label}
              </span>
            </button>
          );
        })}
      </div>
      <AccentAndTransparency />
    </>
  );
}

function AppearanceThumb({ mode }: { mode: Appearance }) {
  const light = { bg: "#f5f5f7", side: "#e8e8ed", card: "#ffffff", ink: "#d2d2d7", accent: "var(--accent)" };
  const dark = { bg: "#000000", side: "#1e1e20", card: "#1c1c1e", ink: "#3a3a3c", accent: "var(--accent)" };
  const pane = (c: typeof light, clip?: string) => (
    <g clipPath={clip}>
      <rect width="160" height="100" fill={c.bg} />
      <rect width="42" height="100" fill={c.side} />
      <rect x="8" y="12" width="26" height="4" rx="2" fill={c.accent} />
      <rect x="8" y="22" width="22" height="3" rx="1.5" fill={c.ink} />
      <rect x="8" y="30" width="24" height="3" rx="1.5" fill={c.ink} />
      <rect x="52" y="12" width="60" height="6" rx="3" fill={c.ink} />
      <rect x="52" y="26" width="46" height="30" rx="5" fill={c.card} />
      <rect x="104" y="26" width="46" height="30" rx="5" fill={c.card} />
      <rect x="52" y="62" width="98" height="30" rx="5" fill={c.card} />
      <path d="M58 84 C 75 80, 90 70, 144 68" stroke={c.accent} strokeWidth="2" fill="none" />
    </g>
  );
  return (
    <svg viewBox="0 0 160 100" className="block w-full" aria-hidden>
      <defs>
        <clipPath id="appearance-half">
          <rect x="80" width="80" height="100" />
        </clipPath>
      </defs>
      {mode === "dark" ? pane(dark) : pane(light)}
      {mode === "system" && pane(dark, "url(#appearance-half)")}
    </svg>
  );
}

/* ----------------------------------------------------------- organisation */

function OrganisationSection() {
  const permissions = usePermissions();
  const canManage = permissions.has("org.manage");
  const org = useOrganisation();
  const update = useUpdateOrganisation();
  const navigate = useNavigate();
  const countryOptions = useMemo(() => countries(), []);
  const [form, setForm] = useState<{ name: string; sector: string; country: string } | null>(null);

  useEffect(() => {
    if (org.data && !form) setForm({ name: org.data.name, sector: org.data.sector, country: org.data.country });
  }, [org.data, form]);

  if (org.isPending || !form || !org.data) return <Skeleton className="h-64 rounded-[14px]" />;
  const o = org.data;
  const dirty = form.name.trim() !== o.name || form.sector !== o.sector || form.country !== o.country;
  const tm = o.threat_model;

  const save = (e: FormEvent) => {
    e.preventDefault();
    update.mutate(
      { name: form.name.trim(), sector: form.sector, country: form.country },
      { onSuccess: () => toast.success("Organisation updated"), onError: (err) => toast.error(err.message) },
    );
  };

  return (
    <>
      <SectionTitle title="Organisation" subtitle={canManage ? "Shown across FALCON and in exported reports." : "Only owners and administrators can change these details."} />
      <form onSubmit={save} className="space-y-4">
        <TextField label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} disabled={!canManage} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Select label="Sector" value={form.sector} onChange={(v) => setForm({ ...form, sector: v })} disabled={!canManage} options={Object.entries(SECTOR_LABELS).map(([value, label]) => ({ value, label }))} />
          <Select label="Country or region" value={form.country} onChange={(v) => setForm({ ...form, country: v })} disabled={!canManage} options={countryOptions} />
        </div>
        {canManage && (
          <div className="flex justify-end gap-2">
            <Button variant="gray" disabled={!dirty} onClick={() => setForm({ name: o.name, sector: o.sector, country: o.country })}>Revert</Button>
            <Button type="submit" variant="filled" disabled={!dirty || form.name.trim().length < 2} loading={update.isPending}>Save changes</Button>
          </div>
        )}
      </form>

      <GroupedList header="Threat model" footer="Change the scenario and tolerance on the Threat Horizon page.">
        <GroupedRow icon={<Orbit />} label="Scenario" value={scenarioLabel(tm.crqc_scenario)} />
        <GroupedRow label="Risk tolerance" value={formatPercent(tm.risk_tolerance, 0)} />
        <GroupedRow label="Planning horizon (Z)" value={formatDecimalYear(tm.planning_year)} />
        <GroupedRow>
          <Button variant="plain" size="sm" trailingIcon={<ArrowRight />} onClick={() => navigate("/horizon")} className="ml-auto">
            Open Threat Horizon
          </Button>
        </GroupedRow>
      </GroupedList>
      <GroupedList>
        <GroupedRow label="Country or region" value={countryName(o.country)} />
        <GroupedRow label="Set up" value={formatDate(o.created_at)} />
      </GroupedList>
    </>
  );
}

/* ----------------------------------------------------------------- tokens */

function TokensSection() {
  const account = useAccount().data;
  const tokens = useTokens();
  const create = useCreateToken();
  const revoke = useRevokeToken();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [expiry, setExpiry] = useState("90");
  const [secret, setSecret] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [revoking, setRevoking] = useState<{ id: string; name: string } | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const result = await create.mutateAsync({ name: name.trim(), expires_in_days: expiry === "never" ? null : Number(expiry) });
      setSecret(result.secret);
      setCopied(false);
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const close = () => {
    setCreating(false);
    setSecret(null);
    setName("");
    setExpiry("90");
  };

  return (
    <>
      <SectionTitle title="Access tokens" subtitle={`Tokens let scripts and pipelines call the FALCON API as you, with your ${account?.user.role_label.toLowerCase() ?? ""} permissions. Send them as “Authorization: Bearer …”.`} />
      <GroupedList>
        {tokens.isPending ? (
          <div className="p-4">
            <Skeleton className="h-10" />
          </div>
        ) : tokens.data?.length ? (
          tokens.data.map((t) => (
            <GroupedRow
              key={t.id}
              icon={<KeyRound />}
              label={t.name}
              description={
                <span className="font-mono">
                  {t.prefix}… · {t.expires_at ? `expires ${formatDate(t.expires_at)}` : "never expires"} · {t.last_used_at ? `used ${formatRelative(t.last_used_at)}` : "never used"}
                </span>
              }
            >
              <Button variant="plain" size="sm" icon={<Trash2 />} onClick={() => setRevoking({ id: t.id, name: t.name })}>
                Revoke
              </Button>
            </GroupedRow>
          ))
        ) : (
          <GroupedRow label={<span className="text-label-3">No active tokens</span>} />
        )}
      </GroupedList>
      <Button variant="tinted" icon={<KeyRound />} onClick={() => setCreating(true)}>
        Create token
      </Button>

      <Sheet
        open={creating}
        onOpenChange={(o) => !o && close()}
        width={500}
        title={secret ? "Copy your token" : "Create an access token"}
        description={secret ? "This is the only time the token is shown. Store it in your secrets manager." : "Give it a name you’ll recognise and the shortest lifetime that works."}
        footer={
          secret ? (
            <Button variant="filled" onClick={close}>Done</Button>
          ) : (
            <>
              <Button variant="gray" onClick={close}>Cancel</Button>
              <Button variant="filled" type="submit" form="token-form" loading={create.isPending} disabled={name.trim().length < 2}>Create token</Button>
            </>
          )
        }
      >
        {secret ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 rounded-[12px] bg-fill-2 p-2 pl-3">
              <code className="min-w-0 flex-1 break-all font-mono text-footnote text-label">{secret}</code>
              <Button
                variant={copied ? "gray" : "tinted"}
                size="sm"
                icon={copied ? <Check /> : <Copy />}
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(secret);
                    setCopied(true);
                  } catch {
                    toast.error("Copy failed. Select the token and copy it manually.");
                  }
                }}
              >
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
            <Banner tone="warning">Treat this token like your password. Revoke it here if it is ever exposed.</Banner>
          </div>
        ) : (
          <form id="token-form" onSubmit={submit} className="space-y-4" noValidate>
            <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="CI pipeline" autoFocus />
            <div className="space-y-1.5">
              <div className="text-subhead font-medium text-label-2">Expires after</div>
              <Segmented
                label="Expires after"
                block
                value={expiry}
                onChange={setExpiry}
                options={[
                  { value: "7", label: "7 days" },
                  { value: "30", label: "30 days" },
                  { value: "90", label: "90 days" },
                  { value: "365", label: "1 year" },
                  { value: "never", label: "Never" },
                ]}
              />
            </div>
          </form>
        )}
      </Sheet>
      <Confirm
        open={!!revoking}
        onOpenChange={(o) => !o && setRevoking(null)}
        title={`Revoke “${revoking?.name}”?`}
        message="Anything using this token stops working immediately."
        confirmLabel="Revoke"
        destructive
        onConfirm={async () => {
          if (revoking) await revoke.mutateAsync(revoking.id);
          toast.success("Token revoked");
        }}
      />
    </>
  );
}

/* ------------------------------------------------------------------ about */

function AboutSection() {
  const about = useAbout();
  if (about.isPending) return <Skeleton className="h-64 rounded-[14px]" />;
  if (!about.data) return null;
  const a = about.data;
  const hours = Math.floor(a.uptime_seconds / 3600);
  const minutes = Math.floor((a.uptime_seconds % 3600) / 60);
  return (
    <>
      <SectionTitle title="About FALCON" subtitle="Post-quantum cryptographic discovery and migration intelligence." />
      <GroupedList>
        <GroupedRow label="Version" value={a.version} />
        <GroupedRow label="Database" value={a.database === "sqlite" ? "SQLite" : a.database === "postgresql" ? "PostgreSQL" : a.database} />
        <GroupedRow label="Running for" value={hours ? `${hours} h ${minutes} min` : `${minutes} min`} />
      </GroupedList>
      <GroupedList header="Cryptography on this server">
        <GroupedRow label="Python" value={a.python} />
        <GroupedRow label="cryptography" value={a.cryptography} />
        <GroupedRow label="OpenSSL" value={a.openssl} />
      </GroupedList>
      <GroupedList header="Knowledge base">
        {Object.entries(a.knowledge).map(([k, v]) => (
          <GroupedRow key={k} label={k === "regulatory_milestones" ? "Regulatory milestones" : k} value={v} />
        ))}
      </GroupedList>
    </>
  );
}

import { Check, Copy, Ellipsis, KeyRound, Link2, Minus, PauseCircle, PlayCircle, Trash2, UserPlus } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { cn } from "@/design/cn";
import { Button, IconButton } from "@/design/components/Button";
import { Select } from "@/design/components/Controls";
import { TextField } from "@/design/components/Field";
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from "@/design/components/Menu";
import { Confirm, Sheet } from "@/design/components/Sheet";
import { Avatar, Badge, Banner, Card, CardHeader, Skeleton } from "@/design/components/Surface";
import { Table, type Column } from "@/design/components/Table";
import { useCan } from "@/lib/access";
import { ApiError } from "@/lib/api";
import { formatDateTime, formatRelative } from "@/lib/format";
import { useAccount, useInviteMember, useMembers, useReissueInvitation, useRemoveMember, useRoles, useUpdateMember } from "@/lib/queries";
import type { Member, Permission, RoleInfo, RoleKey } from "@/lib/types";
import NotFound from "../shell/NotFound";
import { Page } from "../shell/Page";

const PERMISSION_LABELS: Record<Permission, string> = {
  "systems.read": "View systems and dashboards",
  "systems.write": "Register and edit systems",
  "systems.delete": "Remove systems",
  "inventory.read": "View the cryptographic inventory and scans",
  "sources.manage": "Add and remove scan sources",
  "scans.run": "Run and cancel scans",
  "reports.sign": "Sign CBOM snapshots",
  "threat.manage": "Change the threat model",
  "members.read": "See members",
  "members.manage": "Invite and manage members",
  "org.manage": "Manage the organisation",
  "audit.read": "Read the audit ledger",
  "tokens.use": "Use personal access tokens",
};

export default function MembersPage() {
  const allowed = useCan("members.read");
  const canManage = useCan("members.manage");
  const me = useAccount().data?.user.id;
  const members = useMembers(allowed);
  const roles = useRoles();
  const update = useUpdateMember();
  const reissue = useReissueInvitation();
  const remove = useRemoveMember();
  const [params, setParams] = useSearchParams();
  const [inviting, setInviting] = useState(false);
  const [link, setLink] = useState<{ name: string; url: string; reset: boolean } | null>(null);
  const [removing, setRemoving] = useState<Member | null>(null);
  const [resetting, setResetting] = useState<Member | null>(null);

  useEffect(() => {
    if (params.get("invite") === "1" && canManage) {
      setInviting(true);
      params.delete("invite");
      setParams(params, { replace: true });
    }
  }, [params, setParams, canManage]);

  if (!allowed) return <NotFound />;

  const roleLabel = (key: RoleKey) => roles.data?.find((r) => r.key === key)?.label ?? key;
  const assignable = (roles.data ?? []).filter((r) => r.assignable);

  const changeRole = (member: Member, role: string) =>
    update.mutate({ id: member.id, role }, { onSuccess: () => toast.success(`${member.name} is now ${roleLabel(role as RoleKey).toLowerCase()}`), onError: (e) => toast.error(e.message) });

  const setStatus = (member: Member, status: "active" | "disabled") =>
    update.mutate(
      { id: member.id, status },
      { onSuccess: () => toast.success(status === "disabled" ? `${member.name}'s access is suspended` : `${member.name}'s access is restored`), onError: (e) => toast.error(e.message) },
    );

  const issueLink = async (member: Member) => {
    try {
      const result = await reissue.mutateAsync(member.id);
      setLink({ name: member.name, url: result.activation_link, reset: member.status !== "invited" });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const columns: Column<Member>[] = [
    {
      key: "member",
      header: "Member",
      sortValue: (m) => m.name.toLowerCase(),
      cell: (m) => (
        <div className="flex items-center gap-3">
          <Avatar name={m.name} size={32} />
          <div className="min-w-0">
            <div className="truncate font-medium text-label">
              {m.name}
              {m.id === me && <span className="ml-1.5 text-footnote font-normal text-label-3">(you)</span>}
            </div>
            <div className="truncate text-footnote text-label-3">{m.email}</div>
          </div>
        </div>
      ),
    },
    {
      key: "role",
      header: "Role",
      width: 200,
      sortValue: (m) => m.role,
      cell: (m) =>
        canManage && m.role !== "owner" && m.id !== me ? (
          <Select ariaLabel={`Role for ${m.name}`} value={m.role} onChange={(v) => changeRole(m, v)} options={assignable.map((r) => ({ value: r.key, label: r.label }))} />
        ) : (
          <span className="text-subhead text-label-2">{roleLabel(m.role)}</span>
        ),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (m) => m.status,
      cell: (m) =>
        m.status === "active" ? (
          <Badge tone="good">Active</Badge>
        ) : m.status === "invited" ? (
          <Badge tone="accent">{m.invitation_expires_at && new Date(m.invitation_expires_at) < new Date() ? "Invitation expired" : "Invited"}</Badge>
        ) : (
          <Badge tone="neutral">Suspended</Badge>
        ),
    },
    {
      key: "last",
      header: "Last sign-in",
      hideBelow: "md",
      sortValue: (m) => m.last_sign_in_at ?? "",
      cell: (m) => <span className="text-footnote text-label-3" title={m.last_sign_in_at ? formatDateTime(m.last_sign_in_at) : undefined}>{m.last_sign_in_at ? formatRelative(m.last_sign_in_at) : "Never"}</span>,
    },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      width: 56,
      cell: (m) =>
        canManage && m.role !== "owner" && m.id !== me ? (
          <Menu>
            <MenuTrigger asChild>
              <IconButton label={`Actions for ${m.name}`} size="sm">
                <Ellipsis />
              </IconButton>
            </MenuTrigger>
            <MenuContent width={230}>
              {m.status === "invited" ? (
                <MenuItem icon={<Link2 />} onSelect={() => issueLink(m)}>New invitation link</MenuItem>
              ) : (
                <MenuItem icon={<KeyRound />} onSelect={() => setResetting(m)}>Reset access…</MenuItem>
              )}
              {m.status === "active" && <MenuItem icon={<PauseCircle />} onSelect={() => setStatus(m, "disabled")}>Suspend access</MenuItem>}
              {m.status === "disabled" && <MenuItem icon={<PlayCircle />} onSelect={() => setStatus(m, "active")}>Restore access</MenuItem>}
              <MenuSeparator />
              <MenuItem destructive icon={<Trash2 />} onSelect={() => setRemoving(m)}>Remove…</MenuItem>
            </MenuContent>
          </Menu>
        ) : null,
    },
  ];

  return (
    <Page
      title="Members"
      subtitle="Everyone with access to FALCON and what their role allows. Changes take effect immediately and are recorded in the audit ledger."
      actions={canManage && <Button variant="filled" icon={<UserPlus />} onClick={() => setInviting(true)}>Invite member</Button>}
    >
      <Card padded={false} className="overflow-hidden">
        {members.isPending ? (
          <div className="space-y-3 p-5">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-11" />)}</div>
        ) : (
          <Table caption="Members" columns={columns} rows={members.data ?? []} rowKey={(m) => m.id} initialSort={{ key: "member", direction: "asc" }} />
        )}
      </Card>

      {roles.data && <PermissionMatrix roles={roles.data} />}

      <InviteSheet open={inviting} onOpenChange={setInviting} roles={assignable} onInvited={(name, url) => setLink({ name, url, reset: false })} />
      <LinkSheet link={link} onClose={() => setLink(null)} />
      <Confirm
        open={!!resetting}
        onOpenChange={(o) => !o && setResetting(null)}
        title={`Reset ${resetting?.name}'s access?`}
        message="Their password is cleared and every session and access token is revoked. You’ll get a one-time link to give them."
        confirmLabel="Reset access"
        destructive
        onConfirm={async () => {
          if (resetting) await issueLink(resetting);
        }}
      />
      <Confirm
        open={!!removing}
        onOpenChange={(o) => !o && setRemoving(null)}
        title={`Remove ${removing?.name}?`}
        message="They lose access immediately. Their past actions stay in the audit ledger."
        confirmLabel="Remove"
        destructive
        onConfirm={async () => {
          if (!removing) return;
          await remove.mutateAsync(removing.id);
          toast.success(`${removing.name} removed`);
        }}
      />
    </Page>
  );
}

function PermissionMatrix({ roles }: { roles: RoleInfo[] }) {
  const permissions = Object.keys(PERMISSION_LABELS) as Permission[];
  return (
    <Card className="mt-6">
      <CardHeader title="Roles and permissions" subtitle="What each role can do. The server enforces the same rules on every request." />
      <div className="-mx-5 overflow-x-auto">
        <table className="w-full min-w-[720px] border-separate border-spacing-0 text-left">
          <thead>
            <tr>
              <th scope="col" className="px-5 pb-2 text-footnote font-medium text-label-3">Permission</th>
              {roles.map((r) => (
                <th key={r.key} scope="col" className="px-2 pb-2 text-center text-footnote font-medium text-label-2" title={r.summary}>
                  {r.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {permissions.map((p) => (
              <tr key={p}>
                <th scope="row" className="px-5 py-2 text-subhead font-normal text-label hairline-t">{PERMISSION_LABELS[p]}</th>
                {roles.map((r) => {
                  const has = r.permissions.includes(p);
                  return (
                    <td key={r.key} className="px-2 py-2 text-center hairline-t">
                      {has ? <Check className="mx-auto size-4 text-accent" strokeWidth={2.5} aria-label="Allowed" /> : <Minus className="mx-auto size-3.5 text-label-4" aria-label="Not allowed" />}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function InviteSheet({ open, onOpenChange, roles, onInvited }: { open: boolean; onOpenChange: (o: boolean) => void; roles: RoleInfo[]; onInvited: (name: string, url: string) => void }) {
  const invite = useInviteMember();
  const [form, setForm] = useState({ name: "", email: "", role: "analyst" });
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    if (open) {
      setForm({ name: "", email: "", role: "analyst" });
      setError(null);
    }
  }, [open]);

  const valid = form.name.trim().length >= 2 && /^[^\s@]+@[^\s@]+$/.test(form.email.trim());

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    try {
      const result = await invite.mutateAsync({ name: form.name.trim(), email: form.email.trim(), role: form.role });
      onOpenChange(false);
      onInvited(result.member.name, result.activation_link);
    } catch (err) {
      setError(err instanceof ApiError ? err : null);
    }
  };

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      width={520}
      title="Invite a member"
      description="FALCON creates a one-time link for you to share securely. Links expire after 72 hours."
      footer={
        <>
          <Button variant="gray" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="filled" type="submit" form="invite-form" loading={invite.isPending} disabled={!valid}>Create invitation</Button>
        </>
      }
    >
      <form id="invite-form" onSubmit={submit} className="space-y-4" noValidate>
        {error && <Banner tone="critical">{error.message}</Banner>}
        <TextField label="Full name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
        <TextField label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} error={error?.field("email")} />
        <fieldset>
          <legend className="mb-1.5 text-subhead font-medium text-label-2">Role</legend>
          <div className="space-y-1.5" role="radiogroup">
            {roles.map((r) => {
              const selected = form.role === r.key;
              return (
                <button
                  key={r.key}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => setForm({ ...form, role: r.key })}
                  className={cn(
                    "flex w-full items-start gap-3 rounded-[12px] p-3 text-left transition-[background-color,box-shadow] duration-150 focus-visible:focus-ring",
                    selected ? "bg-accent-tint shadow-[inset_0_0_0_1.5px_var(--accent)]" : "bg-fill-2 hover:bg-fill",
                  )}
                >
                  <span className={cn("mt-0.5 grid size-4 shrink-0 place-items-center rounded-full transition-colors", selected ? "bg-accent" : "shadow-[inset_0_0_0_1px_var(--separator-strong)]")}>
                    {selected && <span className="size-1.5 rounded-full bg-white" />}
                  </span>
                  <span>
                    <span className="block text-callout font-medium text-label">{r.label}</span>
                    <span className="block text-footnote text-label-2">{r.summary}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </fieldset>
      </form>
    </Sheet>
  );
}

function LinkSheet({ link, onClose }: { link: { name: string; url: string; reset: boolean } | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => setCopied(false), [link]);
  const copy = async () => {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link.url);
      setCopied(true);
    } catch {
      toast.error("Copy failed. Select the link and copy it manually.");
    }
  };
  return (
    <Sheet
      open={!!link}
      onOpenChange={(o) => !o && onClose()}
      width={520}
      title={link?.reset ? `New sign-in link for ${link?.name}` : `Invitation for ${link?.name}`}
      description="Share this link through a trusted channel. It works once, expires in 72 hours, and won’t be shown again."
      footer={<Button variant="filled" onClick={onClose}>Done</Button>}
    >
      {link && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 rounded-[12px] bg-fill-2 p-2 pl-3">
            <code className="min-w-0 flex-1 truncate font-mono text-footnote text-label">{link.url}</code>
            <Button variant={copied ? "gray" : "tinted"} size="sm" icon={copied ? <Check /> : <Copy />} onClick={copy}>
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <Banner tone="warning">Anyone with this link can set the password for this account until it is used or expires.</Banner>
        </div>
      )}
    </Sheet>
  );
}

import type { ReactNode } from "react";
import { Building2, FolderOpen, KeyRound, LogIn, Orbit, Radar, ScrollText, Server, ShieldCheck, UserRound, type LucideIcon } from "lucide-react";
import { Skeleton } from "@/design/components/Surface";
import { formatRelative } from "@/lib/format";
import { useAudit } from "@/lib/queries";
import type { AuditEvent } from "@/lib/types";

export function eventIcon(action: string): LucideIcon {
  if (action.startsWith("identity.")) return LogIn;
  if (action.startsWith("member.")) return UserRound;
  if (action.startsWith("token.")) return KeyRound;
  if (action.startsWith("threat_model.")) return Orbit;
  if (action.startsWith("organisation.")) return Building2;
  if (action.startsWith("system.")) return Server;
  if (action.startsWith("source.")) return FolderOpen;
  if (action.startsWith("scan.")) return Radar;
  if (action.startsWith("ledger.")) return ShieldCheck;
  return ScrollText;
}

export function EventRow({ event, children }: { event: AuditEvent; children?: ReactNode }) {
  const Icon = eventIcon(event.action);
  return (
    <div className="flex gap-3 py-2.5">
      <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-fill-2 text-label-2">
        <Icon className="size-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-callout text-label">{event.summary}</div>
        <div className="mt-0.5 text-footnote text-label-3">
          <time dateTime={event.occurred_at} title={new Date(event.occurred_at).toLocaleString()}>
            {formatRelative(event.occurred_at)}
          </time>
          {event.ip && <> · {event.ip}</>}
        </div>
        {children}
      </div>
    </div>
  );
}

/** Recent audit events, optionally for one target (system, member…). */
export function ActivityFeed({ target, limit = 10 }: { target?: string; limit?: number }) {
  const audit = useAudit({ target }, { limit });
  if (audit.isPending) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-10" />
        ))}
      </div>
    );
  }
  const events = audit.data?.pages[0]?.events ?? [];
  if (events.length === 0) return <p className="text-subhead text-label-3">No activity yet.</p>;
  return (
    <div className="divide-y divide-separator">
      {events.map((e) => (
        <EventRow key={e.id} event={e} />
      ))}
    </div>
  );
}

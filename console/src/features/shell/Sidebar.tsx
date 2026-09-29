import { Boxes, Clock, FileText, FileSignature, FlaskConical, Gauge, LayoutGrid, Network, Route, SlidersHorizontal, LogOut, Monitor, Moon, Orbit, Radar, ScrollText, Server, ShieldCheck, Settings, Sun, Users, type LucideIcon } from "lucide-react";
import { LayoutGroup, motion } from "motion/react";
import type { ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router";
import { cn } from "@/design/cn";
import { LogoMark, Wordmark } from "@/design/components/Logo";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuRadioGroup, MenuSeparator, MenuTrigger } from "@/design/components/Menu";
import { Avatar } from "@/design/components/Surface";
import { spring } from "@/design/motion";
import { setAppearance, useAppearance, type Appearance } from "@/lib/appearance";
import { usePermissions } from "@/lib/access";
import { prefetchRoute, useAccount, useSignOut } from "@/lib/queries";
import type { Permission } from "@/lib/types";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  permission?: Permission;
  end?: boolean;
}

const primary: NavItem[] = [
  { to: "/", label: "Overview", icon: LayoutGrid, end: true },
  { to: "/systems", label: "Systems", icon: Server, permission: "systems.read" },
  { to: "/horizon", label: "Threat Horizon", icon: Orbit },
];

const intelligence: NavItem[] = [
  { to: "/risk", label: "Quantum Risk", icon: Gauge, permission: "inventory.read" },
  { to: "/time-machine", label: "Time Machine", icon: Clock, permission: "inventory.read" },
  { to: "/compliance", label: "Compliance", icon: ShieldCheck, permission: "inventory.read" },
];

const migration: NavItem[] = [
  { to: "/migration", label: "Migration Plan", icon: Route, permission: "inventory.read" },
  { to: "/blast-radius", label: "Blast Radius", icon: Network, permission: "inventory.read" },
  { to: "/simulator", label: "What-if", icon: SlidersHorizontal, permission: "inventory.read" },
  { to: "/lab", label: "Benchmark Lab", icon: FlaskConical, permission: "inventory.read" },
];

const reporting: NavItem[] = [
  { to: "/reports", label: "Reports", icon: FileSignature, permission: "inventory.read" },
  { to: "/brief", label: "Executive Brief", icon: FileText, permission: "inventory.read" },
];

const discovery: NavItem[] = [
  { to: "/inventory", label: "Inventory", icon: Boxes, permission: "inventory.read" },
  { to: "/scans", label: "Scans", icon: Radar, permission: "inventory.read" },
];

const organisation: NavItem[] = [
  { to: "/members", label: "Members", icon: Users, permission: "members.read" },
  { to: "/ledger", label: "Audit Ledger", icon: ScrollText, permission: "audit.read" },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const account = useAccount().data;
  const permissions = usePermissions();
  const visible = (items: NavItem[]) => items.filter((i) => !i.permission || permissions.has(i.permission));
  const orgItems = visible(organisation);

  return (
    <nav aria-label="Primary" className="flex h-full w-full flex-col">
      <div className="flex items-center gap-2.5 px-4 pb-4 pt-5">
        <LogoMark size={30} />
        <div className="min-w-0 leading-tight">
          <Wordmark className="block text-[14px]" />
          <div className="truncate text-caption text-label-3">{account?.organisation?.name}</div>
        </div>
      </div>

      <LayoutGroup id="sidebar">
        <div className="flex-1 space-y-5 overflow-y-auto px-2.5">
          <NavSection items={visible(primary)} onNavigate={onNavigate} />
          {visible(discovery).length > 0 && <NavSection title="Discovery" items={visible(discovery)} onNavigate={onNavigate} />}
          {visible(intelligence).length > 0 && <NavSection title="Intelligence" items={visible(intelligence)} onNavigate={onNavigate} />}
          {visible(migration).length > 0 && <NavSection title="Migration" items={visible(migration)} onNavigate={onNavigate} />}
          {visible(reporting).length > 0 && <NavSection title="Reporting" items={visible(reporting)} onNavigate={onNavigate} />}
          {orgItems.length > 0 && <NavSection title="Organisation" items={orgItems} onNavigate={onNavigate} />}
        </div>
        <div className="px-2.5 pb-3">
          <NavSection items={[{ to: "/settings", label: "Settings", icon: Settings }]} onNavigate={onNavigate} />
        </div>
      </LayoutGroup>

      <AccountButton />
    </nav>
  );
}

function NavSection({ title, items, onNavigate }: { title?: string; items: NavItem[]; onNavigate?: () => void }) {
  const location = useLocation();
  return (
    <div>
      {title && <div className="mb-1 px-2.5 text-caption font-semibold text-label-3">{title}</div>}
      <ul className="space-y-px">
        {items.map((item) => {
          const active = item.end ? location.pathname === item.to : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
          const Icon = item.icon;
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                onClick={onNavigate}
                onPointerEnter={() => prefetchRoute(item.to)}
                onFocus={() => prefetchRoute(item.to)}
                className={cn(
                  "hover-light relative flex h-8 items-center gap-2.5 rounded-[9px] px-2.5 text-callout outline-none transition-colors duration-150",
                  "focus-visible:focus-ring",
                  active ? "font-medium text-label" : "text-label-2 hover:bg-fill-2 hover:text-label",
                )}
              >
                {active && (
                  <motion.span
                    layoutId="nav-selection"
                    transition={spring.snappy}
                    className="absolute inset-0 rounded-[9px] bg-[var(--glass-strong)] shadow-[0_0_0_0.5px_var(--glass-rim),inset_0_1px_0_var(--glass-edge),0_1px_3px_rgba(15,23,42,0.06)]"
                  />
                )}
                <Icon className={cn("relative size-[17px] shrink-0", active ? "text-accent" : "text-label-3")} strokeWidth={1.9} />
                <span className="relative truncate">{item.label}</span>
              </NavLink>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const appearanceOptions: { value: Appearance; label: ReactNode }[] = [
  { value: "system", label: <span className="flex items-center gap-2"><Monitor className="size-4" /> Match system</span> },
  { value: "light", label: <span className="flex items-center gap-2"><Sun className="size-4" /> Light</span> },
  { value: "dark", label: <span className="flex items-center gap-2"><Moon className="size-4" /> Dark</span> },
];

function AccountButton() {
  const account = useAccount().data;
  const appearance = useAppearance();
  const signOut = useSignOut();
  const navigate = useNavigate();
  if (!account) return null;
  return (
    <div className="px-2.5 pb-3 hairline-t pt-3">
      <Menu>
        <MenuTrigger asChild>
          <button type="button" className="hover-light flex w-full items-center gap-2.5 rounded-[10px] p-1.5 text-left outline-none transition-colors hover:bg-fill-2 focus-visible:focus-ring data-[state=open]:bg-fill-2">
            <Avatar name={account.user.name} size={30} />
            <div className="min-w-0 flex-1 leading-tight">
              <div className="truncate text-subhead font-medium text-label">{account.user.name}</div>
              <div className="truncate text-caption text-label-3">{account.user.role_label}</div>
            </div>
          </button>
        </MenuTrigger>
        <MenuContent align="start" width={232}>
          <MenuLabel>{account.user.email}</MenuLabel>
          <MenuItem icon={<Settings />} onSelect={() => navigate("/settings")}>
            Settings
          </MenuItem>
          <MenuSeparator />
          <MenuLabel>Appearance</MenuLabel>
          <MenuRadioGroup value={appearance} onChange={setAppearance} options={appearanceOptions} />
          <MenuSeparator />
          <MenuItem icon={<LogOut />} onSelect={() => signOut.mutate()}>
            Sign out
          </MenuItem>
        </MenuContent>
      </Menu>
    </div>
  );
}

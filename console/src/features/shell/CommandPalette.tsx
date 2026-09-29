import { Command } from "cmdk";
import { ArrowDownToLine, Boxes, Clock, CornerDownLeft, FileSignature, FileText, FlaskConical, FolderOpen, History, Keyboard, Volume2, VolumeX, Gauge, Network, Route, ShieldCheck, SlidersHorizontal, LayoutGrid, LogOut, Monitor, Moon, Orbit, Plus, Radar, ScrollText, Search, Server, Settings, Sun, UserPlus, Users } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { Dialog } from "radix-ui";
import { useDeferredValue, useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { Chip, Kbd } from "@/design/components/Surface";
import { spring } from "@/design/motion";
import { usePermissions } from "@/lib/access";
import { toast } from "sonner";
import { setAppearance } from "@/lib/appearance";
import { api } from "@/lib/api";
import { saveExport } from "@/lib/exports";
import { useArtefacts, useExports, useSignOut, useSystems } from "@/lib/queries";
import { useRecents } from "@/lib/recents";
import { isMac } from "@/lib/shortcuts";
import { play, setSoundPrefs, useSoundPrefs } from "@/lib/sound";
import { STATUS_META } from "@/viz/charts/MoscaChart";
import { KINDS, QUANTUM } from "../discovery/vocab";

export const commandKey = isMac ? "⌘" : "Ctrl";

export function CommandPalette({ open, onOpenChange, onShowShortcuts }: { open: boolean; onOpenChange: (open: boolean) => void; onShowShortcuts?: () => void }) {
  const navigate = useNavigate();
  const permissions = usePermissions();
  const signOut = useSignOut();
  const [search, setSearch] = useState("");
  const systems = useSystems({});
  const canReadSystems = permissions.has("systems.read");
  const canReadInventory = permissions.has("inventory.read");
  const term = useDeferredValue(search.trim());
  const artefacts = useArtefacts({ q: term, sort: "risk" }, open && canReadInventory && term.length >= 2);
  const found = term.length >= 2 ? (artefacts.data?.pages[0]?.items.slice(0, 8) ?? []) : [];
  const recents = useRecents().filter((r) => r.path !== window.location.pathname + window.location.search).slice(0, 5);
  const sound = useSoundPrefs();
  const exports = useExports();
  const desktop = exports.data?.location.desktop ?? false;

  useEffect(() => {
    if (!open) setSearch("");
  }, [open]);

  const run = (action: () => void) => {
    onOpenChange(false);
    action();
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild forceMount>
              <motion.div className="fixed inset-0 z-40 bg-[var(--overlay)]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} />
            </Dialog.Overlay>
            <Dialog.Content asChild forceMount aria-describedby={undefined}>
              <motion.div
                className="fixed left-1/2 top-[14vh] z-50 w-[min(640px,calc(100vw-32px))] -translate-x-1/2 overflow-hidden rounded-[16px] bg-elevated shadow-pop outline-none vibrancy"
                initial={{ opacity: 0, scale: 0.97, y: -8 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.12 } }}
                transition={spring.smooth}
              >
                <Dialog.Title className="sr-only">Search FALCON</Dialog.Title>
                <Command label="Search FALCON" loop filter={matchWords} className="flex max-h-[min(520px,70vh)] flex-col">
                  <div className="flex items-center gap-3 px-4 hairline-b">
                    <Search className="size-5 shrink-0 text-label-3" />
                    <Command.Input
                      value={search}
                      onValueChange={setSearch}
                      placeholder="Search systems, artefacts, pages and actions"
                      className="h-14 w-full bg-transparent text-[17px] text-label outline-none placeholder:text-label-4 focus-visible:shadow-none"
                    />
                    <Kbd>esc</Kbd>
                  </div>
                  <Command.List className="min-h-0 flex-1 overflow-y-auto p-2 [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-caption [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-label-3">
                    <Command.Empty className="px-4 py-10 text-center text-subhead text-label-3">No results for “{search}”</Command.Empty>

                    {!search && recents.length > 0 && (
                      <Command.Group heading="Recent">
                        {recents.map((r) => (
                          <Item key={r.path} icon={<History />} value={`recent ${r.title} ${r.path}`} onSelect={() => run(() => navigate(r.path))}>
                            <span className="truncate">{r.title}</span>
                          </Item>
                        ))}
                      </Command.Group>
                    )}

                    <Command.Group heading="Go to">
                      <Item icon={<LayoutGrid />} onSelect={() => run(() => navigate("/"))}>Overview</Item>
                      {canReadSystems && <Item icon={<Server />} onSelect={() => run(() => navigate("/systems"))}>Systems</Item>}
                      <Item icon={<Orbit />} onSelect={() => run(() => navigate("/horizon"))}>Threat Horizon</Item>
                      {canReadInventory && <Item icon={<Boxes />} value="inventory cryptography artefacts cbom" onSelect={() => run(() => navigate("/inventory"))}>Inventory</Item>}
                      {canReadInventory && <Item icon={<Radar />} value="scans discovery history" onSelect={() => run(() => navigate("/scans"))}>Scans</Item>}
                      {canReadInventory && <Item icon={<Gauge />} value="quantum risk mosca hndl harvest register matrix" onSelect={() => run(() => navigate("/risk"))}>Quantum Risk</Item>}
                      {canReadInventory && <Item icon={<Clock />} value="time machine timeline future year" onSelect={() => run(() => navigate("/time-machine"))}>Time Machine</Item>}
                      {canReadInventory && <Item icon={<ShieldCheck />} value="compliance policy nist cnsa sp 800-131a ir 8547 eu" onSelect={() => run(() => navigate("/compliance"))}>Compliance</Item>}
                      {canReadInventory && <Item icon={<Route />} value="migration plan roadmap waves recommendations pqc" onSelect={() => run(() => navigate("/migration"))}>Migration Plan</Item>}
                      {canReadInventory && <Item icon={<Network />} value="blast radius dependency graph shared" onSelect={() => run(() => navigate("/blast-radius"))}>Blast Radius</Item>}
                      {canReadInventory && <Item icon={<SlidersHorizontal />} value="what if simulator scenario delay" onSelect={() => run(() => navigate("/simulator"))}>What-if Simulator</Item>}
                      {canReadInventory && <Item icon={<FlaskConical />} value="benchmark lab performance ml-kem ml-dsa speed" onSelect={() => run(() => navigate("/lab"))}>Benchmark Lab</Item>}
                      {canReadInventory && <Item icon={<FileSignature />} value="reports export cbom cyclonedx sarif spdx csv snapshot sign verify attestation drift" onSelect={() => run(() => navigate("/reports"))}>Reports</Item>}
                      {canReadInventory && <Item icon={<FileText />} value="executive brief board summary print pdf" onSelect={() => run(() => navigate("/brief"))}>Executive Brief</Item>}
                      {permissions.has("members.read") && <Item icon={<Users />} onSelect={() => run(() => navigate("/members"))}>Members</Item>}
                      {permissions.has("audit.read") && <Item icon={<ScrollText />} onSelect={() => run(() => navigate("/ledger"))}>Audit Ledger</Item>}
                      <Item icon={<Settings />} onSelect={() => run(() => navigate("/settings"))}>Settings</Item>
                    </Command.Group>

                    {canReadSystems && search && (systems.data?.items.length ?? 0) > 0 && (
                      <Command.Group heading="Systems">
                        {systems.data!.items.map((s) => {
                          const meta = STATUS_META[s.mosca.status];
                          return (
                            <Item
                              key={s.id}
                              value={`${s.code} ${s.name} ${s.owner ?? ""} ${s.tags.join(" ")}`}
                              icon={<Server />}
                              onSelect={() => run(() => navigate(`/systems/${s.id}`))}
                              trailing={
                                <span className="flex items-center gap-1 text-footnote text-label-3">
                                  <meta.icon className="size-3.5" style={{ color: meta.color }} />
                                  {meta.label}
                                </span>
                              }
                            >
                              <Chip>{s.code}</Chip>
                              <span className="truncate">{s.name}</span>
                            </Item>
                          );
                        })}
                      </Command.Group>
                    )}

                    {found.length > 0 && (
                      <Command.Group heading="Artefacts">
                        {found.map((a) => {
                          const Icon = KINDS[a.kind].icon;
                          const q = a.quantum && a.kind !== "library" && a.kind !== "hardware" ? QUANTUM[a.quantum] : null;
                          return (
                            <Item
                              key={a.id}
                              value={`${a.name} ${KINDS[a.kind].singular} ${a.system?.code ?? ""} ${a.family ?? ""}`}
                              icon={<Icon />}
                              onSelect={() => run(() => navigate(`/inventory/${a.id}`))}
                              trailing={q && <span className="text-footnote text-label-3">{q.short}</span>}
                            >
                              <span className="truncate">{a.name}</span>
                              {a.system && <Chip>{a.system.code}</Chip>}
                            </Item>
                          );
                        })}
                      </Command.Group>
                    )}

                    <Command.Group heading="Actions">
                      {permissions.has("systems.write") && (
                        <Item icon={<Plus />} onSelect={() => run(() => navigate("/systems?register=1"))}>Register a system</Item>
                      )}
                      {permissions.has("members.manage") && (
                        <Item icon={<UserPlus />} onSelect={() => run(() => navigate("/members?invite=1"))}>Invite a member</Item>
                      )}
                      {canReadInventory && (
                        <Item
                          icon={<ArrowDownToLine />}
                          value="export cbom cyclonedx download save"
                          onSelect={() => run(() => void saveExport({ format: "cyclonedx-json" }).catch((e: Error) => toast.error(e.message)))}
                        >
                          Export the CycloneDX CBOM
                        </Item>
                      )}
                      {desktop && (
                        <Item icon={<FolderOpen />} value="open export folder downloads location" onSelect={() => run(() => void api.post("/reports/exports/location/open"))}>
                          Open the export folder
                        </Item>
                      )}
                      {onShowShortcuts && (
                        <Item icon={<Keyboard />} value="keyboard shortcuts keys help" onSelect={() => run(onShowShortcuts)}>
                          Keyboard shortcuts
                        </Item>
                      )}
                      <Item
                        icon={sound.enabled ? <VolumeX /> : <Volume2 />}
                        value="sounds audio mute interface clicks"
                        onSelect={() =>
                          run(() => {
                            setSoundPrefs({ enabled: !sound.enabled });
                            play(sound.enabled ? "toggleOff" : "toggleOn", { force: true });
                          })
                        }
                      >
                        {sound.enabled ? "Turn interface sounds off" : "Turn interface sounds on"}
                      </Item>
                      <Item icon={<Sun />} value="appearance light theme" onSelect={() => run(() => setAppearance("light"))}>Use light appearance</Item>
                      <Item icon={<Moon />} value="appearance dark theme" onSelect={() => run(() => setAppearance("dark"))}>Use dark appearance</Item>
                      <Item icon={<Monitor />} value="appearance system theme" onSelect={() => run(() => setAppearance("system"))}>Match system appearance</Item>
                      <Item icon={<LogOut />} onSelect={() => run(() => signOut.mutate())}>Sign out</Item>
                    </Command.Group>
                  </Command.List>
                  <div className="flex items-center justify-end gap-3 px-4 py-2 text-caption text-label-3 hairline-t">
                    <span className="flex items-center gap-1"><Kbd>↑</Kbd><Kbd>↓</Kbd> to navigate</span>
                    <span className="flex items-center gap-1"><Kbd><CornerDownLeft className="size-3" /></Kbd> to open</span>
                  </div>
                </Command>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}

/** Every typed word must appear in the item; earlier matches rank higher. */
function matchWords(value: string, search: string): number {
  const haystack = value.toLowerCase();
  const words = search.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.some((w) => !haystack.includes(w))) return 0;
  return 1 / (1 + haystack.indexOf(words[0] ?? ""));
}

function Item({ children, icon, onSelect, value, trailing }: { children: ReactNode; icon: ReactNode; onSelect: () => void; value?: string; trailing?: ReactNode }) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      className="flex h-10 cursor-pointer items-center gap-3 rounded-[9px] px-2.5 text-callout text-label outline-none data-[selected=true]:bg-accent data-[selected=true]:text-on-accent [&>svg]:size-[18px] [&>svg]:shrink-0 [&>svg]:text-label-3 data-[selected=true]:[&>svg]:text-on-accent data-[selected=true]:[&_*]:!text-on-accent"
    >
      {icon}
      <span className="flex min-w-0 flex-1 items-center gap-2">{children}</span>
      {trailing}
    </Command.Item>
  );
}

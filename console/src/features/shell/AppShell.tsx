import { PanelLeft, Search } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router";
import { toast } from "sonner";
import { cn } from "@/design/cn";
import { IconButton } from "@/design/components/Button";
import { Kbd } from "@/design/components/Surface";
import { ease, spring } from "@/design/motion";
import { prefetchPages } from "@/app/prefetch";
import { setAppearance } from "@/lib/appearance";
import { bindingFor, displayKeys, SHORTCUTS, useShortcutPrefs } from "@/lib/shortcuts";
import { play, setSoundPrefs, useSoundPrefs } from "@/lib/sound";
import { CommandPalette } from "./CommandPalette";
import { ConnectionStatus } from "./ConnectionStatus";
import { DownloadsButton } from "./DownloadsButton";
import { FalconFlight } from "./FalconFlight";
import { ShortcutsSheet, useShortcutDispatcher } from "./Shortcuts";
import { PageTitleProvider, useToolbarTitle } from "./Page";
import { Sidebar } from "./Sidebar";

const NARROW = "(max-width: 960px)";

function useNarrow() {
  const [narrow, setNarrow] = useState(() => window.matchMedia(NARROW).matches);
  useEffect(() => {
    const mq = window.matchMedia(NARROW);
    const on = () => setNarrow(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return narrow;
}

export function AppShell() {
  const narrow = useNarrow();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [downloadsOpen, setDownloadsOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const scroller = useRef<HTMLDivElement>(null);
  const sound = useSoundPrefs();

  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const toggleSidebar = useCallback(() => (narrow ? setDrawerOpen((v) => !v) : setSidebarOpen((v) => !v)), [narrow]);

  // Every keyboard shortcut, as bound in Settings → Keyboard.
  const actions: Record<string, () => void> = {
    palette: openPalette,
    shortcuts: () => setShortcutsOpen(true),
    sidebar: toggleSidebar,
    exports: () => setDownloadsOpen(true),
    find: () => {
      const field = document.querySelector<HTMLInputElement>('#content input[type="search"], #content [data-page-search]');
      if (field) field.focus();
      else openPalette();
    },
    sounds: () => {
      const on = !sound.enabled;
      setSoundPrefs({ enabled: on });
      play(on ? "toggleOn" : "toggleOff", { force: true });
      toast(on ? "Interface sounds on" : "Interface sounds off");
    },
    "appearance.light": () => setAppearance("light"),
    "appearance.dark": () => setAppearance("dark"),
    "appearance.system": () => setAppearance("system"),
  };
  for (const s of SHORTCUTS) if (s.path) actions[s.id] = () => navigate(s.path!);
  useShortcutDispatcher(actions);

  // New page, fresh scroll position (instantly: smooth scrolling is for jumps within a page).
  useEffect(() => {
    scroller.current?.scrollTo({ top: 0, behavior: "instant" });
    setDrawerOpen(false);
  }, [location.pathname]);

  // Once the console is idle, fetch every page's code so navigation never waits on the network.
  useEffect(() => prefetchPages(), []);

  return (
    <PageTitleProvider>
      <a href="#content" className="skip-link glass-strong rounded-[10px] px-3 py-2 text-subhead font-medium text-label focus-visible:focus-ring">
        Skip to content
      </a>
      <div className="flex h-dvh overflow-hidden">
        {!narrow && (
          <motion.aside
            initial={false}
            animate={{ width: sidebarOpen ? 248 : 0 }}
            transition={spring.smooth}
            className="relative shrink-0 overflow-hidden"
          >
            {/* A floating glass panel, inset from the window edge. */}
            <div className="h-full w-[248px] py-2 pl-2">
              <div className="glass-strong h-full overflow-hidden rounded-[18px]">
                <Sidebar />
              </div>
            </div>
          </motion.aside>
        )}

        <AnimatePresence>
          {narrow && drawerOpen && (
            <>
              <motion.div className="fixed inset-0 z-30 bg-[var(--overlay)]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setDrawerOpen(false)} />
              <motion.aside
                className="glass-strong fixed inset-y-2 left-2 z-40 w-[264px] overflow-hidden rounded-[18px]"
                initial={{ x: -280 }}
                animate={{ x: 0 }}
                exit={{ x: -280 }}
                transition={spring.smooth}
              >
                <Sidebar onNavigate={() => setDrawerOpen(false)} />
              </motion.aside>
            </>
          )}
        </AnimatePresence>

        <main className="relative min-w-0 flex-1">
          <Toolbar onToggleSidebar={toggleSidebar} onSearch={openPalette} downloadsOpen={downloadsOpen} onDownloadsOpenChange={setDownloadsOpen} />
          <div ref={scroller} id="content" className="h-full overflow-y-auto overflow-x-hidden pt-[52px] [scroll-padding-top:64px]">
            {/* No exit phase: the next page starts the instant it is chosen, and its sections rise in (see .reveal). */}
            <motion.div key={location.pathname} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.22, ease: ease.out }}>
              <Outlet />
            </motion.div>
          </div>
        </main>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} onShowShortcuts={() => setShortcutsOpen(true)} />
      <ShortcutsSheet open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
      <FalconFlight />
      <ConnectionStatus />
    </PageTitleProvider>
  );
}

function Toolbar({ onToggleSidebar, onSearch, downloadsOpen, onDownloadsOpenChange }: {
  onToggleSidebar: () => void; onSearch: () => void; downloadsOpen: boolean; onDownloadsOpenChange: (open: boolean) => void;
}) {
  const { title, compact } = useToolbarTitle();
  const prefs = useShortcutPrefs();
  const sidebarKeys = displayKeys(bindingFor("sidebar", prefs)).join("");
  const paletteKeys = displayKeys(bindingFor("palette", prefs));
  return (
    <header
      className={cn(
        "absolute inset-x-0 top-0 z-20 flex h-[52px] items-center gap-2 px-3 transition-[background-color,box-shadow] duration-200",
        compact ? "bg-[var(--toolbar)] vibrancy shadow-[0_0.5px_0_var(--glass-rim)]" : "bg-transparent",
      )}
    >
      <IconButton label={sidebarKeys ? `Toggle sidebar (${sidebarKeys})` : "Toggle sidebar"} onClick={onToggleSidebar}>
        <PanelLeft strokeWidth={1.75} />
      </IconButton>
      <div className="pointer-events-none absolute inset-x-0 flex justify-center">
        <AnimatePresence>
          {compact && title && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
              className="text-headline text-label"
            >
              {title}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <div className="ml-auto flex items-center gap-1.5">
        <DownloadsButton open={downloadsOpen} onOpenChange={onDownloadsOpenChange} />
        <button
          type="button"
          onClick={onSearch}
          className="glass hover-light flex h-8 w-[220px] items-center gap-2 rounded-full px-3 text-subhead text-label-3 transition-colors hover:text-label-2 focus-visible:focus-ring max-sm:w-8 max-sm:justify-center max-sm:px-0"
        >
          <Search className="size-4 shrink-0" />
          <span className="flex-1 text-left max-sm:hidden">Search</span>
          {paletteKeys.length > 0 && (
            <span className="flex gap-0.5 max-sm:hidden">
              {paletteKeys.map((k, i) => (k === "then" ? null : <Kbd key={i}>{k}</Kbd>))}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}

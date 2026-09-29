import { lazy, Suspense, type ComponentType, type ReactNode } from "react";
import { createBrowserRouter, Navigate, Outlet, useLocation } from "react-router";
import { AppShell } from "@/features/shell/AppShell";
import { BootScreen } from "@/features/shell/BootScreen";
import { PageSkeleton } from "@/features/shell/Page";
import { useAccount, useSetupStatus } from "@/lib/queries";
import { registerPage } from "./prefetch";
import { SessionWatch } from "./SessionWatch";

type PageModule = { default: ComponentType };

/**
 * A code-split page. Once its chunk has loaded (on first visit or by the idle
 * prefetch) it renders synchronously, so navigating to it never shows a
 * skeleton or waits a frame.
 */
function page(load: () => Promise<PageModule>) {
  let loaded: PageModule | null = null;
  let pending: Promise<PageModule> | null = null;
  const preload = () =>
    (pending ??= load().then(
      (mod) => (loaded = mod),
      (err) => {
        pending = null; // a failed fetch (offline, redeploy) may be retried
        throw err;
      },
    ));
  registerPage(preload);
  const Lazy = lazy(preload);
  function RoutePage() {
    if (loaded) {
      const Component = loaded.default;
      return <Component />;
    }
    return (
      <Suspense fallback={<PageSkeleton />}>
        <Lazy />
      </Suspense>
    );
  }
  return <RoutePage />;
}

function standalone(load: () => Promise<{ default: ComponentType }>) {
  const Component = lazy(load);
  return (
    <Suspense fallback={<BootScreen />}>
      <Component />
    </Suspense>
  );
}

/** Decides where a visitor belongs: setup, sign-in or the console. */
function Gate() {
  const setup = useSetupStatus();
  const location = useLocation();
  if (setup.isPending) return <BootScreen />;
  if (setup.isError) return <BootScreen error={setup.error} onRetry={() => setup.refetch()} />;
  const onSetup = location.pathname === "/setup";
  if (!setup.data.initialised && !onSetup) return <Navigate to="/setup" replace />;
  if (setup.data.initialised && onSetup) return <Navigate to="/" replace />;
  return (
    <>
      <SessionWatch />
      <Outlet />
    </>
  );
}

function RequireAccount({ children }: { children: ReactNode }) {
  const account = useAccount();
  const location = useLocation();
  if (account.isPending) return <BootScreen />;
  if (account.isError) return <BootScreen error={account.error} onRetry={() => account.refetch()} />;
  if (!account.data) {
    const next = location.pathname + location.search;
    return <Navigate to={next === "/" ? "/sign-in" : `/sign-in?next=${encodeURIComponent(next)}`} replace />;
  }
  return <>{children}</>;
}

export const router = createBrowserRouter([
  {
    element: <Gate />,
    children: [
      { path: "/setup", element: standalone(() => import("@/features/auth/SetupAssistant")) },
      { path: "/sign-in", element: standalone(() => import("@/features/auth/SignIn")) },
      { path: "/activate", element: standalone(() => import("@/features/auth/Activate")) },
      // The executive brief is a document: no sidebar or toolbar, laid out for the screen and for print.
      { path: "/brief", element: <RequireAccount>{standalone(() => import("@/features/reports/BriefPage"))}</RequireAccount> },
      {
        path: "/",
        element: (
          <RequireAccount>
            <AppShell />
          </RequireAccount>
        ),
        children: [
          { index: true, element: page(() => import("@/features/overview/OverviewPage")) },
          { path: "systems", element: page(() => import("@/features/systems/SystemsPage")) },
          { path: "systems/:systemId", element: page(() => import("@/features/systems/SystemDetailPage")) },
          { path: "inventory", element: page(() => import("@/features/discovery/InventoryPage")) },
          { path: "inventory/:artefactId", element: page(() => import("@/features/discovery/ArtefactPage")) },
          { path: "scans", element: page(() => import("@/features/discovery/ScansPage")) },
          { path: "risk", element: page(() => import("@/features/risk/RiskPage")) },
          { path: "time-machine", element: page(() => import("@/features/risk/TimeMachinePage")) },
          { path: "compliance", element: page(() => import("@/features/risk/CompliancePage")) },
          { path: "migration", element: page(() => import("@/features/migration/MigrationPage")) },
          { path: "blast-radius", element: page(() => import("@/features/migration/BlastRadiusPage")) },
          { path: "simulator", element: page(() => import("@/features/migration/SimulatorPage")) },
          { path: "lab", element: page(() => import("@/features/migration/LabPage")) },
          { path: "reports", element: page(() => import("@/features/reports/ReportsPage")) },
          { path: "scans/:scanId", element: page(() => import("@/features/discovery/ScanPage")) },
          { path: "horizon", element: page(() => import("@/features/horizon/HorizonPage")) },
          { path: "members", element: page(() => import("@/features/settings/MembersPage")) },
          { path: "ledger", element: page(() => import("@/features/settings/LedgerPage")) },
          { path: "settings", element: page(() => import("@/features/settings/SettingsPage")) },
          { path: "*", element: page(() => import("@/features/shell/NotFound")) },
        ],
      },
    ],
  },
]);

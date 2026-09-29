import { keepPreviousData, QueryClient, useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "./api";
import type {
  ExportLocation,
  ExportRecord,
  AttestationKey,
  Drift,
  ReportFormat,
  Snapshot,
  SnapshotDetail,
  Verification,
  BenchmarkReport,
  BlastGraph,
  MigrationPlan,
  Recommendation,
  ScanDiff,
  PolicyOverview,
  RiskDetail,
  RiskRow,
  RiskSummary,
  RiskTimelinePayload,
  About,
  AccessTokenInfo,
  Account,
  ArtefactDetail,
  ArtefactPage,
  AuditPage,
  DiscoveryCapabilities,
  Horizon,
  LedgerVerification,
  Member,
  MilestoneCatalogue,
  Organisation,
  Overview,
  RoleInfo,
  InventorySummary,
  ScanBrief,
  ScanDetail,
  ScanListItem,
  SessionInfo,
  SetupStatus,
  Source,
  SystemInput,
  SystemRecord,
  SystemsSummary,
  ThreatModelSettings,
  Vocabulary,
} from "./types";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: true,
      retry: (count, error) => !(error instanceof ApiError && error.status > 0 && error.status < 500) && count < 2,
    },
    mutations: { retry: false },
  },
});

export const keys = {
  setup: ["setup"] as const,
  account: ["account"] as const,
  organisation: ["organisation"] as const,
  overview: ["overview"] as const,
  horizon: ["horizon"] as const,
  milestones: ["milestones"] as const,
  systems: (filters?: SystemFilters) => ["systems", "list", filters ?? {}] as const,
  systemsAll: ["systems"] as const,
  system: (id: string) => ["systems", "detail", id] as const,
  systemsSummary: ["systems", "summary"] as const,
  vocabulary: ["systems", "vocabulary"] as const,
  members: ["members"] as const,
  roles: ["roles"] as const,
  sessions: ["sessions"] as const,
  tokens: ["tokens"] as const,
  audit: (filters: AuditFilters) => ["audit", filters] as const,
  auditAll: ["audit"] as const,
  about: ["about"] as const,
  capabilities: ["discovery", "capabilities"] as const,
  sources: (systemId: string) => ["discovery", "sources", systemId] as const,
  scans: (filters: ScanFilters) => ["discovery", "scans", filters] as const,
  scan: (id: string) => ["discovery", "scan", id] as const,
  artefacts: (filters: ArtefactFilters) => ["discovery", "artefacts", filters] as const,
  artefact: (id: string) => ["discovery", "artefact", id] as const,
  inventory: (system?: string) => ["discovery", "inventory", system ?? "all"] as const,
  discovery: ["discovery"] as const,
  risk: ["risk"] as const,
  riskSummary: (system?: string) => ["risk", "summary", system ?? "all"] as const,
  riskRegister: (filters: RiskFilters) => ["risk", "register", filters] as const,
  riskArtefact: (id: string) => ["risk", "artefact", id] as const,
  riskTimeline: (system?: string) => ["risk", "timeline", system ?? "all"] as const,
  riskPolicies: ["risk", "policies"] as const,
};

/* -------------------------------------------------------------- session */

export function useSetupStatus() {
  return useQuery({ queryKey: keys.setup, queryFn: () => api.get<SetupStatus>("/setup"), staleTime: Infinity });
}

export function useAccount(enabled = true) {
  return useQuery({
    queryKey: keys.account,
    enabled,
    staleTime: 60_000,
    // /auth/session answers 200 with null when signed out, so probing never logs an error.
    queryFn: async () => (await api.get<{ account: Account | null }>("/auth/session")).account,
  });
}

export function useSignIn() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) => api.post<Account>("/auth/sign-in", body),
    onSuccess: (account) => {
      client.clear();
      client.setQueryData(keys.account, account);
      client.setQueryData(keys.setup, (s: SetupStatus | undefined) => ({ ...(s ?? { version: "" }), initialised: true }));
    },
  });
}

export function useSignOut() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/auth/sign-out"),
    onSettled: () => {
      client.clear();
      client.setQueryData(keys.account, null);
      client.setQueryData(keys.setup, { initialised: true, version: "" });
    },
  });
}

/* --------------------------------------------------------- organisation */

export function useOrganisation() {
  return useQuery({ queryKey: keys.organisation, queryFn: () => api.get<Organisation>("/organisation") });
}

function invalidateModelDependents(client: QueryClient) {
  return Promise.all([
    client.invalidateQueries({ queryKey: keys.organisation }),
    client.invalidateQueries({ queryKey: keys.overview }),
    client.invalidateQueries({ queryKey: keys.horizon }),
    client.invalidateQueries({ queryKey: keys.risk }),
    client.invalidateQueries({ queryKey: ["migration"] }),
    client.invalidateQueries({ queryKey: keys.systemsAll }),
    client.invalidateQueries({ queryKey: keys.auditAll }),
  ]);
}

export function useUpdateOrganisation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<{ name: string; sector: string; country: string }>) => api.patch<Organisation>("/organisation", body),
    onSuccess: (org) => {
      client.setQueryData(keys.organisation, org);
      client.setQueryData(keys.account, (a: Account | null | undefined) => (a ? { ...a, organisation: { id: org.id, name: org.name } } : a));
      return invalidateModelDependents(client);
    },
  });
}

export function useUpdateThreatModel() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ThreatModelSettings) => api.put<Organisation>("/organisation/threat-model", body),
    onSuccess: (org) => {
      client.setQueryData(keys.organisation, org);
      return invalidateModelDependents(client);
    },
  });
}

/* -------------------------------------------------------------- horizon */

export function useHorizon() {
  return useQuery({ queryKey: keys.horizon, queryFn: () => api.get<Horizon>("/horizon") });
}

export function useMilestones() {
  return useQuery({ queryKey: keys.milestones, queryFn: () => api.get<MilestoneCatalogue>("/horizon/milestones"), staleTime: Infinity });
}

export function useOverview() {
  return useQuery({ queryKey: keys.overview, queryFn: () => api.get<Overview>("/overview"), placeholderData: keepPreviousData });
}

/* -------------------------------------------------------------- systems */

export interface SystemFilters {
  q?: string;
  kind?: string[];
  criticality?: string[];
  exposure?: string[];
  classification?: string[];
  status?: string[];
  sort?: string;
}

export function useSystems(filters: SystemFilters) {
  return useQuery({
    queryKey: keys.systems(filters),
    queryFn: ({ signal }) => api.get<{ items: SystemRecord[]; total: number }>("/systems", { ...filters }, signal),
    placeholderData: keepPreviousData,
  });
}

export function useSystem(id: string) {
  return useQuery({ queryKey: keys.system(id), queryFn: () => api.get<SystemRecord>(`/systems/${id}`) });
}

export function useSystemsSummary() {
  return useQuery({ queryKey: keys.systemsSummary, queryFn: () => api.get<SystemsSummary>("/systems/summary") });
}

export function useVocabulary() {
  return useQuery({ queryKey: keys.vocabulary, queryFn: () => api.get<Vocabulary>("/systems/vocabulary"), staleTime: Infinity });
}

function invalidateSystems(client: QueryClient) {
  return Promise.all([
    client.invalidateQueries({ queryKey: keys.risk }),
    client.invalidateQueries({ queryKey: ["migration"] }),
    client.invalidateQueries({ queryKey: keys.systemsAll }),
    client.invalidateQueries({ queryKey: keys.overview }),
    client.invalidateQueries({ queryKey: keys.auditAll }),
  ]);
}

export function useCreateSystem() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: SystemInput) => api.post<SystemRecord>("/systems", body),
    onSuccess: (system) => {
      client.setQueryData(keys.system(system.id), system);
      return invalidateSystems(client);
    },
  });
}

export function useUpdateSystem(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<SystemInput>) => api.patch<SystemRecord>(`/systems/${id}`, body),
    onSuccess: (system) => {
      client.setQueryData(keys.system(id), system);
      return invalidateSystems(client);
    },
  });
}

export function useDeleteSystem() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/systems/${id}`),
    onSuccess: (_, id) => {
      client.removeQueries({ queryKey: keys.system(id) });
      return invalidateSystems(client);
    },
  });
}

/* -------------------------------------------------------------- members */

export function useMembers(enabled = true) {
  return useQuery({ queryKey: keys.members, queryFn: () => api.get<Member[]>("/members"), enabled });
}

export function useRoles() {
  return useQuery({ queryKey: keys.roles, queryFn: () => api.get<RoleInfo[]>("/members/roles"), staleTime: Infinity });
}

function invalidateMembers(client: QueryClient) {
  return Promise.all([client.invalidateQueries({ queryKey: keys.members }), client.invalidateQueries({ queryKey: keys.overview }), client.invalidateQueries({ queryKey: keys.auditAll })]);
}

export function useInviteMember() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; name: string; role: string }) => api.post<{ member: Member; activation_link: string }>("/members", body),
    onSuccess: () => invalidateMembers(client),
  });
}

export function useReissueInvitation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<{ expires_at: string; activation_link: string }>(`/members/${id}/invitation`),
    onSuccess: () => invalidateMembers(client),
  });
}

export function useUpdateMember() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; role?: string; status?: string }) => api.patch<Member>(`/members/${id}`, body),
    onSuccess: () => invalidateMembers(client),
  });
}

export function useRemoveMember() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (id: string) => api.delete(`/members/${id}`), onSuccess: () => invalidateMembers(client) });
}

/* ------------------------------------------------------- account & access */

export function useSessions() {
  return useQuery({ queryKey: keys.sessions, queryFn: () => api.get<SessionInfo[]>("/auth/sessions") });
}

export function useRevokeSession() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (id: string) => api.delete(`/auth/sessions/${id}`), onSuccess: () => client.invalidateQueries({ queryKey: keys.sessions }) });
}

export function useRevokeOtherSessions() {
  const client = useQueryClient();
  return useMutation({ mutationFn: () => api.delete<{ revoked: number }>("/auth/sessions"), onSuccess: () => client.invalidateQueries({ queryKey: keys.sessions }) });
}

export function useChangePassword() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) => api.post<void>("/auth/password", body),
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: keys.sessions }), client.invalidateQueries({ queryKey: keys.account })]),
  });
}

export function useUpdateProfile() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (body: { name: string }) => api.patch<Account>("/auth/me", body), onSuccess: (a) => client.setQueryData(keys.account, a) });
}

export function useTokens(enabled = true) {
  return useQuery({ queryKey: keys.tokens, queryFn: () => api.get<AccessTokenInfo[]>("/tokens"), enabled });
}

export function useCreateToken() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; expires_in_days: number | null }) => api.post<{ token: AccessTokenInfo; secret: string }>("/tokens", body),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.tokens }),
  });
}

export function useRevokeToken() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (id: string) => api.delete(`/tokens/${id}`), onSuccess: () => client.invalidateQueries({ queryKey: keys.tokens }) });
}

/* ------------------------------------------------------------------ audit */

export interface AuditFilters {
  category?: string;
  q?: string;
  target?: string;
}

export function useAudit(filters: AuditFilters, { enabled = true, limit = 50 }: { enabled?: boolean; limit?: number } = {}) {
  return useInfiniteQuery({
    queryKey: [...keys.audit(filters), limit],
    enabled,
    placeholderData: keepPreviousData,
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam, signal }) => api.get<AuditPage>("/audit", { limit, ...filters, before: pageParam }, signal),
    getNextPageParam: (last) => last.next_before ?? undefined,
  });
}

export function useVerifyLedger() {
  const client = useQueryClient();
  return useMutation({ mutationFn: () => api.post<LedgerVerification>("/audit/verify"), onSuccess: () => client.invalidateQueries({ queryKey: keys.auditAll }) });
}

export function useAbout() {
  return useQuery({ queryKey: keys.about, queryFn: () => api.get<About>("/platform/about") });
}

/* -------------------------------------------------------------- discovery */

export function useCapabilities() {
  return useQuery({ queryKey: keys.capabilities, queryFn: () => api.get<DiscoveryCapabilities>("/discovery/capabilities"), staleTime: 5 * 60_000 });
}

const isActive = (scan: ScanBrief | null | undefined) => !!scan && (scan.status === "queued" || scan.status === "running");

export function useSources(systemId: string, enabled = true) {
  return useQuery({
    queryKey: keys.sources(systemId),
    enabled,
    queryFn: () => api.get<Source[]>(`/systems/${systemId}/sources`),
    // While any source is scanning, keep its row current (the scan view streams; lists poll gently).
    refetchInterval: (query) => (query.state.data?.some((s) => isActive(s.active_scan)) ? 1500 : false),
  });
}

export interface ScanFilters {
  system?: string;
  status?: string[];
  limit?: number;
}

export function useScans(filters: ScanFilters = {}) {
  return useQuery({
    queryKey: keys.scans(filters),
    queryFn: ({ signal }) => api.get<ScanListItem[]>("/scans", { limit: 100, ...filters }, signal),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => (query.state.data?.some(isActive) ? 1500 : false),
  });
}

export function useScan(id: string) {
  return useQuery({ queryKey: keys.scan(id), enabled: !!id, queryFn: () => api.get<ScanDetail>(`/scans/${id}`) });
}

export interface ArtefactFilters {
  system?: string;
  kind?: string[];
  quantum?: string[];
  classical?: string[];
  status?: "active" | "resolved" | "all";
  family?: string;
  q?: string;
  scan?: string;
  sort?: "risk" | "name" | "recent" | "evidence";
}

const ARTEFACT_PAGE = 100;

export function useArtefacts(filters: ArtefactFilters, enabled = true) {
  return useInfiniteQuery({
    queryKey: keys.artefacts(filters),
    enabled,
    placeholderData: keepPreviousData,
    initialPageParam: 0,
    queryFn: ({ pageParam, signal }) => api.get<ArtefactPage>("/artefacts", { ...filters, limit: ARTEFACT_PAGE, offset: pageParam }, signal),
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, p) => n + p.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
  });
}

export function useArtefact(id: string) {
  return useQuery({ queryKey: keys.artefact(id), queryFn: () => api.get<ArtefactDetail>(`/artefacts/${id}`) });
}

export function useInventorySummary(system?: string, enabled = true) {
  return useQuery({
    queryKey: keys.inventory(system),
    enabled,
    queryFn: () => api.get<InventorySummary>("/inventory/summary", { system }),
    placeholderData: keepPreviousData,
  });
}

/** A scan changes the inventory, the systems register and the overview at once. */
export function invalidateDiscovery(client: QueryClient) {
  return Promise.all([
    client.invalidateQueries({ queryKey: keys.discovery }),
    client.invalidateQueries({ queryKey: keys.risk }),
    client.invalidateQueries({ queryKey: ["migration"] }),
    client.invalidateQueries({ queryKey: keys.systemsAll }),
    client.invalidateQueries({ queryKey: keys.overview }),
    client.invalidateQueries({ queryKey: keys.auditAll }),
  ]);
}

export interface NewSource {
  kind: "directory" | "archive" | "image-archive" | "git" | "image-registry" | "endpoint";
  locator: string;
  name?: string;
  options?: Record<string, unknown>;
  scan_now?: boolean;
}

export function useCreateSource(systemId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: NewSource) => api.post<{ source: Source; scan: ScanBrief | null }>(`/systems/${systemId}/sources`, body),
    onSuccess: () => invalidateDiscovery(client),
  });
}

export function useStartScan() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) => api.post<ScanBrief>(`/sources/${sourceId}/scans`),
    onSuccess: () => invalidateDiscovery(client),
  });
}

export function useCancelScan() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (scanId: string) => api.post<ScanBrief>(`/scans/${scanId}/cancel`),
    onSuccess: () => invalidateDiscovery(client),
  });
}

export function useRenameSource() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api.patch<Source>(`/sources/${id}`, { name }),
    onSuccess: () => invalidateDiscovery(client),
  });
}

export function useRemoveSource() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (id: string) => api.delete(`/sources/${id}`), onSuccess: () => invalidateDiscovery(client) });
}

/* ------------------------------------------------------------------ risk */

export interface RiskFilters {
  system?: string;
  band?: string[];
  kind?: string[];
  role?: string;
  hndl?: boolean;
  lifetime?: string;
  framework?: string;
  policy_status?: string[];
  likelihood?: string;
  impact?: string;
  q?: string;
  sort?: "score" | "exposure" | "probability" | "name";
}

export function useRiskSummary(system?: string) {
  return useQuery({ queryKey: keys.riskSummary(system), queryFn: () => api.get<RiskSummary>("/risk/summary", { system }), placeholderData: keepPreviousData });
}

export function useRiskRegister(filters: RiskFilters, enabled = true) {
  return useInfiniteQuery({
    queryKey: keys.riskRegister(filters),
    enabled,
    placeholderData: keepPreviousData,
    initialPageParam: 0,
    queryFn: ({ pageParam, signal }) => api.get<{ items: RiskRow[]; total: number }>("/risk/register", { ...filters, limit: 100, offset: pageParam }, signal),
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, p) => n + p.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
  });
}

export function useRiskArtefact(id: string, enabled = true) {
  return useQuery({ queryKey: keys.riskArtefact(id), enabled: enabled && !!id, queryFn: () => api.get<RiskDetail>(`/risk/artefacts/${id}`) });
}

export function useRiskTimeline(system?: string) {
  return useQuery({
    queryKey: keys.riskTimeline(system),
    queryFn: () => api.get<RiskTimelinePayload>("/risk/timeline", { system, until: 2045 }),
    placeholderData: keepPreviousData,
  });
}

export function useRiskPolicies() {
  return useQuery({ queryKey: keys.riskPolicies, queryFn: () => api.get<PolicyOverview>("/risk/policies") });
}

/* ------------------------------------------------------------- migration */

export function useRecommendation(id: string, enabled = true) {
  return useQuery({ queryKey: ["migration", "recommendation", id], enabled: enabled && !!id, queryFn: () => api.get<Recommendation>(`/migration/recommendations/${id}`) });
}

export function useMigrationPlan(system?: string) {
  return useQuery({ queryKey: ["migration", "plan", system ?? "all"], queryFn: () => api.get<MigrationPlan>("/migration/plan", { system }), placeholderData: keepPreviousData });
}

export function useBlastGraph() {
  return useQuery({ queryKey: ["migration", "graph"], queryFn: () => api.get<BlastGraph>("/migration/graph") });
}

export function useBenchmarks() {
  return useQuery({ queryKey: ["migration", "benchmarks"], queryFn: async () => (await api.get<{ report: BenchmarkReport | null }>("/migration/benchmarks")).report });
}

export function useRunBenchmarks() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => (await api.post<{ report: BenchmarkReport }>("/migration/benchmarks")).report,
    onSuccess: (report) => {
      client.setQueryData(["migration", "benchmarks"], report);
      return client.invalidateQueries({ queryKey: ["migration"] });
    },
  });
}

export function useScanDiff(scanId: string, enabled = true) {
  return useQuery({ queryKey: ["discovery", "diff", scanId], enabled: enabled && !!scanId, queryFn: () => api.get<ScanDiff>(`/scans/${scanId}/diff`) });
}

/* --------------------------------------------------------------- reports */

export function useReportFormats() {
  return useQuery({ queryKey: ["reports", "formats"], queryFn: async () => (await api.get<{ formats: ReportFormat[] }>("/reports/formats")).formats, staleTime: Infinity });
}

export function useSnapshots() {
  return useQuery({ queryKey: ["reports", "snapshots"], queryFn: async () => (await api.get<{ items: Snapshot[] }>("/reports/snapshots")).items });
}

export function useSnapshot(id: string | null) {
  return useQuery({ queryKey: ["reports", "snapshot", id], enabled: !!id, queryFn: () => api.get<SnapshotDetail>(`/reports/snapshots/${id}`) });
}

export function useCreateSnapshot() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { label?: string; system_id?: string | null }) => api.post<Snapshot>("/reports/snapshots", body),
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: ["reports"] }), client.invalidateQueries({ queryKey: keys.auditAll })]),
  });
}

export function useDrift(base: string | null, head: string | null) {
  return useQuery({
    queryKey: ["reports", "drift", base, head ?? "live"],
    enabled: !!base,
    queryFn: () => api.get<Drift>("/reports/drift", { base: base ?? undefined, head: head ?? undefined }),
    placeholderData: keepPreviousData,
  });
}

export function useAttestationKey() {
  return useQuery({ queryKey: ["reports", "key"], queryFn: () => api.get<AttestationKey>("/reports/key") });
}

export function useRotateKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<AttestationKey>("/reports/key/rotate"),
    onSuccess: (key) => {
      client.setQueryData(["reports", "key"], key);
      return client.invalidateQueries({ queryKey: keys.auditAll });
    },
  });
}

export function useVerifyEnvelope() {
  return useMutation({ mutationFn: (body: { envelope: unknown; public_key?: string }) => api.post<Verification>("/reports/verify", body) });
}

/* ------------------------------------------------------------ prefetch */

type Prefetch = { queryKey: readonly unknown[]; queryFn: () => Promise<unknown> };

/** The data each page waits on first, so pointing at a link can start loading it before the click. */
const ROUTE_DATA: Record<string, () => Prefetch[]> = {
  "/": () => [{ queryKey: keys.overview, queryFn: () => api.get<Overview>("/overview") }],
  "/inventory": () => [{ queryKey: keys.inventory(undefined), queryFn: () => api.get<InventorySummary>("/inventory/summary", {}) }],
  "/risk": () => [{ queryKey: keys.riskSummary(undefined), queryFn: () => api.get<RiskSummary>("/risk/summary", {}) }],
  "/time-machine": () => [{ queryKey: keys.riskTimeline(undefined), queryFn: () => api.get<RiskTimelinePayload>("/risk/timeline", { until: 2045 }) }],
  "/compliance": () => [{ queryKey: keys.riskPolicies, queryFn: () => api.get<PolicyOverview>("/risk/policies") }],
  "/horizon": () => [{ queryKey: keys.horizon, queryFn: () => api.get<Horizon>("/horizon") }],
  "/migration": () => [{ queryKey: ["migration", "plan", "all"], queryFn: () => api.get<MigrationPlan>("/migration/plan", {}) }],
  "/blast-radius": () => [{ queryKey: ["migration", "graph"], queryFn: () => api.get<BlastGraph>("/migration/graph") }],
  "/reports": () => [
    { queryKey: ["reports", "formats"], queryFn: async () => (await api.get<{ formats: ReportFormat[] }>("/reports/formats")).formats },
    { queryKey: ["reports", "snapshots"], queryFn: async () => (await api.get<{ items: Snapshot[] }>("/reports/snapshots")).items },
  ],
};
ROUTE_DATA["/brief"] = () => [...ROUTE_DATA["/risk"](), ...ROUTE_DATA["/migration"](), ...ROUTE_DATA["/compliance"]()];

export function prefetchRoute(path: string): void {
  for (const q of ROUTE_DATA[path]?.() ?? []) void queryClient.prefetchQuery(q);
}

/* ---------------------------------------------------------------- exports */

export function useExports() {
  return useQuery({ queryKey: ["reports", "exports"], queryFn: () => api.get<{ items: ExportRecord[]; location: ExportLocation }>("/reports/exports") });
}

export function useExportLocationMutations() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ["reports", "exports"] });
  return {
    choose: useMutation({ mutationFn: (path: string) => api.put<ExportLocation>("/reports/exports/location", { path }), onSuccess: refresh }),
    reset: useMutation({ mutationFn: () => api.delete<ExportLocation>("/reports/exports/location"), onSuccess: refresh }),
    open: useMutation({ mutationFn: () => api.post<ExportLocation>("/reports/exports/location/open") }),
  };
}

export function useRemoveExport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/reports/exports/${id}`),
    onMutate: async (id) => {
      await client.cancelQueries({ queryKey: ["reports", "exports"] });
      const before = client.getQueryData<{ items: ExportRecord[]; location: ExportLocation }>(["reports", "exports"]);
      if (before) client.setQueryData(["reports", "exports"], { ...before, items: before.items.filter((e) => e.id !== id) });
      return { before };
    },
    onError: (_e, _id, ctx) => ctx?.before && client.setQueryData(["reports", "exports"], ctx.before),
    onSettled: () => client.invalidateQueries({ queryKey: ["reports", "exports"] }),
  });
}

/** Wire types for the FALCON API (mirrors the server's payloads). */

export type Permission =
  | "org.manage"
  | "threat.manage"
  | "members.read"
  | "members.manage"
  | "systems.read"
  | "systems.write"
  | "systems.delete"
  | "audit.read"
  | "tokens.use"
  | "inventory.read"
  | "sources.manage"
  | "scans.run"
  | "reports.sign";

export type RoleKey = "owner" | "admin" | "security_lead" | "analyst" | "auditor" | "viewer";

export interface Account {
  user: {
    id: string;
    email: string;
    name: string;
    role: RoleKey;
    role_label: string;
    last_sign_in_at: string | null;
    password_changed_at: string | null;
  };
  permissions: Permission[];
  via: "session" | "token";
  organisation: { id: string; name: string } | null;
}

export type ScenarioKey = "aggressive" | "moderate" | "conservative";
export type Scenario = ScenarioKey | "custom";
export type Uncertainty = "narrow" | "moderate" | "wide";

export interface ScenarioPreset {
  label: string;
  median_year: number;
  sigma: number;
  summary: string;
}

export interface HorizonCatalogue {
  scenarios: Record<ScenarioKey, ScenarioPreset>;
  uncertainty: Record<Uncertainty, number>;
  tolerances: number[];
}

export interface SetupStatus {
  initialised: boolean;
  version: string;
  /** Running inside the FALCON desktop app. */
  desktop?: boolean;
  sectors?: string[];
  horizon?: HorizonCatalogue;
}

export interface ThreatModelSummary {
  scenario: Scenario;
  median_year: number;
  sigma: number;
  tolerance: number;
  evaluated_at: number;
  planning_years: number;
  planning_year: number;
  p10_year: number;
  p50_year: number;
  p90_year: number;
}

export interface ThreatModelSettings {
  crqc_scenario: Scenario;
  crqc_median_year: number | null;
  crqc_uncertainty: Uncertainty | null;
  risk_tolerance: number;
}

export interface Organisation {
  id: string;
  name: string;
  sector: string;
  country: string;
  created_at: string;
  threat_model: ThreatModelSettings & Omit<ThreatModelSummary, "scenario" | "tolerance">;
}

export interface CurvePoint {
  year: number;
  p: number;
}

export interface Horizon {
  model: ThreatModelSummary;
  curve: CurvePoint[];
  catalogue: HorizonCatalogue;
}

export interface Milestone {
  id: string;
  date: string;
  precision: "day" | "month" | "year";
  authority: string;
  authority_name: string;
  region: string;
  framework: string;
  kind: "publication" | "deadline" | "guidance";
  title: string;
  detail: string;
  source: string;
  year: number;
  decimal_year: number;
}

export interface MilestoneCatalogue {
  version: string;
  note: string;
  authorities: Record<string, { name: string; region: string; kind: string }>;
  milestones: Milestone[];
}

export type MoscaStatus = "exposed" | "watch" | "clear";

export interface Mosca {
  x: number;
  y: number;
  z: number;
  exposure_years: number;
  status: MoscaStatus;
  probability: number;
  complete_by: number;
  start_by: number;
  overdue_years: number;
}

export type SystemKind = "application" | "service" | "product" | "platform" | "infrastructure" | "device" | "data_store";
export type Criticality = "critical" | "high" | "moderate" | "low";
export type Classification = "secret" | "restricted" | "confidential" | "internal" | "public";
export type Exposure = "external" | "partner" | "internal" | "isolated";
export type Lifecycle = "planned" | "active" | "sunsetting" | "retired";
export type Environment = "production" | "staging" | "development" | "disaster_recovery";

export interface SystemRecord {
  id: string;
  code: string;
  name: string;
  description: string | null;
  kind: SystemKind;
  lifecycle: Lifecycle;
  environment: Environment;
  exposure: Exposure;
  criticality: Criticality;
  data_classification: Classification;
  data_shelf_life_years: number;
  migration_years: number;
  owner: string | null;
  team: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
  mosca: Mosca;
  inventory?: { artefacts: number; vulnerable: number; last_scan_at: string | null };
}

export type SystemInput = Omit<SystemRecord, "id" | "created_at" | "updated_at" | "mosca" | "inventory">;

export interface VocabularyEntry {
  label: string;
  rank?: number;
  summary?: string;
  migration_years?: number;
  shelf_life_years?: number;
}

export interface Vocabulary {
  kinds: Record<SystemKind, VocabularyEntry>;
  criticality: Record<Criticality, VocabularyEntry>;
  classification: Record<Classification, VocabularyEntry>;
  exposure: Record<Exposure, VocabularyEntry>;
  lifecycle: Record<Lifecycle, VocabularyEntry>;
  environment: Record<Environment, VocabularyEntry>;
}

export interface Tally {
  key: string;
  label: string;
  count: number;
}

export interface PlanePoint {
  id: string;
  code: string;
  name: string;
  criticality: Criticality;
  kind: SystemKind;
  x: number;
  y: number;
  z: number;
  exposure_years: number;
  status: MoscaStatus;
  probability: number;
  start_by: number;
}

export interface SystemsSummary {
  total: number;
  active: number;
  retired: number;
  mosca: {
    exposed: number;
    watch: number;
    clear: number;
    mean_probability: number;
    max_probability: number;
    overdue: number;
  };
  by_criticality: Tally[];
  by_classification: Tally[];
  by_exposure: Tally[];
  by_kind: Tally[];
  plane: PlanePoint[];
}

export interface ChecklistItem {
  key: string;
  title: string;
  done: boolean;
  detail: string;
}

export interface Overview {
  organisation: Organisation;
  horizon: ThreatModelSummary;
  systems: SystemsSummary;
  milestones: Milestone[];
  checklist: ChecklistItem[];
  discovery?: { inventory: InventorySummary; recent_scans: ScanListItem[] };
  risk?: Pick<RiskSummary, "bands" | "hndl" | "total" | "assessed" | "systems" | "top">;
}

export interface Member {
  id: string;
  email: string;
  name: string;
  role: RoleKey;
  status: "invited" | "active" | "disabled";
  created_at: string;
  last_sign_in_at: string | null;
  invitation_expires_at: string | null;
}

export interface RoleInfo {
  key: RoleKey;
  label: string;
  summary: string;
  assignable: boolean;
  permissions: Permission[];
}

export interface SessionInfo {
  id: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  ip: string | null;
  user_agent: string | null;
  current: boolean;
}

export interface AccessTokenInfo {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
}

export interface AuditEvent {
  id: string;
  seq: number;
  occurred_at: string;
  actor_id: string | null;
  actor_label: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  summary: string;
  detail: Record<string, unknown> | null;
  ip: string | null;
  hash: string;
  prev_hash: string;
}

export interface AuditPage {
  events: AuditEvent[];
  next_before: number | null;
  head: { seq: number; hash: string } | null;
  categories: string[];
}

export interface LedgerVerification {
  valid: boolean;
  checked: number;
  broken_at: number | null;
  reason: string | null;
  head_seq: number | null;
  head_hash?: string;
}

export interface About {
  product: string;
  version: string;
  database: string;
  python: string;
  cryptography: string;
  openssl: string;
  uptime_seconds: number;
  knowledge: Record<string, string>;
}

/* ------------------------------------------------------------- discovery */

export type SourceKind = "directory" | "archive" | "git" | "image-archive" | "image-registry" | "endpoint";
export type ScanStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type ScanStage = "acquire" | "enumerate" | "analyse" | "done";
export type ArtefactKind = "algorithm" | "key" | "certificate" | "protocol" | "library" | "hardware" | "cloud_service";
export type QuantumStatus = "vulnerable" | "weakened" | "unknown" | "hybrid" | "resistant" | "pqc";
export type ClassicalStatus = "broken" | "weak" | "legacy" | "acceptable" | "strong" | "unknown";

export interface DiscoveryCapabilities {
  desktop: boolean;
  source_kinds: { kind: SourceKind; label: string; available: boolean; reason: string | null }[];
  scan_roots: string[];
  any_folder: boolean;
  upload_max_mb: number;
  engine_version: string;
  knowledge: { algorithms: string; libraries: string };
}

export interface ScanBrief {
  id: string;
  source_id: string;
  system_id: string;
  status: ScanStatus;
  stage: ScanStage | null;
  stage_detail: string | null;
  files_total: number;
  files_done: number;
  bytes_done: number;
  evidence: number;
  artefacts: number;
  new_artefacts: number;
  error: string | null;
  requested_by: string | null;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
}

export interface ScanListItem extends ScanBrief {
  source_name: string;
  source_kind: SourceKind;
  source_kind_label: string;
  system_name: string;
  system_code: string;
}

export interface CoverageLeaf {
  files: number;
  bytes: number;
  scanned: number;
  findings: number;
}

export interface ScanDetail extends ScanBrief {
  coverage: Record<string, CoverageLeaf>;
  stats: {
    engine?: string;
    knowledge?: { algorithms: string; libraries: string };
    openssl?: string;
    source?: Record<string, unknown>;
    skipped?: Record<string, number>;
    composition?: Record<string, number>;
    files?: number;
    bytes?: number;
    duration_seconds?: number;
    file_errors?: { path: string; error: string }[];
    endpoints?: EndpointReport[];
  };
  source: { id: string; name: string; kind: SourceKind; kind_label: string } | null;
  system: { id: string; name: string; code: string } | null;
  summary?: InventorySummary;
}

export interface EndpointReport {
  endpoint: string;
  error?: string;
  pq_probe?: { selected: string | null; offered: string[]; hello_retry: boolean; error?: string | null };
  version?: string | null;
  cipher?: string | null;
  certificates?: number;
  also_accepted?: string[];
}

export interface Source {
  id: string;
  system_id: string;
  kind: SourceKind;
  kind_label: string;
  name: string;
  locator: string;
  options: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  last_scan: ScanBrief | null;
  active_scan: ScanBrief | null;
}

export interface Assessment {
  classical_bits: number | null;
  quantum_bits: number | null;
  quantum: QuantumStatus;
  classical: ClassicalStatus;
  primitive: string | null;
  reasons: string[];
  nist_category: number | null;
}

export interface Artefact {
  id: string;
  system_id: string;
  kind: ArtefactKind;
  name: string;
  family: string | null;
  quantum: QuantumStatus | null;
  classical: ClassicalStatus | null;
  primitive: string | null;
  confidence: number;
  status: "active" | "resolved";
  occurrences: number;
  first_seen_at: string;
  last_seen_at: string;
  identity: Record<string, unknown>;
  properties: Record<string, unknown> & { assessment?: Assessment };
  system?: { id: string; name: string; code: string };
}

export interface Evidence {
  id: string;
  scan_id: string;
  source: string;
  path: string;
  line: number | null;
  column: number | null;
  snippet: [number, string][] | null;
  detector: string;
  rule: string;
  confidence: number;
  function: string | null;
  via: string | null;
  scanned_at: string | null;
}

export interface ArtefactLinkInfo {
  direction: "in" | "out";
  relation: string;
  artefact: { id: string; name: string; kind: ArtefactKind; quantum: QuantumStatus | null };
}

export interface ArtefactDetail extends Artefact {
  evidence: Evidence[];
  links: ArtefactLinkInfo[];
  catalogue?: { description: string | null; standard: string | null; class: string | null; primitives: string[] | null };
  assessment: Partial<Assessment>;
}

export interface InventorySummary {
  total: number;
  systems: number;
  by_kind: Record<ArtefactKind, number>;
  by_quantum: Partial<Record<QuantumStatus, number>>;
  by_classical: Partial<Record<ClassicalStatus, number>>;
  matrix: Partial<Record<ArtefactKind, Partial<Record<QuantumStatus, number>>>>;
  top_families: { family: string; count: number }[];
  libraries: { total: number; pqc_capable: number; end_of_life: number; abandoned: number };
  certificates: { total: number; expired: number; expiring_90_days: number; self_signed: number };
}

export interface ArtefactPage {
  items: Artefact[];
  total: number;
}

/* ------------------------------------------------------------------ risk */

export type RiskBand = "critical" | "high" | "medium" | "low" | "none";
export type RiskRole = "confidentiality" | "authenticity" | "integrity" | "enabling";
export type PolicyStatus = "approved" | "acceptable" | "not-applicable" | "transition" | "not-approved" | "deprecated" | "disallowed";
export type FrameworkId = "nist-ir-8547" | "nist-sp-800-131a" | "cnsa-2.0" | "eu-pqc-roadmap";

export interface RiskModelInfo {
  now: number;
  planning_years: number;
  planning_year: number;
  planning_label: string;
  tolerance: number;
  scenario: string;
}

export interface RiskMosca {
  x: number;
  y: number;
  z: number;
  exposure_years: number;
  status: MoscaStatus;
  probability: number;
  complete_by: number;
  start_by: number;
}

export interface RiskTimeline {
  at_risk: number | null;
  exposed: number | null;
  broken: number | null;
}

export interface RiskRow {
  id: string;
  name: string;
  kind: ArtefactKind;
  family: string | null;
  quantum: QuantumStatus | null;
  classical: ClassicalStatus | null;
  system: { id: string; code: string; name: string; criticality: Criticality };
  score: number;
  band: RiskBand;
  roles: RiskRole[];
  lifetime: { years: number; basis: string; band: string };
  migration: { key: string; label: string; years: number; summary?: string };
  mosca: RiskMosca;
  hndl: { applies: boolean; reach: "internet" | "partner" | "insider" | "isolated" | null; exposed: boolean };
  classification: { type: ArtefactKind; role: string; lifetime: string; criticality: Criticality; mosca: string };
  likelihood: { value: number; driver: "classical" | "quantum" | "policy"; bucket: string };
  impact: { value: number; bucket: string };
  driver: string | null;
  policy: Record<FrameworkId, PolicyStatus>;
  timeline: RiskTimeline;
}

export interface FrameworkInfo {
  name: string;
  authority: string;
  title: string;
  publication: string;
  source: string;
  summary: string;
}

export interface PolicyResultInfo extends FrameworkInfo {
  framework: FrameworkId;
  status: PolicyStatus;
  status_now: PolicyStatus;
  rule: string;
  deprecated_from: number | null;
  disallowed_from: number | null;
}

export interface RiskDetail extends Omit<RiskRow, "impact" | "likelihood"> {
  model: RiskModelInfo;
  impact: { value: number; bucket: string; criticality: number; exposure: number; classification: number | null };
  likelihood: {
    value: number;
    bucket: string;
    driver: "classical" | "quantum" | "policy";
    classical: number;
    quantum: number;
    quantum_severity: number;
    policy: number;
    policy_deadline: number | null;
  };
  drivers: string[];
  policies: PolicyResultInfo[];
}

export interface RiskSystemRow {
  id: string;
  code: string;
  name: string;
  criticality: Criticality;
  exposure: Exposure;
  artefacts: number;
  score: number;
  band: RiskBand;
  bands: Partial<Record<RiskBand, number>>;
  hndl_exposed: number;
  x: number;
  register_y: number;
  estimated_y: number | null;
}

export interface RiskSummary {
  model: RiskModelInfo;
  total: number;
  assessed: number;
  bands: Record<RiskBand, number>;
  hndl: { applies: number; exposed: number; systems: number; internet: number };
  matrix: {
    likelihood: { key: string; label: string }[];
    impact: { key: string; label: string }[];
    cells: { likelihood: string; impact: string; count: number; score: number; band: RiskBand }[];
  };
  classification: {
    lifetimes: { key: string; label: string }[];
    rows: { kind: ArtefactKind; cells: Record<string, { count: number; score: number }> }[];
    roles: Partial<Record<RiskRole, number>>;
    mosca: Record<string, number>;
  };
  plane: { x: number; y: number; count: number; band: RiskBand; exposure: number; kinds: Partial<Record<ArtefactKind, number>>; sample: string[] }[];
  systems: RiskSystemRow[];
  compliance: Record<FrameworkId, Partial<Record<PolicyStatus, number>>>;
  top: RiskRow[];
}

export interface TimelineEvent {
  year: number;
  kind: "horizon" | "probability" | "policy" | "certificate" | "library";
  title: string;
  detail: string;
  count: number | null;
  framework: FrameworkId | null;
}

export interface TimelineArtefact {
  id: string;
  name: string;
  kind: ArtefactKind;
  system_id: string;
  band: RiskBand;
  score: number;
  t: RiskTimeline;
  policy: Partial<Record<FrameworkId, number>>;
}

export interface RiskTimelinePayload {
  model: RiskModelInfo;
  until: number;
  curve: CurvePoint[];
  systems: { id: string; code: string; name: string; criticality: Criticality }[];
  artefacts: TimelineArtefact[];
  events: TimelineEvent[];
}

export interface PolicyOverview {
  model: RiskModelInfo;
  statuses: PolicyStatus[];
  frameworks: (FrameworkInfo & {
    id: FrameworkId;
    now: Partial<Record<PolicyStatus, number>>;
    at: Record<string, Partial<Record<PolicyStatus, number>>>;
    dates: number[];
  })[];
}

/* ------------------------------------------------------------- migration */

export interface PqcAlgorithm {
  name: string;
  standard: string;
  category: number | null;
  summary: string;
  why: string;
  sizes: { public_key?: number; ciphertext?: number; signature?: number };
}

export interface BenchmarkResult {
  algorithm: string;
  kind: "kem" | "signature";
  quantum: "pqc" | "hybrid" | "vulnerable";
  category: number | null;
  operations: Record<string, number>;
  sizes: { public_key: number; ciphertext?: number; signature?: number };
}

export interface BenchmarkReport {
  measured_at: string;
  duration_seconds: number;
  host: { machine: string; processor: string; cpus: number; system: string; python: string; openssl: string };
  method: string;
  results: BenchmarkResult[];
}

export interface Recommendation {
  action: "replace" | "upgrade" | "enable" | "reissue" | "refresh" | "strengthen" | "keep";
  title: string;
  summary: string;
  grade: string;
  primary: PqcAlgorithm | null;
  hybrid: PqcAlgorithm | null;
  alternatives: PqcAlgorithm[];
  overhead: { before: number | null; after: number; delta: number | null; unit: string } | null;
  latency: { after: BenchmarkResult; before?: BenchmarkResult } | null;
  effort: { years: number; label: string };
  steps: string[];
}

export interface PlanItem {
  id: string;
  name: string;
  kind: ArtefactKind;
  band: RiskBand;
  score: number;
  system: { id: string; code: string; name: string; criticality: Criticality };
  years: number;
  effort: string;
  action: Recommendation["action"];
  recommendation: string;
  primary: string | null;
}

export type WaveKey = "fix-now" | "stop-harvest" | "long-lead" | "before-2030" | "complete";

export interface Wave {
  key: WaveKey;
  title: string;
  summary: string;
  start: number;
  finish: number;
  artefacts: number;
  systems: number;
  effort_years: number;
  deadline: number | null;
  on_time: boolean | null;
  items: PlanItem[];
}

export interface MigrationPlan {
  model: RiskModelInfo;
  waves: Wave[];
  lanes: { system: { id: string; code: string; name: string; criticality: Criticality }; bars: { wave: WaveKey; start: number; finish: number; count: number; worst: RiskBand }[] }[];
  completion: number;
  completion_probability: number;
  horizon: number;
  totals: { artefacts: number; effort_years: number; systems: number; actions: Record<string, number>; targets: { name: string; count: number }[] };
  benchmarked: boolean;
}

export interface BlastNode {
  id: string;
  label: string;
  kind: ArtefactKind;
  systems: string[];
  artefacts: number;
  band: RiskBand;
  score: number;
  hndl: number;
  sample: string;
  radius: number;
  mission_critical: number;
}

export interface BlastGraph {
  model: RiskModelInfo;
  systems: { id: string; code: string; name: string; criticality: Criticality; exposure: Exposure }[];
  nodes: BlastNode[];
  links: { system: string; node: string; artefacts: number; band: RiskBand }[];
}

export interface ScanDiffRow {
  id: string;
  name: string;
  kind: ArtefactKind;
  quantum: QuantumStatus | null;
  classical: ClassicalStatus | null;
  new_locations?: string[];
}

export interface ScanDiff {
  scan: ScanBrief;
  base: ScanBrief | null;
  added: ScanDiffRow[];
  removed: ScanDiffRow[];
  spread: ScanDiffRow[];
  unchanged: number;
  before: Partial<Record<QuantumStatus, number>>;
  after: Partial<Record<QuantumStatus, number>>;
  verified: { retired: number; introduced: number; regressions: number };
  verdict: "improved" | "regressed" | "mixed" | "unchanged" | "baseline";
}

/* ---------------------------------------------------------------- reports */

export type ReportFormatId = "cyclonedx-json" | "cyclonedx-xml" | "sarif" | "spdx" | "csv" | "json";

export interface ReportFormat {
  id: ReportFormatId;
  label: string;
  extension: string;
  media: string;
  summary: string;
}

export interface SnapshotSummary {
  artefacts: number;
  kinds: Partial<Record<ArtefactKind, number>>;
  bands: Record<RiskBand, number>;
  quantum: Partial<Record<QuantumStatus | "n/a", number>>;
  hndl_exposed: number;
  broken_or_weak: number;
  max_score: number;
  scope: string;
  organisation: string;
  threat_model: string;
}

export interface Snapshot {
  id: string;
  label: string;
  created_at: string;
  created_by: string | null;
  system_id: string | null;
  digest: string;
  components: number;
  summary: SnapshotSummary;
  key_id: string;
}

export interface VerificationCheck {
  check: "envelope" | "key" | "signature" | "statement" | "digest";
  ok: boolean;
  detail: string;
}

export interface Verification {
  valid: boolean;
  algorithm: string;
  key_id: string | null;
  subject: { name: string; sha256: string } | null;
  checks: VerificationCheck[];
  components?: number;
  timestamp?: string;
  stored_matches?: boolean;
  scope?: string;
  organisation?: string;
  artefacts?: number;
}

export interface SnapshotDetail extends Snapshot {
  verification: Verification;
}

export interface DriftRow {
  ref: string;
  name: string;
  kind: string;
  system: string | null;
  quantum: QuantumStatus | null;
  band: RiskBand | null;
  score: number;
  changes?: Record<string, { from: string | null; to: string | null }>;
  direction?: "better" | "worse" | "same";
}

export interface Drift {
  base: { serial: string; timestamp: string; components: number } & Partial<Snapshot>;
  head: { serial?: string; timestamp?: string; components?: number; id: string | null; label: string; created_at: string };
  added: DriftRow[];
  removed: DriftRow[];
  changed: DriftRow[];
  unchanged: number;
  totals: { risk_before: number; risk_after: number; vulnerable_before: number; vulnerable_after: number; pqc_before: number; pqc_after: number };
  verified: { retired: number; introduced: number; regressions: number };
  verdict: "improved" | "regressed" | "mixed" | "changed" | "unchanged";
}

export interface AttestationKey {
  key_id: string;
  algorithm: string;
  standard: string;
  nist_category: number;
  created_at: string;
  public_key_bytes: number;
  signature_bytes: number;
  public_key_pem: string;
  fingerprint: string;
  known_keys: string[];
}

export interface ExportLocation {
  path: string;
  default: string;
  custom: boolean;
  desktop: boolean;
  exists: boolean;
}

export interface ExportRecord {
  id: string;
  created_at: string;
  created_by: string | null;
  kind: "inventory" | "snapshot" | "key";
  format: string;
  label: string;
  scope: string;
  system_id: string | null;
  filename: string;
  size: number;
  sha256: string;
  path: string | null;
  available: boolean;
}

export type ExportRequest =
  | { kind?: "inventory"; format: ReportFormatId; system_id?: string | null }
  | { kind: "snapshot"; snapshot_id: string; part: "cbom" | "envelope" }
  | { kind: "key" };

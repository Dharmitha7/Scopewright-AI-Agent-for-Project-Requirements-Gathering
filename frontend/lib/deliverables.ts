/** Mirrors backend REQUIREMENTS_PACKS — labels for UI only. */

export type DeliverablePackMeta = {
  key: string;
  title: string;
  short: string;
};

export const REQUIREMENTS_PACKS: DeliverablePackMeta[] = [
  { key: "requirements_summary", title: "Requirements Summary", short: "Summary" },
  {
    key: "business_requirements",
    title: "Business Requirements Specification",
    short: "Business",
  },
  {
    key: "functional_requirements",
    title: "Functional Requirements Specification",
    short: "Functional",
  },
  {
    key: "non_functional_requirements",
    title: "Non-Functional Requirements",
    short: "Non-functional",
  },
  {
    key: "epics_features_stories",
    title: "Epics > Features > Stories (With Acceptance Criteria)",
    short: "Stories",
  },
  { key: "data_requirements", title: "Data Requirements", short: "Data" },
  { key: "integration_requirements", title: "Integration Requirements", short: "Integration" },
  { key: "traceability_matrix", title: "Requirements Traceability Matrix", short: "RTM" },
  { key: "user_journey", title: "User Journey Document", short: "User journey" },
  {
    key: "quality_gap_report",
    title: "Requirements Quality & Gap Report",
    short: "Quality report",
  },
];

const BY_KEY = Object.fromEntries(REQUIREMENTS_PACKS.map((p) => [p.key, p])) as Record<
  string,
  DeliverablePackMeta
>;

export function packLabel(key: string): string {
  return BY_KEY[key]?.title ?? titleCaseKey(key);
}

export function packShortLabel(key: string): string {
  return BY_KEY[key]?.short ?? packLabel(key);
}

export function packLabels(keys: string[]): string {
  return keys.map(packShortLabel).join(", ");
}

function titleCaseKey(key: string): string {
  return key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

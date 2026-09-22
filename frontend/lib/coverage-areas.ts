/** Mirror of backend templates.py CoverageArea rows — used to hydrate stored widgets. */

export type CoverageAreaMeta = {
  key: string;
  label: string;
  hint: string;
};

export const COVERAGE_TEMPLATES: Record<string, CoverageAreaMeta[]> = {
  planning: [
    {
      key: "business_need",
      label: "Business need & vision",
      hint: "What problem this solves and for whom",
    },
    {
      key: "scope",
      label: "Scope & exclusions",
      hint: "What's in v1 and what's explicitly out",
    },
    {
      key: "stakeholders",
      label: "Stakeholders",
      hint: "Who decides, uses it, and builds it",
    },
    {
      key: "risks",
      label: "Risks",
      hint: "What could block or derail the project",
    },
  ],
  requirements: [
    {
      key: "product_boundary",
      label: "Product boundary",
      hint: "Confirm what's in or out of v1",
    },
    {
      key: "users_goals",
      label: "Who it's for & why",
      hint: "Main user types and what they need to accomplish",
    },
    {
      key: "tasks_scenarios",
      label: "User flows",
      hint: "Step-by-step how people use the product",
    },
    {
      key: "failure_paths",
      label: "Errors & recovery",
      hint: "What happens when something goes wrong",
    },
    {
      key: "rules_calculations",
      label: "Business rules",
      hint: "Logic, thresholds, and validation the system must enforce",
    },
    {
      key: "data",
      label: "Data & records",
      hint: "What information is stored and where it comes from",
    },
    {
      key: "external_interfaces",
      label: "Integrations",
      hint: "Other systems, APIs, and data handoffs",
    },
    {
      key: "quality_targets",
      label: "Performance & reliability",
      hint: "Speed, uptime, and scale — numbers if you have them",
    },
    {
      key: "constraints_compliance",
      label: "Compliance & security",
      hint: "Laws, policies, and security requirements",
    },
  ],
};

export function lookupCoverageArea(areaKey: string): CoverageAreaMeta | undefined {
  for (const areas of Object.values(COVERAGE_TEMPLATES)) {
    const hit = areas.find((a) => a.key === areaKey);
    if (hit) return hit;
  }
  return undefined;
}

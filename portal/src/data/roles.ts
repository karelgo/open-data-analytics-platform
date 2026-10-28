// Role metadata: human-readable name, domain, link to handbook.
// Capability data (catalogs/PII/medical) is loaded from
// role-mappings.generated.json (generated from opa-policies-src).

import roleMappings from './role-mappings.generated.json';

export type RoleId =
  | 'claims_analyst'
  | 'fraud_analyst'
  | 'marketing_analyst'
  | 'finance_analyst'
  | 'operations_manager'
  | 'researcher'
  | 'data_steward'
  | 'data_engineer'
  | 'platform_admin';

export interface RoleMeta {
  id: RoleId;
  displayName: string;
  domain: string;
  category: 'business' | 'tech';
  // Portal path to the bundled role handbook (see
  // portal/src/pages/handbooks/[role].astro). Synced by
  // portal/scripts/sync-handbooks.mjs from docs/handbooks/.
  handbookPath: string;
}

export const roles: RoleMeta[] = [
  { id: 'claims_analyst',     displayName: 'Job Market Analyst',     domain: 'Vacancy demand',             category: 'business', handbookPath: 'handbooks/claims_analyst/' },
  { id: 'fraud_analyst',      displayName: 'Source Quality Analyst',      domain: 'Source quality',  category: 'business', handbookPath: 'handbooks/fraud_analyst/' },
  { id: 'marketing_analyst',  displayName: 'Skills Analyst',  domain: 'Skills demand',       category: 'business', handbookPath: 'handbooks/marketing_analyst/' },
  { id: 'finance_analyst',    displayName: 'Salary Analyst',    domain: 'Advertised compensation',            category: 'business', handbookPath: 'handbooks/finance_analyst/' },
  { id: 'operations_manager', displayName: 'Market Operations', domain: 'Daily market coverage',         category: 'business', handbookPath: 'handbooks/operations_manager/' },
  { id: 'researcher',         displayName: 'Labour Market Researcher',         domain: 'Job market research', category: 'business', handbookPath: 'handbooks/researcher/' },
  { id: 'data_steward',       displayName: 'Data Steward',       domain: 'Job market governance',         category: 'tech',     handbookPath: 'handbooks/data_steward/' },
  { id: 'data_engineer',      displayName: 'Data Engineer',      domain: 'Job market pipeline',          category: 'tech',     handbookPath: 'handbooks/data_engineer/' },
  { id: 'platform_admin',     displayName: 'Platform Admin',     domain: 'Platform operations', category: 'tech',     handbookPath: 'handbooks/platform_admin/' },
];

export interface RoleCapability {
  catalogs: string[];
  schemas: string[] | null;
  purposes: string[];
  can_see_pii: boolean;
  can_see_medical: boolean;
  can_see_bankrekening: boolean;
  regio_filter: boolean;
  break_glass: boolean;
  jit_required?: boolean;
  four_eyes_required?: boolean;
  _role_purpose?: string;
}

const rawRoles = (roleMappings as { role_mappings: { roles: Record<string, RoleCapability> } })
  .role_mappings.roles;

export function capabilityFor(role: RoleId): RoleCapability | undefined {
  return rawRoles[role];
}

export function roleById(id: string): RoleMeta | undefined {
  return roles.find((r) => r.id === id);
}

export function isKnownRole(id: string): id is RoleId {
  return roles.some((r) => r.id === id);
}

// Astro Content Collections schema for the certificeringsplatform.
// Eén entry = één module. Eén directory onder content/learn/<rol-id>/ = één track.
//
// We dwingen een schema af zodat alle modules dezelfde structuur hebben en
// MDX-content geen typo's introduceert in fields die de UI gebruikt.

import { defineCollection, z } from 'astro:content';

const roleIds = [
  'claims_analyst',
  'fraud_analyst',
  'marketing_analyst',
  'finance_analyst',
  'operations_manager',
  'researcher',
  'data_steward',
  'data_engineer',
  'platform_admin',
] as const;

const levels = ['foundation', 'practitioner', 'expert'] as const;

const labSchema = z.object({
  title: z.string(),
  hint: z.string().optional(),
  // /go/<service> redirect of externe URL.
  href: z.string(),
  // VS Code: relatief pad in repo. Wordt vertaald naar vscode.dev URL.
  vscodePath: z.string().optional(),
});

const quizQuestionSchema = z.object({
  q: z.string(),
  options: z.array(z.string()).min(2),
  // Index van het correcte antwoord (0-based).
  correct: z.number().int().nonnegative(),
  // Optionele toelichting na invullen.
  explain: z.string().optional(),
});

const checkSchema = z.object({
  // Naam van de auto-check (smoke-test endpoint).
  // Wordt aangeroepen als POST /api/learn/check/<id>; respons {ok:bool, msg:string}.
  id: z.string(),
  title: z.string(),
  hint: z.string().optional(),
});

const learn = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    role: z.enum(roleIds),
    level: z.enum(levels),
    // Volgorde binnen het level (1, 2, 3...). Bepaalt sortering op rol-pagina.
    order: z.number().int().positive(),
    summary: z.string(),
    duration: z.string(), // "20 min", "1 uur"
    prereqs: z.array(z.string()).default([]), // ["claims_analyst/foundation"]
    labs: z.array(labSchema).default([]),
    quiz: z.array(quizQuestionSchema).default([]),
    checks: z.array(checkSchema).default([]),
    // Welk certificaat verleen je bij voltooiing van dit level?
    // Alleen ingevuld on the laatste module van een level.
    certifies: z.boolean().default(false),
  }),
});

// Role handbooks — extended reference documents ("What does your role do?",
// workflows, error messages, escalation). Source of truth is docs/handbooks/
// at the repo root; portal/scripts/sync-handbooks.mjs copies them each build
// into portal/src/content/handbooks/<role-id>.md with frontmatter.
// Rendered by pages/handbooks/[role].astro.
const handbooks = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    role: z.enum(roleIds),
  }),
});

export const collections = { learn, handbooks };
export type RoleId = (typeof roleIds)[number];
export type Level = (typeof levels)[number];

// UC-11 Integrale Klantreis — deck generator
// Dark platform-amber theme matching the portal aesthetic.
const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
pres.author = "UWV Referentie Platform";
pres.title = "UC-11 — Integrale Klantreis";
pres.subject = "Demo-deck voor het Open Data & Analytics Platform";

// ── palette (matches portal CSS) ─────────────────────────────────────
const BG = "14110C";         // near-black with warm tint
const BG_ELEV = "1F1A10";    // card background
const LINE = "2A2417";       // soft border
const LINE_2 = "3D3525";     // stronger border
const INK_1 = "F2EDDD";      // primary text
const INK_2 = "C7BFA9";      // muted text
const INK_3 = "8A8068";      // very muted
const AMBER = "F59E0B";      // platform style accent
const AMBER_SOFT = "FBBF24"; // lighter amber
const RED = "E2675C";        // for deny/warn
const GREEN = "6BB47C";      // for allow/ok

// ── fonts ─────────────────────────────────────────────────────────────
const F_HEAD = "Georgia";
const F_BODY = "Calibri";
const F_MONO = "Consolas";

// ── slide-master / chrome ─────────────────────────────────────────────
const SLIDE_W = 13.3;
const SLIDE_H = 7.5;

function chrome(slide, eyebrow) {
  slide.background = { color: BG };

  // Top hairline
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: SLIDE_W, h: 0.04,
    fill: { color: AMBER }, line: { color: AMBER, width: 0 },
  });

  // Eyebrow + brand line at top
  slide.addText(eyebrow, {
    x: 0.5, y: 0.18, w: 8, h: 0.35,
    fontFace: F_BODY, fontSize: 10, color: AMBER,
    bold: true, charSpacing: 4,
  });
  slide.addText("UWV Referentie Data- en Analyseplatform", {
    x: SLIDE_W - 5.5, y: 0.18, w: 5.0, h: 0.35,
    fontFace: F_BODY, fontSize: 10, color: INK_3,
    align: "right",
  });

  // Footer
  slide.addShape(pres.shapes.LINE, {
    x: 0.5, y: SLIDE_H - 0.35, w: SLIDE_W - 1.0, h: 0,
    line: { color: LINE_2, width: 0.5 },
  });
  slide.addText("UC-11 · Integrale Klantreis · synthetic data · v1", {
    x: 0.5, y: SLIDE_H - 0.3, w: SLIDE_W - 1.0, h: 0.25,
    fontFace: F_BODY, fontSize: 9, color: INK_3,
  });
}

function title(slide, text) {
  slide.addText(text, {
    x: 0.5, y: 0.7, w: SLIDE_W - 1.0, h: 0.9,
    fontFace: F_HEAD, fontSize: 30, color: INK_1, bold: false,
    margin: 0,
  });
}

function subtitle(slide, text) {
  slide.addText(text, {
    x: 0.5, y: 1.55, w: SLIDE_W - 1.0, h: 0.55,
    fontFace: F_BODY, fontSize: 15, color: INK_2,
    italic: true, margin: 0,
  });
}

// ════════════════════════════════════════════════════════════════════
// SLIDE 0 — Title
// ════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: BG };

  // Left amber stripe (motif we'll reuse)
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.4, h: SLIDE_H,
    fill: { color: AMBER }, line: { color: AMBER, width: 0 },
  });

  s.addText("UC-11", {
    x: 1.0, y: 1.4, w: 6.0, h: 0.6,
    fontFace: F_BODY, fontSize: 18, color: AMBER,
    bold: true, charSpacing: 8, margin: 0,
  });

  s.addText("Integrale Klantreis", {
    x: 1.0, y: 2.0, w: 11.0, h: 1.6,
    fontFace: F_HEAD, fontSize: 60, color: INK_1, margin: 0,
  });

  s.addText(
    "Eén synthetische cliënt door alle facetten van het ODAP platform.",
    {
      x: 1.0, y: 3.7, w: 10.5, h: 0.7,
      fontFace: F_HEAD, fontSize: 22, color: INK_2,
      italic: true, margin: 0,
    },
  );

  // Three meta-tags
  const tags = [
    { x: 1.0, label: "event-stream + fase-reconstructie" },
    { x: 5.5, label: "OPA enforces 6 rol-projecties" },
    { x: 9.5, label: "draait op één laptop" },
  ];
  tags.forEach((t) => {
    s.addShape(pres.shapes.RECTANGLE, {
      x: t.x, y: 5.3, w: 0.04, h: 0.5,
      fill: { color: AMBER }, line: { color: AMBER, width: 0 },
    });
    s.addText(t.label, {
      x: t.x + 0.15, y: 5.3, w: 4.0, h: 0.5,
      fontFace: F_BODY, fontSize: 13, color: INK_1, margin: 0,
      valign: "middle",
    });
  });

  s.addText("UWV Referentie Data- en Analyseplatform · synthetic data · v1", {
    x: 1.0, y: SLIDE_H - 0.6, w: 11.0, h: 0.3,
    fontFace: F_BODY, fontSize: 10, color: INK_3, margin: 0,
  });
}

// ════════════════════════════════════════════════════════════════════
// SLIDE 1 — De cliënt (Saskia tijdlijn)
// ════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  chrome(s, "SLIDE 01");
  title(s, "Saskia Bakker — één tijdlijn, alle UWV-domeinen.");
  subtitle(s, "47 jaar · BSN 99999-901 · synthetisch");

  // Timeline horizontal
  const yT = 4.0;
  const stages = [
    { x: 0.7, label: "Werknemer", domain: "polisadm" },
    { x: 2.7, label: "Ziek", domain: "ZW" },
    { x: 4.7, label: "WIA-aanvraag", domain: "WIA" },
    { x: 6.7, label: "WGA toegekend", domain: "WIA" },
    { x: 8.7, label: "Re-integratie", domain: "AG · CRM" },
    { x: 10.7, label: "Werkhervatter", domain: "polisadm" },
  ];

  // Timeline base line — stops at the last dot (x = 10.7).
  s.addShape(pres.shapes.LINE, {
    x: 0.7, y: yT, w: 10.0, h: 0,
    line: { color: AMBER, width: 1.5 },
  });

  stages.forEach((st, i) => {
    // Dot
    s.addShape(pres.shapes.OVAL, {
      x: st.x - 0.12, y: yT - 0.12, w: 0.24, h: 0.24,
      fill: { color: AMBER }, line: { color: BG, width: 1.5 },
    });
    // Label above
    s.addText(st.label, {
      x: st.x - 1.0, y: yT - 1.05, w: 2.0, h: 0.4,
      fontFace: F_HEAD, fontSize: 14, color: INK_1, align: "center",
      bold: true, margin: 0,
    });
    // Domain below
    s.addText(st.domain, {
      x: st.x - 1.0, y: yT + 0.25, w: 2.0, h: 0.35,
      fontFace: F_MONO, fontSize: 10, color: INK_3, align: "center",
      margin: 0,
    });
    // Stage number
    s.addText(`T${i}`, {
      x: st.x - 0.4, y: yT - 0.6, w: 0.8, h: 0.35,
      fontFace: F_BODY, fontSize: 9, color: AMBER, align: "center",
      bold: true, charSpacing: 3, margin: 0,
    });
  });

  // Big takeaway below
  s.addShape(pres.shapes.RECTANGLE, {
    x: 1.0, y: 5.6, w: 11.3, h: 1.2,
    fill: { color: BG_ELEV }, line: { color: LINE, width: 0.5 },
  });
  s.addText(
    "Alle bronnen voor dit verhaal bestaan al in het platform — UC-11 voegt alleen het mart toe dat de tijdlijn reconstrueert.",
    {
      x: 1.3, y: 5.65, w: 10.8, h: 1.1,
      fontFace: F_HEAD, fontSize: 18, color: INK_1,
      italic: true, valign: "middle", margin: 0,
    },
  );
}

// ════════════════════════════════════════════════════════════════════
// SLIDE 2 — Eén tabel, zes waarheden
// ════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  chrome(s, "SLIDE 02");
  title(s, "Eén tabel — zes brillen.");
  subtitle(s, "Dezelfde gold-mart, andere projectie per rol — afgedwongen door OPA at-query-time.");

  // Table data
  const hdr = (t) => ({ text: t, options: {
    bold: true, color: AMBER, fontFace: F_BODY, fontSize: 10,
    fill: { color: BG_ELEV }, valign: "middle", align: "left",
  }});
  const c = (t, opts = {}) => ({ text: t, options: {
    fontFace: F_MONO, fontSize: 9.5, color: INK_1,
    fill: { color: BG_ELEV }, valign: "middle", align: "left", ...opts,
  }});
  const ok = (t) => c(t, { color: GREEN });
  const deny = (t) => c(t, { color: RED, bold: true });
  const mask = (t) => c(t, { color: AMBER_SOFT });

  const tableData = [
    [
      hdr("ROL"),
      hdr("BSN"),
      hdr("event_label"),
      hdr("medisch event"),
      hdr("regio-filter"),
    ],
    [
      c("crm_medewerker"),
      mask("XXXXX + last-4"),
      mask("gesanitized"),
      deny("deny"),
      c("—"),
    ],
    [
      c("wia_beoordelaar"),
      ok("full"),
      ok("full"),
      ok("full"),
      mask("eigen regio"),
    ],
    [
      c("ww_handhaver"),
      ok("full"),
      ok("full"),
      deny("WGA/IVA hidden"),
      c("—"),
    ],
    [
      c("wajong_arb.deskundige"),
      ok("full"),
      ok("full"),
      ok("full"),
      c("—"),
    ],
    [
      c("fez_analist"),
      mask("hashed"),
      mask("aggregated"),
      mask("aggregated"),
      c("—"),
    ],
    [
      c("data_steward"),
      mask("bucket per jaar"),
      mask("sanitized"),
      deny("deny"),
      c("—"),
    ],
  ];

  s.addTable(tableData, {
    x: 0.5, y: 2.3, w: 12.3, h: 3.5,
    colW: [2.6, 2.4, 2.4, 2.8, 2.1],
    border: { type: "solid", pt: 0.5, color: LINE_2 },
    fontFace: F_BODY, fontSize: 10, color: INK_1,
    rowH: [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
    valign: "middle",
  });

  // Bottom callout
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 6.0, w: 0.06, h: 0.95,
    fill: { color: AMBER }, line: { color: AMBER, width: 0 },
  });
  s.addText("Niet via aparte views.", {
    x: 0.75, y: 6.0, w: 8.0, h: 0.4,
    fontFace: F_HEAD, fontSize: 16, color: INK_1, bold: true, margin: 0,
  });
  s.addText(
    "OPA-policy in Rego rewrite't dezelfde query per rol — column-mask + row-filter.",
    {
      x: 0.75, y: 6.4, w: 12.0, h: 0.5,
      fontFace: F_BODY, fontSize: 12, color: INK_2, margin: 0,
    },
  );
}

// ════════════════════════════════════════════════════════════════════
// SLIDE 3 — Dataflow
// ════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  chrome(s, "SLIDE 03");
  title(s, "Van bron tot consumptie.");
  subtitle(s, "Volledig open-source, Kubernetes-native via Stackable.");

  // Pipeline boxes
  const pipeline = [
    { label: "Generators", sub: "synthetic" },
    { label: "NiFi",       sub: "ingest" },
    { label: "Kafka",      sub: "uwv.*.*" },
    { label: "Spark",      sub: "streaming" },
    { label: "Delta",      sub: "lakehouse" },
    { label: "dbt-trino",  sub: "transforms" },
    { label: "Trino",      sub: "query + OPA" },
    { label: "Superset",   sub: "BI · API" },
  ];

  const boxW = 1.32;
  const boxH = 0.95;
  const gap = 0.22;            // larger gap so arrows are visible
  const totalW = pipeline.length * boxW + (pipeline.length - 1) * gap;
  const startX = (SLIDE_W - totalW) / 2;
  const yPipe = 2.7;

  pipeline.forEach((p, i) => {
    const x = startX + i * (boxW + gap);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: yPipe, w: boxW, h: boxH,
      fill: { color: BG_ELEV }, line: { color: LINE_2, width: 0.5 },
    });
    s.addText(p.label, {
      x: x + 0.05, y: yPipe + 0.12, w: boxW - 0.1, h: 0.38,
      fontFace: F_BODY, fontSize: 11, color: INK_1, align: "center",
      bold: true, margin: 0,
    });
    s.addText(p.sub, {
      x: x + 0.05, y: yPipe + 0.5, w: boxW - 0.1, h: 0.38,
      fontFace: F_MONO, fontSize: 8, color: INK_3, align: "center", margin: 0,
    });
    // Arrow between boxes — bigger, properly centered in the gap.
    if (i < pipeline.length - 1) {
      const arrowW = 0.16;
      const arrowH = 0.16;
      const arrowX = x + boxW + (gap - arrowW) / 2;
      s.addShape(pres.shapes.RIGHT_TRIANGLE, {
        x: arrowX, y: yPipe + boxH / 2 - arrowH / 2, w: arrowW, h: arrowH,
        fill: { color: AMBER }, line: { color: AMBER, width: 0 },
        rotate: 90,
      });
    }
  });

  // Cross-cutting layer
  const yCross = 4.5;
  s.addText("Cross-cutting", {
    x: 0.5, y: yCross, w: 2.0, h: 0.3,
    fontFace: F_BODY, fontSize: 9, color: AMBER,
    bold: true, charSpacing: 3, margin: 0,
  });

  const cross = [
    { label: "Keycloak",     sub: "OIDC · rollen" },
    { label: "OPA",          sub: "Rego · row+column" },
    { label: "OpenMetadata", sub: "catalog · lineage · tags" },
    { label: "Vector · OpenSearch", sub: "audit-trail" },
  ];
  const cBoxW = 2.85;
  const cBoxH = 0.85;
  const cGap = 0.18;
  const cTotal = cross.length * cBoxW + (cross.length - 1) * cGap;
  const cStartX = (SLIDE_W - cTotal) / 2;
  const yCrossBoxes = 4.8;

  cross.forEach((c, i) => {
    const x = cStartX + i * (cBoxW + cGap);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: yCrossBoxes, w: cBoxW, h: cBoxH,
      fill: { color: BG_ELEV }, line: { color: AMBER, width: 0.5 },
    });
    s.addText(c.label, {
      x, y: yCrossBoxes + 0.1, w: cBoxW, h: 0.35,
      fontFace: F_BODY, fontSize: 12, color: INK_1, align: "center",
      bold: true, margin: 0,
    });
    s.addText(c.sub, {
      x, y: yCrossBoxes + 0.45, w: cBoxW, h: 0.35,
      fontFace: F_MONO, fontSize: 9, color: INK_3, align: "center", margin: 0,
    });
  });

  // Takeaway
  s.addText(
    "Eén dataflow, vier cross-cutting capabilities. Geen vendor lock-in — alle componenten zijn open-source en Helm-deployable.",
    {
      x: 0.5, y: 6.15, w: 12.3, h: 0.6,
      fontFace: F_HEAD, fontSize: 14, color: INK_2,
      italic: true, align: "center", margin: 0,
    },
  );
}

// ════════════════════════════════════════════════════════════════════
// SLIDE 4 — Medallion + sensitive
// ════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  chrome(s, "SLIDE 04");
  title(s, "Vier zones, vier vertrouwensniveau's.");
  subtitle(s, "Eén MinIO-bucket per zone, één Trino-catalog, eigen OPA-regels.");

  const zones = [
    { name: "bronze",     desc: "Raw Kafka-envelopes.\nIncl. PII zoals ontvangen.", access: "Data-engineers met JIT-grant.", color: "9F6E3A" },
    { name: "silver",     desc: "Geconformeerd.\nPseudonimisering waar passend.",    access: "Analisten + engineers.",        color: "C7BFA9" },
    { name: "gold",       desc: "CGM-conform business products.\nUC-marts.",        access: "Domein-rollen via OPA.",        color: AMBER },
    { name: "sensitive",  desc: "Bijzondere persoonsgegevens.\nArt. 9 AVG · medisch.", access: "4-eyes principe, strikt.",      color: RED },
  ];

  const cardW = 2.85;
  const cardH = 3.5;
  const gap = 0.22;
  const totalW = zones.length * cardW + (zones.length - 1) * gap;
  const startX = (SLIDE_W - totalW) / 2;
  const yCards = 2.5;

  zones.forEach((z, i) => {
    const x = startX + i * (cardW + gap);
    // Card
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: yCards, w: cardW, h: cardH,
      fill: { color: BG_ELEV }, line: { color: LINE_2, width: 0.5 },
    });
    // Left color stripe
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: yCards, w: 0.1, h: cardH,
      fill: { color: z.color }, line: { color: z.color, width: 0 },
    });
    // Zone name
    s.addText(z.name, {
      x: x + 0.3, y: yCards + 0.25, w: cardW - 0.4, h: 0.5,
      fontFace: F_MONO, fontSize: 18, color: z.color, bold: true, margin: 0,
    });
    // Tagline
    s.addText("MinIO bucket · Trino catalog", {
      x: x + 0.3, y: yCards + 0.75, w: cardW - 0.4, h: 0.3,
      fontFace: F_MONO, fontSize: 8.5, color: INK_3, margin: 0,
    });
    // Hairline
    s.addShape(pres.shapes.LINE, {
      x: x + 0.3, y: yCards + 1.15, w: cardW - 0.55, h: 0,
      line: { color: LINE_2, width: 0.5 },
    });
    // Description
    s.addText("Inhoud", {
      x: x + 0.3, y: yCards + 1.3, w: cardW - 0.4, h: 0.3,
      fontFace: F_BODY, fontSize: 8.5, color: AMBER, bold: true,
      charSpacing: 3, margin: 0,
    });
    s.addText(z.desc, {
      x: x + 0.3, y: yCards + 1.6, w: cardW - 0.4, h: 0.85,
      fontFace: F_BODY, fontSize: 11, color: INK_1, margin: 0,
    });
    // Access
    s.addText("Toegang (default)", {
      x: x + 0.3, y: yCards + 2.55, w: cardW - 0.4, h: 0.3,
      fontFace: F_BODY, fontSize: 8.5, color: AMBER, bold: true,
      charSpacing: 3, margin: 0,
    });
    s.addText(z.access, {
      x: x + 0.3, y: yCards + 2.85, w: cardW - 0.4, h: 0.55,
      fontFace: F_BODY, fontSize: 11, color: INK_2, margin: 0,
    });
  });

  // Bottom note
  s.addText(
    "OPA is format-agnostisch — switchen tussen Delta en Iceberg laat de policies onaangetast.",
    {
      x: 0.5, y: 6.5, w: 12.3, h: 0.4,
      fontFace: F_HEAD, fontSize: 13, color: INK_2,
      italic: true, align: "center", margin: 0,
    },
  );
}

// ════════════════════════════════════════════════════════════════════
// SLIDE 5 — dbt-lineage
// ════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  chrome(s, "SLIDE 05");
  title(s, "Zeven bronnen, één tijdlijn.");
  subtitle(s, "Live verkenbaar in dbt docs op het platform.");

  // Left column: 7 staging models
  const staging = [
    "stg_persona",
    "stg_polisadm_ikv",
    "stg_ww_aanvraag",
    "stg_zw_melding",
    "stg_wia_aanvraag",
    "stg_wajong_dossier",
    "stg_crm_contact",
  ];

  const stagX = 0.7;
  const stagW = 3.0;
  const stagH = 0.42;
  const stagGap = 0.08;
  const stagYStart = 2.5;

  staging.forEach((m, i) => {
    const y = stagYStart + i * (stagH + stagGap);
    s.addShape(pres.shapes.RECTANGLE, {
      x: stagX, y, w: stagW, h: stagH,
      fill: { color: BG_ELEV }, line: { color: LINE_2, width: 0.5 },
    });
    s.addText(m, {
      x: stagX + 0.15, y, w: stagW - 0.2, h: stagH,
      fontFace: F_MONO, fontSize: 11.5, color: INK_1, valign: "middle", margin: 0,
    });
    // Connector line to intermediate
    s.addShape(pres.shapes.LINE, {
      x: stagX + stagW, y: y + stagH / 2,
      w: 1.4, h: (4.05 - (y + stagH / 2)),
      line: { color: AMBER, width: 0.75 },
    });
  });

  // Header for staging column
  s.addText("silver.<domain>.stg_*", {
    x: stagX, y: stagYStart - 0.4, w: stagW, h: 0.3,
    fontFace: F_BODY, fontSize: 9, color: AMBER,
    bold: true, charSpacing: 3, margin: 0,
  });

  // Intermediate (middle column)
  const intX = 5.4;
  const intY = 3.8;
  s.addShape(pres.shapes.RECTANGLE, {
    x: intX, y: intY, w: 3.0, h: 0.5,
    fill: { color: BG_ELEV }, line: { color: AMBER, width: 1.2 },
  });
  s.addText("int_klantreis_events", {
    x: intX + 0.15, y: intY, w: 2.7, h: 0.5,
    fontFace: F_MONO, fontSize: 11.5, color: INK_1, valign: "middle",
    bold: true, margin: 0,
  });
  s.addText("UNION ALL", {
    x: intX, y: intY + 0.55, w: 3.0, h: 0.3,
    fontFace: F_MONO, fontSize: 9, color: AMBER_SOFT,
    align: "center", margin: 0,
  });
  s.addText("silver.intermediate", {
    x: intX, y: intY - 0.4, w: 3.0, h: 0.3,
    fontFace: F_BODY, fontSize: 9, color: AMBER,
    bold: true, charSpacing: 3, margin: 0,
  });

  // Marts (right column)
  const martsX = 9.3;
  const martsW = 3.5;
  const martsH = 0.95;
  s.addText("gold.uc11_klantreis", {
    x: martsX, y: stagYStart - 0.4, w: martsW, h: 0.3,
    fontFace: F_BODY, fontSize: 9, color: AMBER,
    bold: true, charSpacing: 3, margin: 0,
  });

  const marts = [
    { name: "mart_uc11_klantreis_events", sub: "één rij per gebeurtenis" },
    { name: "mart_uc11_klantreis_phases", sub: "gaps-and-islands fase-reconstructie" },
  ];
  const martsY0 = 3.0;
  const martsGap = 1.4;
  marts.forEach((m, i) => {
    const y = martsY0 + i * martsGap;
    s.addShape(pres.shapes.RECTANGLE, {
      x: martsX, y, w: martsW, h: martsH,
      fill: { color: BG_ELEV }, line: { color: AMBER, width: 1.2 },
    });
    s.addText(m.name, {
      x: martsX + 0.15, y: y + 0.1, w: martsW - 0.3, h: 0.4,
      fontFace: F_MONO, fontSize: 11, color: INK_1, bold: true, margin: 0,
    });
    s.addText(m.sub, {
      x: martsX + 0.15, y: y + 0.5, w: martsW - 0.3, h: 0.35,
      fontFace: F_BODY, fontSize: 10, color: INK_2, italic: true, margin: 0,
    });
  });

  // Int → events_mart (top right): horizontal line, then small arrow head.
  const eventsCenterY = martsY0 + martsH / 2;
  s.addShape(pres.shapes.LINE, {
    x: intX + 3.0, y: intY + 0.25, w: 0.6, h: eventsCenterY - (intY + 0.25),
    line: { color: AMBER, width: 1 },
  });
  s.addShape(pres.shapes.RIGHT_TRIANGLE, {
    x: martsX - 0.15, y: eventsCenterY - 0.08, w: 0.13, h: 0.16,
    fill: { color: AMBER }, line: { color: AMBER, width: 0 },
    rotate: 90,
  });

  // events_mart → phases_mart (vertical arrow down).
  const phasesCenterY = martsY0 + martsGap + martsH / 2;
  const arrowMidX = martsX + martsW / 2;
  s.addShape(pres.shapes.LINE, {
    x: arrowMidX, y: martsY0 + martsH,
    w: 0, h: martsY0 + martsGap - (martsY0 + martsH),
    line: { color: AMBER, width: 1 },
  });
  s.addShape(pres.shapes.RIGHT_TRIANGLE, {
    x: arrowMidX - 0.08, y: martsY0 + martsGap - 0.16,
    w: 0.16, h: 0.13,
    fill: { color: AMBER }, line: { color: AMBER, width: 0 },
    rotate: 180,
  });

  // Bottom note
  s.addText(
    "Alle bouwstenen bestonden al — UC-11 voegt één intermediate-view en twee marts toe. Geen nieuwe brongegevens.",
    {
      x: 0.5, y: 6.7, w: 12.3, h: 0.4,
      fontFace: F_HEAD, fontSize: 13, color: INK_2,
      italic: true, align: "center", margin: 0,
    },
  );
}

// ════════════════════════════════════════════════════════════════════
// SLIDE 6 — Doelbinding als code
// ════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  chrome(s, "SLIDE 06");
  title(s, "Doelbinding als code.");
  subtitle(s, "Tag in catalog → Rego in OPA → query-rewrite in Trino.");

  // 3-step horizontal flow
  const steps = [
    {
      n: "01",
      label: "OpenMetadata",
      detail: "Kolom event_label krijgt tag\nDoelbinding.Klantcontact.",
    },
    {
      n: "02",
      label: "OPA · Rego",
      detail: "Rule firet als rol geen\ncan_see_medical capability heeft.",
    },
    {
      n: "03",
      label: "Trino",
      detail: "Mask injectie:\nconcat(domein,'.',event_type)",
    },
  ];

  const stepW = 3.7;
  const stepH = 2.5;
  const stepGap = 0.5;
  const stepTotalW = steps.length * stepW + (steps.length - 1) * stepGap;
  const stepStartX = (SLIDE_W - stepTotalW) / 2;
  const stepY = 2.5;

  steps.forEach((st, i) => {
    const x = stepStartX + i * (stepW + stepGap);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: stepY, w: stepW, h: stepH,
      fill: { color: BG_ELEV }, line: { color: LINE_2, width: 0.5 },
    });
    // Step number large
    s.addText(st.n, {
      x: x + 0.2, y: stepY + 0.15, w: 1.2, h: 0.6,
      fontFace: F_HEAD, fontSize: 32, color: AMBER, margin: 0,
    });
    // Label
    s.addText(st.label, {
      x: x + 0.2, y: stepY + 0.85, w: stepW - 0.4, h: 0.45,
      fontFace: F_HEAD, fontSize: 17, color: INK_1, bold: true, margin: 0,
    });
    // Detail
    s.addText(st.detail, {
      x: x + 0.2, y: stepY + 1.4, w: stepW - 0.4, h: 1.0,
      fontFace: F_BODY, fontSize: 11.5, color: INK_2, margin: 0,
    });

    // Arrow between
    if (i < steps.length - 1) {
      const ax = x + stepW + 0.05;
      s.addShape(pres.shapes.RIGHT_TRIANGLE, {
        x: ax, y: stepY + stepH / 2 - 0.12, w: 0.18, h: 0.25,
        fill: { color: AMBER }, line: { color: AMBER, width: 0 },
        rotate: 90,
      });
    }
  });

  // Result panel
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 5.3, w: 12.3, h: 1.5,
    fill: { color: BG_ELEV }, line: { color: AMBER, width: 0.5 },
  });
  s.addText("RESULTAAT", {
    x: 0.7, y: 5.4, w: 5.0, h: 0.3,
    fontFace: F_BODY, fontSize: 9, color: AMBER,
    bold: true, charSpacing: 3, margin: 0,
  });
  s.addText(
    "Eén query — verschillende projecties per rol. crm_medewerker ziet géén diagnose, wia_beoordelaar zonder beperking. Geen aparte views, geen extra applicatie-code, geen vergeten checks.",
    {
      x: 0.7, y: 5.7, w: 11.9, h: 1.1,
      fontFace: F_HEAD, fontSize: 14, color: INK_1,
      italic: true, margin: 0,
    },
  );
}

// ════════════════════════════════════════════════════════════════════
// SLIDE 7 — AI minimaal
// ════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  chrome(s, "SLIDE 07");
  title(s, "AI minimaal — bewust.");
  subtitle(s, "Het AI-pad laten zien zonder hoog-risico te bouwen.");

  // Left: AI Act classification card
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 2.5, w: 6.0, h: 4.0,
    fill: { color: BG_ELEV }, line: { color: LINE_2, width: 0.5 },
  });
  s.addText("AI ACT-CLASSIFICATIE", {
    x: 0.75, y: 2.7, w: 5.5, h: 0.35,
    fontFace: F_BODY, fontSize: 10, color: AMBER,
    bold: true, charSpacing: 3, margin: 0,
  });
  s.addText("Laag risico", {
    x: 0.75, y: 3.05, w: 5.5, h: 0.8,
    fontFace: F_HEAD, fontSize: 36, color: GREEN, bold: true, margin: 0,
  });

  const features = [
    "Beslismodel, geen ML",
    "Human-in-the-loop verplicht",
    "Algoritmeregister-stub aanwezig",
    "MRM-classificatie: laag",
    "Geen direct impact op individu",
  ];
  features.forEach((f, i) => {
    const y = 4.0 + i * 0.45;
    s.addShape(pres.shapes.OVAL, {
      x: 0.85, y: y + 0.13, w: 0.13, h: 0.13,
      fill: { color: AMBER }, line: { color: AMBER, width: 0 },
    });
    s.addText(f, {
      x: 1.15, y, w: 5.2, h: 0.4,
      fontFace: F_BODY, fontSize: 13, color: INK_1, valign: "middle", margin: 0,
    });
  });

  // Right: Use-case card
  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.8, y: 2.5, w: 6.0, h: 4.0,
    fill: { color: BG_ELEV }, line: { color: LINE_2, width: 0.5 },
  });
  s.addText("USE CASE", {
    x: 7.05, y: 2.7, w: 5.5, h: 0.35,
    fontFace: F_BODY, fontSize: 10, color: AMBER,
    bold: true, charSpacing: 3, margin: 0,
  });
  s.addText("Next best contact", {
    x: 7.05, y: 3.05, w: 5.5, h: 0.6,
    fontFace: F_HEAD, fontSize: 26, color: INK_1, bold: true, margin: 0,
  });
  s.addText(
    "Gegeven de huidige fase van een cliënt, welk klantcontact past het beste?",
    {
      x: 7.05, y: 3.7, w: 5.5, h: 0.6,
      fontFace: F_HEAD, fontSize: 14, color: INK_2,
      italic: true, margin: 0,
    },
  );
  s.addText(
    "Voorbeeld: cliënt in fase 'wia_in_behandeling' > 30 dagen → suggesteer telefonisch update-contact.",
    {
      x: 7.05, y: 4.5, w: 5.5, h: 0.7,
      fontFace: F_BODY, fontSize: 12, color: INK_2, margin: 0,
    },
  );
  s.addText(
    "Suggestie. Beslissing blijft bij de medewerker.",
    {
      x: 7.05, y: 5.8, w: 5.5, h: 0.4,
      fontFace: F_BODY, fontSize: 12, color: AMBER, bold: true, margin: 0,
    },
  );
}

// ════════════════════════════════════════════════════════════════════
// SLIDE 8 — Audit demo (glass box)
// ════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  chrome(s, "SLIDE 08");
  title(s, "Glass-box: elke read is herleidbaar.");
  subtitle(s, "Verboden query → OPA deny → audit-dashboard in 30 seconden.");

  // 4-step timeline horizontal with icons (use shapes/text)
  const steps = [
    { t: "T+0s · query",  label: "Query", detail: "crm_medewerker vraagt\narbeidsongeschikt_pct op", color: INK_1 },
    { t: "T+0s · deny",   label: "OPA deny", detail: "Geen can_see_medical\n→ allow=false", color: RED },
    { t: "T+5s",          label: "Audit-emit", detail: "Trino event-listener\n→ Kafka audit-topic", color: AMBER },
    { t: "T+30s",         label: "Dashboard", detail: "Vector → OpenSearch\nopzoekbaar per user/rol/BSN", color: GREEN },
  ];

  const sw = 2.85;
  const sh = 2.1;
  const sg = 0.4;
  const tw = steps.length * sw + (steps.length - 1) * sg;
  const sx0 = (SLIDE_W - tw) / 2;
  const sy = 2.7;

  steps.forEach((st, i) => {
    const x = sx0 + i * (sw + sg);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: sy, w: sw, h: sh,
      fill: { color: BG_ELEV }, line: { color: LINE_2, width: 0.5 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: sy, w: 0.08, h: sh,
      fill: { color: st.color }, line: { color: st.color, width: 0 },
    });
    s.addText(st.t, {
      x: x + 0.25, y: sy + 0.15, w: 1.5, h: 0.3,
      fontFace: F_MONO, fontSize: 10, color: st.color, bold: true, margin: 0,
    });
    s.addText(st.label, {
      x: x + 0.25, y: sy + 0.5, w: sw - 0.4, h: 0.45,
      fontFace: F_HEAD, fontSize: 16, color: INK_1, bold: true, margin: 0,
    });
    s.addText(st.detail, {
      x: x + 0.25, y: sy + 1.05, w: sw - 0.4, h: 1.0,
      fontFace: F_BODY, fontSize: 11, color: INK_2, margin: 0,
    });
    if (i < steps.length - 1) {
      s.addShape(pres.shapes.RIGHT_TRIANGLE, {
        x: x + sw + 0.06, y: sy + sh / 2 - 0.1, w: 0.16, h: 0.22,
        fill: { color: AMBER }, line: { color: AMBER, width: 0 },
        rotate: 90,
      });
    }
  });

  // Bottom retention note
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 5.4, w: 12.3, h: 1.3,
    fill: { color: BG_ELEV }, line: { color: AMBER, width: 0.5 },
  });
  s.addText("AUDIT-TRAIL", {
    x: 0.75, y: 5.55, w: 5.0, h: 0.3,
    fontFace: F_BODY, fontSize: 9, color: AMBER,
    bold: true, charSpacing: 3, margin: 0,
  });
  s.addText("user · rol · doelcode · queried-BSN · timestamp · applied-mask", {
    x: 0.75, y: 5.85, w: 11.9, h: 0.4,
    fontFace: F_MONO, fontSize: 12, color: INK_1, margin: 0,
  });
  s.addText("Retention 7 jaar in Delta-formaat onder bronze.audit.klantreis_reads.", {
    x: 0.75, y: 6.25, w: 11.9, h: 0.4,
    fontFace: F_BODY, fontSize: 11, color: INK_2, italic: true, margin: 0,
  });
}

// ════════════════════════════════════════════════════════════════════
// SLIDE 9 — Self-service access-request
// ════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  chrome(s, "SLIDE 09");
  title(s, "Self-service toegang — zonder ticket, zonder shell.");
  subtitle(s, "Nieuwe verzekeringsarts wil toegang tot gold.uc11_klantreis.");

  const flow = [
    {
      role: "1 — Arts",
      action: "Vraagt aan",
      detail: "Klikt 'Request Access' op de\ntabel in OpenMetadata-UI.\nVult doel + aanleiding in.",
    },
    {
      role: "2 — Data-steward",
      action: "Keurt goed",
      detail: "Inbox-task. Reviewt doel.\nKnop 'Approve' → OM emit\nTaskResolved-event.",
    },
    {
      role: "3 — OM-access-bridge",
      action: "Realm-role",
      detail: "Service consumeert webhook.\nZet realm-role\ndata_access:gold.uc11_klantreis.",
    },
    {
      role: "4 — Arts",
      action: "Heeft toegang",
      detail: "Volgende login: token bevat\nrole. OPA-policy enforce't.\nGeen handmatige stap meer.",
    },
  ];

  const cw = 2.85;
  const ch = 3.6;
  const cg = 0.3;
  const ctw = flow.length * cw + (flow.length - 1) * cg;
  const cx0 = (SLIDE_W - ctw) / 2;
  const cy = 2.5;

  flow.forEach((f, i) => {
    const x = cx0 + i * (cw + cg);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: cy, w: cw, h: ch,
      fill: { color: BG_ELEV }, line: { color: LINE_2, width: 0.5 },
    });
    s.addText(f.role, {
      x: x + 0.25, y: cy + 0.2, w: cw - 0.4, h: 0.3,
      fontFace: F_BODY, fontSize: 10, color: AMBER,
      bold: true, charSpacing: 3, margin: 0,
    });
    s.addText(f.action, {
      x: x + 0.25, y: cy + 0.55, w: cw - 0.4, h: 0.7,
      fontFace: F_HEAD, fontSize: 22, color: INK_1, bold: true, margin: 0,
    });
    s.addShape(pres.shapes.LINE, {
      x: x + 0.25, y: cy + 1.45, w: cw - 0.5, h: 0,
      line: { color: LINE_2, width: 0.5 },
    });
    s.addText(f.detail, {
      x: x + 0.25, y: cy + 1.65, w: cw - 0.4, h: 1.7,
      fontFace: F_BODY, fontSize: 11.5, color: INK_2, margin: 0,
    });

    if (i < flow.length - 1) {
      // Arrow sits in the top portion of the card-gap, above the divider line.
      s.addShape(pres.shapes.RIGHT_TRIANGLE, {
        x: x + cw + (cg - 0.18) / 2,
        y: cy + 0.65, w: 0.18, h: 0.22,
        fill: { color: AMBER }, line: { color: AMBER, width: 0 },
        rotate: 90,
      });
    }
  });

  // Bottom takeaway
  s.addText(
    "Zelfde flow voor élke gold-tabel. ADR-0008 · platform/18-om-access-bridge.",
    {
      x: 0.5, y: 6.5, w: 12.3, h: 0.4,
      fontFace: F_HEAD, fontSize: 13, color: INK_2,
      italic: true, align: "center", margin: 0,
    },
  );
}

// ════════════════════════════════════════════════════════════════════
// SLIDE 10 — Wat dit kost
// ════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  chrome(s, "SLIDE 10");
  title(s, "Wat dit kost.");
  subtitle(s, "Eén laptop, één commando — productie is dezelfde Helm.");

  // 3 big stat callouts
  const stats = [
    { big: "€0", label: "cloud-bill", sub: "k3d in Docker · alles lokaal" },
    { big: "1", label: "commando voor deploy", sub: "make cluster + bootstrap + deploy + seed" },
    { big: "0", label: "vendor lock-in", sub: "alle componenten Apache-2 / open-source" },
  ];

  const stW = 4.0;
  const stH = 2.7;
  const stG = 0.3;
  const stTot = stats.length * stW + (stats.length - 1) * stG;
  const stX0 = (SLIDE_W - stTot) / 2;
  const stY = 2.5;

  stats.forEach((stat, i) => {
    const x = stX0 + i * (stW + stG);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: stY, w: stW, h: stH,
      fill: { color: BG_ELEV }, line: { color: LINE_2, width: 0.5 },
    });
    s.addText(stat.big, {
      x, y: stY + 0.3, w: stW, h: 1.4,
      fontFace: F_HEAD, fontSize: 80, color: AMBER,
      align: "center", margin: 0,
    });
    s.addText(stat.label, {
      x, y: stY + 1.75, w: stW, h: 0.45,
      fontFace: F_HEAD, fontSize: 17, color: INK_1,
      align: "center", bold: true, margin: 0,
    });
    s.addText(stat.sub, {
      x: x + 0.2, y: stY + 2.2, w: stW - 0.4, h: 0.4,
      fontFace: F_BODY, fontSize: 11, color: INK_3,
      align: "center", italic: true, margin: 0,
    });
  });

  // Command panel
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 5.6, w: 12.3, h: 1.1,
    fill: { color: BG_ELEV }, line: { color: AMBER, width: 0.5 },
  });
  s.addText("Update dbt-docs op het platform:", {
    x: 0.75, y: 5.7, w: 6.0, h: 0.35,
    fontFace: F_BODY, fontSize: 11, color: INK_2, margin: 0,
  });
  s.addText("$ make portal-publish-dbt-docs", {
    x: 0.75, y: 6.05, w: 11.9, h: 0.55,
    fontFace: F_MONO, fontSize: 18, color: AMBER, margin: 0,
  });
}

// ════════════════════════════════════════════════════════════════════
// SLIDE 11 — Closing — bookend-style (matches title slide's amber stripe)
// ════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: BG };

  // Left amber stripe (mirror title slide)
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.4, h: SLIDE_H,
    fill: { color: AMBER }, line: { color: AMBER, width: 0 },
  });

  s.addText("EINDE", {
    x: 1.0, y: 1.0, w: 11.0, h: 0.4,
    fontFace: F_BODY, fontSize: 14, color: AMBER,
    bold: true, charSpacing: 6, margin: 0,
  });

  s.addText("Vragen?", {
    x: 1.0, y: 1.45, w: 11.0, h: 1.5,
    fontFace: F_HEAD, fontSize: 72, color: INK_1, margin: 0,
  });

  s.addText("Verder lezen", {
    x: 1.0, y: 3.5, w: 11.0, h: 0.45,
    fontFace: F_BODY, fontSize: 10, color: AMBER,
    bold: true, charSpacing: 4, margin: 0,
  });

  const links = [
    {
      label: "UC-spec",
      path: "docs/use-cases/uc11-klantreis.md",
    },
    {
      label: "Demo-tour (walkthrough)",
      path: "docs/use-cases/uc11-klantreis-walkthrough.md",
    },
    {
      label: "Live lineage",
      path: "https://platform.odap.local:8443/dbt-docs.html",
    },
    {
      label: "Architectuur",
      path: "https://platform.odap.local:8443/architecture",
    },
  ];
  links.forEach((l, i) => {
    const y = 4.05 + i * 0.55;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 1.0, y: y + 0.1, w: 0.04, h: 0.3,
      fill: { color: AMBER }, line: { color: AMBER, width: 0 },
    });
    s.addText(l.label, {
      x: 1.2, y, w: 4.5, h: 0.5,
      fontFace: F_HEAD, fontSize: 14, color: INK_1, valign: "middle",
      bold: true, margin: 0,
    });
    s.addText(l.path, {
      x: 5.7, y, w: 7.5, h: 0.5,
      fontFace: F_MONO, fontSize: 11, color: INK_2, valign: "middle", margin: 0,
    });
  });

  s.addText("UC-11 · Integrale Klantreis · synthetic data · v1", {
    x: 1.0, y: SLIDE_H - 0.6, w: 11.0, h: 0.3,
    fontFace: F_BODY, fontSize: 10, color: INK_3, margin: 0,
  });
}

const OUT = "/Users/karelgoense/Documents/programming/UWV/UDP_Stackable/docs/use-cases/uc11-klantreis-deck.pptx";
pres.writeFile({ fileName: OUT })
  .then((f) => console.log(`[uc11-deck] ${f}`))
  .catch((e) => { console.error(e); process.exit(1); });

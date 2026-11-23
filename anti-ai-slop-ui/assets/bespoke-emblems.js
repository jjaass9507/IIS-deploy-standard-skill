/**
 * 16 Hand-Crafted 48x48 Multi-Layer Duotone & Isometric SVG Emblems
 * Extracted from Platform Hub (Editorial Chapter Spread & Ceramic Glaze Craft System).
 *
 * Each emblem follows the 4-layer architecture:
 *   Layer 1: Base plate (fill-opacity 0.10-0.14 + crisp outer stroke)
 *   Layer 2: Mid-tone facet (fill-opacity 0.20-0.30)
 *   Layer 3: Precision engineering linework (stroke-linecap="round")
 *   Layer 4: Complementary signal node (.svg-signal bound to --emblem-signal)
 *
 * Pair with CSS:
 *   .svg-signal { fill: var(--emblem-signal, var(--cinnabar, #d14828)); }
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.BESPOKE_SVGS = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  return {
    // 1. Silicon Wafer & PLC Circuit (Manufacturing / MES)
    cpu: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <rect x="8" y="8" width="32" height="32" rx="6" fill="currentColor" fill-opacity="0.12" stroke="currentColor" stroke-width="1.8"/>
        <path d="M16 16H32V32H16V16Z" fill="currentColor" fill-opacity="0.24" stroke="currentColor" stroke-width="1.8"/>
        <path d="M15 4V8M24 4V8M33 4V8M15 40V44M24 40V44M33 40V44M4 15H8M4 24H8M4 33H8M40 15H44M40 24H44M40 33H44" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        <path d="M20 24H28M24 20V28" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
        <circle cx="24" cy="24" r="3.2" class="svg-signal"/>
        <circle cx="13" cy="13" r="1.5" fill="currentColor"/>
        <circle cx="35" cy="35" r="1.5" fill="currentColor"/>
      </svg>`,

    // 2. Isometric Stacked Ledger Planes (ERP & Finance)
    layers: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <path d="M24 27L42 35L24 43L6 35L24 27Z" fill="currentColor" fill-opacity="0.14" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
        <path d="M24 16L42 24L24 32L6 24L24 16Z" fill="currentColor" fill-opacity="0.26" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
        <path d="M24 5L42 13L24 21L6 13L24 5Z" fill="currentColor" fill-opacity="0.1" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/>
        <path d="M24 13V35" stroke="currentColor" stroke-width="1.4" stroke-dasharray="2 2"/>
        <circle cx="24" cy="13" r="3" class="svg-signal"/>
      </svg>`,

    // 3. Neural Octahedron Prism (AI & Data Intelligence)
    sparkles: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <polygon points="24,4 42,24 24,44 6,24" fill="currentColor" fill-opacity="0.11" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
        <polygon points="24,4 42,24 24,29" fill="currentColor" fill-opacity="0.25"/>
        <path d="M24 4V44M6 24H42" stroke="currentColor" stroke-width="1.3" stroke-opacity="0.5"/>
        <path d="M24 14L27 21L34 24L27 27L24 34L21 27L14 24L21 21L24 14Z" fill="currentColor" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
        <circle cx="24" cy="24" r="3" class="svg-signal"/>
        <circle cx="37" cy="11" r="2.2" class="svg-signal"/>
      </svg>`,

    // 4. Overlapping Identity Badges & Org Nodes (HR & Workflow)
    users: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <rect x="6" y="10" width="22" height="28" rx="4" fill="currentColor" fill-opacity="0.12" stroke="currentColor" stroke-width="1.7"/>
        <rect x="18" y="10" width="24" height="28" rx="4" fill="currentColor" fill-opacity="0.22" stroke="currentColor" stroke-width="1.8"/>
        <circle cx="30" cy="20" r="4.5" fill="currentColor" fill-opacity="0.3" stroke="currentColor" stroke-width="1.7"/>
        <path d="M22 33C22 29.134 25.582 26 30 26C34.418 26 38 29.134 38 33" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        <circle cx="14" cy="20" r="3" stroke="currentColor" stroke-width="1.5"/>
        <path d="M10 31C10 28.2 11.8 26 14.5 26" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="37" cy="14" r="2.5" class="svg-signal"/>
      </svg>`,

    // 5. Architectural Console & Command Prompt (IIS Deploy & DevOps)
    terminal: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <rect x="5" y="8" width="38" height="32" rx="5" fill="currentColor" fill-opacity="0.11" stroke="currentColor" stroke-width="1.8"/>
        <path d="M5 16H43" stroke="currentColor" stroke-width="1.6"/>
        <rect x="9" y="21" width="30" height="14" rx="2" fill="currentColor" fill-opacity="0.2"/>
        <circle cx="10" cy="12" r="1.5" class="svg-signal"/>
        <circle cx="15" cy="12" r="1.5" fill="currentColor" fill-opacity="0.5"/>
        <circle cx="20" cy="12" r="1.5" fill="currentColor" fill-opacity="0.5"/>
        <path d="M13 25L18 28.5L13 32" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <rect x="22" y="27" width="8" height="3" rx="1" class="svg-signal"/>
      </svg>`,

    // 6. Open Technical Codex & Bookmark Ribbon (ISO Docs & SOP)
    book: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <path d="M24 11C19 8.5 12 8.5 7 10.5V37.5C12 35.5 19 35.5 24 38C29 35.5 36 35.5 41 37.5V10.5C36 8.5 29 8.5 24 11Z" fill="currentColor" fill-opacity="0.13" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
        <path d="M24 11V38" stroke="currentColor" stroke-width="1.8"/>
        <path d="M24 11C29 8.5 36 8.5 41 10.5V37.5C36 35.5 29 35.5 24 38V11Z" fill="currentColor" fill-opacity="0.22"/>
        <path d="M31 9.5V23L34.5 20.5L38 23V10" class="svg-signal" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
        <path d="M11 17H19M11 22H19M11 27H17" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
      </svg>`,

    // 7. Telemetry Waveform & Coordinate Bars (Power Bill & BI Analytics)
    chart: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <rect x="6" y="6" width="36" height="36" rx="5" fill="currentColor" fill-opacity="0.1" stroke="currentColor" stroke-width="1.7"/>
        <rect x="12" y="26" width="5" height="10" rx="1" fill="currentColor" fill-opacity="0.3" stroke="currentColor" stroke-width="1.5"/>
        <rect x="21.5" y="20" width="5" height="16" rx="1" fill="currentColor" fill-opacity="0.45" stroke="currentColor" stroke-width="1.5"/>
        <rect x="31" y="15" width="5" height="21" rx="1" fill="currentColor" fill-opacity="0.22" stroke="currentColor" stroke-width="1.5"/>
        <path d="M12 20L21 14L29 17L37 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="37" cy="10" r="3" class="svg-signal"/>
      </svg>`,

    // 8. Cylindrical Platter Vault (Database Audit)
    database: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <ellipse cx="24" cy="11" rx="15" ry="5.5" fill="currentColor" fill-opacity="0.28" stroke="currentColor" stroke-width="1.8"/>
        <path d="M9 11V24C9 27.04 15.72 29.5 24 29.5C32.28 29.5 39 27.04 39 24V11" fill="currentColor" fill-opacity="0.12" stroke="currentColor" stroke-width="1.8"/>
        <path d="M9 24V37C9 40.04 15.72 42.5 24 42.5C32.28 42.5 39 40.04 39 37V24" fill="currentColor" fill-opacity="0.18" stroke="currentColor" stroke-width="1.8"/>
        <path d="M9 17.5C9 20.54 15.72 23 24 23C32.28 23 39 20.54 39 17.5" stroke="currentColor" stroke-width="1.5"/>
        <circle cx="33" cy="25" r="2" class="svg-signal"/>
        <circle cx="33" cy="36" r="2" class="svg-signal"/>
      </svg>`,

    // 9. Industrial Substation & Energy Pulse (Facility Monitoring)
    bolt: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <polygon points="24,4 41,14 41,34 24,44 7,34 7,14" fill="currentColor" fill-opacity="0.12" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
        <circle cx="24" cy="24" r="12" fill="currentColor" fill-opacity="0.2" stroke="currentColor" stroke-width="1.4" stroke-dasharray="3 2"/>
        <path d="M26 11L15 25H24L22 37L33 23H24L26 11Z" fill="currentColor" fill-opacity="0.35" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
        <circle cx="24" cy="24" r="2.8" class="svg-signal"/>
      </svg>`,

    // 10. Precision Engineering Gear & Caliper (Equipment PM Maintenance)
    wrench: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <circle cx="24" cy="24" r="14" fill="currentColor" fill-opacity="0.14" stroke="currentColor" stroke-width="1.8"/>
        <circle cx="24" cy="24" r="7" fill="currentColor" fill-opacity="0.28" stroke="currentColor" stroke-width="1.8"/>
        <path d="M24 5V10M24 38V43M5 24H10M38 24H43M10.5 10.5L14 14M34 34L37.5 37.5M37.5 10.5L34 14M14 34L10.5 37.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>
        <circle cx="24" cy="24" r="2.8" class="svg-signal"/>
      </svg>`,

    // 11. Stamped Approval Dossier (BPM Electronic Sign-off & Asset Audit)
    "file-check": `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <path d="M10 6H29L38 15V42H10V6Z" fill="currentColor" fill-opacity="0.12" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
        <path d="M29 6V15H38" fill="currentColor" fill-opacity="0.26" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
        <circle cx="24" cy="28" r="8" fill="currentColor" fill-opacity="0.22" stroke="currentColor" stroke-width="1.6"/>
        <path d="M20.5 28L23 30.5L28 25.5" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M15 14H24" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>
        <circle cx="33" cy="37" r="2.6" class="svg-signal"/>
      </svg>`,

    // 12. Faceted Aegis Crest (IT Service Desk & Security Access)
    shield: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <path d="M24 5L39 11V23C39 33.2 32.5 40.5 24 44C15.5 40.5 9 33.2 9 23V11L24 5Z" fill="currentColor" fill-opacity="0.12" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
        <path d="M24 5L39 11V23C39 33.2 32.5 40.5 24 44V5Z" fill="currentColor" fill-opacity="0.22"/>
        <circle cx="24" cy="22" r="4" class="svg-signal"/>
        <path d="M24 26V33" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
      </svg>`,

    // 13. Dual Blade Server Cluster (Host & Background Services)
    server: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <rect x="7" y="8" width="34" height="13" rx="3" fill="currentColor" fill-opacity="0.14" stroke="currentColor" stroke-width="1.8"/>
        <rect x="7" y="27" width="34" height="13" rx="3" fill="currentColor" fill-opacity="0.24" stroke="currentColor" stroke-width="1.8"/>
        <path d="M14 21V27M34 21V27" stroke="currentColor" stroke-width="1.8"/>
        <circle cx="13" cy="14.5" r="2.2" class="svg-signal"/>
        <circle cx="13" cy="33.5" r="2.2" class="svg-signal"/>
        <path d="M22 14.5H35M22 33.5H35" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
      </svg>`,

    // 14. Orbital Mesh Sphere (External Cloud & Network Topology)
    globe: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <circle cx="24" cy="24" r="16" fill="currentColor" fill-opacity="0.12" stroke="currentColor" stroke-width="1.8"/>
        <ellipse cx="24" cy="24" rx="8" ry="16" fill="currentColor" fill-opacity="0.2" stroke="currentColor" stroke-width="1.6"/>
        <path d="M8.5 19H39.5M8.5 29H39.5" stroke="currentColor" stroke-width="1.5"/>
        <circle cx="32" cy="19" r="2.8" class="svg-signal"/>
        <circle cx="16" cy="29" r="2.4" fill="currentColor"/>
      </svg>`,

    // 15. Precision Sweep Chronometer (Scheduled Jobs & Attendance)
    clock: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <circle cx="24" cy="24" r="17" fill="currentColor" fill-opacity="0.12" stroke="currentColor" stroke-width="1.8"/>
        <path d="M24 24V10A14 14 0 0 1 36.12 31L24 24Z" fill="currentColor" fill-opacity="0.28"/>
        <path d="M24 12V24L32 29" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="24" cy="24" r="3" class="svg-signal"/>
      </svg>`,

    // 16. Isometric Dispatch Envelope (Notifications & Alerts)
    mail: `
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <rect x="6" y="12" width="36" height="26" rx="4" fill="currentColor" fill-opacity="0.13" stroke="currentColor" stroke-width="1.8"/>
        <path d="M7 14L24 26L41 14" fill="currentColor" fill-opacity="0.22" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
        <circle cx="38" cy="12" r="4" class="svg-signal"/>
      </svg>`
  };
});

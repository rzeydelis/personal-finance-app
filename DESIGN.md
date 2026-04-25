# Design System - Pluto Finance

## Product Context
- **What this is:** Pluto Finance is a local-first personal finance web app that ingests CSV or Plaid transaction data and turns it into actionable spending insights, monthly summaries, and question answering.
- **Who it's for:** Individual users who want fast clarity on spending habits without sending raw financial history to third-party SaaS dashboards.
- **Space/industry:** Consumer fintech, personal analytics, local AI-assisted decision support.
- **Project type:** Web app dashboard with analysis workflows.

## Aesthetic Direction
- **Direction:** Operational calm.
- **Decoration level:** Intentional.
- **Mood:** Feels like a focused command center, not a marketing landing page. High information density with quiet confidence and clear visual hierarchy.
- **Reference sites:** https://mercury.com, https://www.ramp.com, https://linear.app

## Typography
- **Display/Hero:** General Sans - geometric and modern, gives headlines authority without feeling ornamental.
- **Body:** Instrument Sans - highly readable at small UI sizes and conversational enough for long-form insight copy.
- **UI/Labels:** Instrument Sans (same as body) with tighter tracking for controls.
- **Data/Tables:** IBM Plex Mono - reliable tabular numerals and strong scanability for amounts and dates.
- **Code:** JetBrains Mono.
- **Loading:** `https://api.fontshare.com/v2/css?f[]=general-sans@400,500,600,700&display=swap` and `https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=JetBrains+Mono:wght@400;600&display=swap`
- **Scale:** 12px (`0.75rem`) label micro, 14px (`0.875rem`) body-sm, 16px (`1rem`) body, 20px (`1.25rem`) section title, 28px (`1.75rem`) page title, 40px (`2.5rem`) hero.

## Color
- **Approach:** Balanced, dark-first with equal light-mode tokens.
- **Primary:** `#0F8BFF` - primary actions, active navigation, focused controls.
- **Secondary:** `#10B981` - positive outcomes, savings, success states.
- **Neutrals:** Cool slate ramp from `#F5F7FA` to `#0B1014` (`#F5F7FA`, `#DDE4EC`, `#A3B1C2`, `#6A7A8C`, `#2A3440`, `#121920`, `#0B1014`).
- **Semantic:** success `#10B981`, warning `#F59E0B`, error `#E11D48`, info `#0EA5E9`.
- **Dark mode:** Keep surfaces layered (`bg`, `card`, `elevated`), reduce saturated accents by ~15% on large fills, and reserve full saturation for interactive states.

## Spacing
- **Base unit:** 4px.
- **Density:** Comfortable.
- **Scale:** 2xs(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(48) 3xl(64)

## Layout
- **Approach:** Hybrid (grid-disciplined data surfaces with editorial hero blocks for insight storytelling).
- **Grid:** Mobile 4 columns, tablet 8 columns, desktop 12 columns.
- **Max content width:** 1200px for analysis pages, 960px for focused setup flows.
- **Border radius:** xs 6px, sm 10px, md 14px, lg 20px, pill 9999px.

## Motion
- **Approach:** Intentional.
- **Easing:** enter `cubic-bezier(0.16, 1, 0.3, 1)`, exit `cubic-bezier(0.7, 0, 0.84, 0)`, move `cubic-bezier(0.45, 0, 0.2, 1)`.
- **Duration:** micro(80ms) short(180ms) medium(280ms) long(500ms).

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-25 | Established initial Pluto Finance design system | Consolidates the current multi-template UI into one coherent token set and typography hierarchy. |
| 2026-04-25 | Selected General Sans + Instrument Sans + IBM Plex Mono | Improves visual character while preserving readability in dense financial tables and metrics. |
| 2026-04-25 | Standardized accent strategy around blue + emerald | Replaces per-page accent drift and maps color directly to action and outcome semantics. |

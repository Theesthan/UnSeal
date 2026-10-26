---
name: accessibility
description: Use before any PR that touches apps/web UI. Audits against WCAG 2.1 AA with axe-core, eslint-plugin-jsx-a11y and a manual checklist, including lang attributes and readable sizes for Tamil and Hindi text.
---

# Accessibility (WCAG 2.1 AA)

Target: **WCAG 2.1 AA** for the web app. India's GIGW guidelines for government websites reference WCAG, but UnSeal is not a government site and this skill makes no legal claim. It is the quality bar for a public civic tool that citizens use on phones, often with large-text or screen-reader settings.

## Automated (add when the web app exists)
No code exists yet, so none of this is installed. The first PR that adds UI should add:
- `@axe-core/playwright`, run with Playwright on every page and flow touched, in en, hi and ta. Zero serious or critical violations.
- `eslint-plugin-jsx-a11y` (recommended rules) in the web lint step (`npm run lint`). Fix findings; never disable a rule to pass.
- Optional: a Lighthouse accessibility score as a trend signal, not a gate.

Until those exist, write "not yet automated" in the PR, never "passed".

## Tamil and Hindi content
- `<html lang>` follows the UI language (`en`, `hi`, `ta`). Wrap any run in another language in its own `lang` element: a Tamil question inside an English page, or the original and translated text shown side by side when the translation fallback is used.
- Label language-switcher options in their own script ("தமிழ்", "हिन्दी", "English") with the matching `lang`, so screen readers pronounce them correctly.
- Body text at least 16px (`1rem`), never below 14px for anything a user must read. Size in `rem` so browser text scaling works. Use `leading-relaxed` for Indic body text.
- No letter-spacing (`tracking-*`) on Tamil or Devanagari; it can break conjunct shaping.
- Do not rely on a Tamil or Hindi screen-reader voice being installed. Keep headings, labels and structure meaningful even when speech falls back.

## Manual checklist (per UI change)
- **Keyboard:** every control reachable and operable, logical focus order, visible focus ring, dialogs trap and restore focus, no keyboard trap.
- **Screen reader:** every input labelled, headings in order, meaningful `alt`. The case timeline is an ordered list with dates in `<time>`. Accept and Edit buttons in the question list carry the question number in their accessible name, not a column of identical "Accept".
- **Contrast:** text 4.5:1 (3:1 for large text); controls and focus rings 3:1 against the surface.
- **Not colour alone:** validator flag severity, deadline state, "estimated" and "recheck" each need a text label or labelled icon, not just hue.
- **Errors:** announced (`role="alert"` or an `aria-live` region), tied to the field with `aria-describedby`, not colour-only. This includes the block on export when a PIO or applicant address is missing.
- **Motion:** honour `prefers-reduced-motion`.
- **Zoom and reflow:** usable at 200% zoom and at 320 CSS px wide without horizontal scroll or lost content (see the `responsive-design` skill).

## Record the result
Put the axe output and the manual checklist outcome in the PR description. A serious or critical axe violation, a control that cannot be reached by keyboard, or Tamil or Hindi text without a correct `lang` is a required fix before merge.

---
name: responsive-design
description: Use when adding or changing any screen in apps/web. Phone-first (360px up) Next.js and Tailwind layouts that hold long Tamil and Hindi text, with the case timeline and question accept/edit list working on a phone, verified by Playwright screenshots.
---

# Responsive Design

Voters will mostly try the live demo on a phone. A screen that only works at 1440px, or only with English text, is not done.

## Method
- Mobile-first Tailwind: base classes are the 360px layout; `sm:` `md:` `lg:` add room as it appears. Never write desktop first and patch it with `max-*` queries.
- Fluid layouts: `w-full`, `flex-1`, `min-w-0`. No fixed pixel widths on containers; use `max-w-*` with `mx-auto` only for a readable measure (forms, prose).
- Put `min-w-0` on every flex or grid child that holds text. A long unbreakable string (an id, a URL, a long Tamil compound) forcing page-wide horizontal scroll is the most common bug.
- Keep layout in CSS and server components (the CLAUDE.md default); do not branch on window width in client code.

## Tamil and Devanagari need room
The same sentence is usually longer in Tamil or Hindi than in English, and the glyphs are taller.
- No fixed-height text boxes. Use `min-h-*`, never `h-*`, on anything that holds text; let buttons and badges grow to two lines.
- Never truncate legal text: rewritten questions, subject lines, authority names, PIO addresses, deadline labels, validator flag messages, disclaimers. Use `break-words` and let it wrap. `truncate` and `line-clamp` are for decoration only.
- Use `leading-relaxed` (at least `leading-normal`) for body text; `leading-none` and `leading-tight` can clip Indic marks.
- Design with the longest of the three languages (usually Tamil), not the English string. Labels, tabs and the language switcher must survive it.
- Confirm Tamil and Devanagari glyphs render on a phone (no missing-glyph boxes). If the fallback font is poor, load Noto Sans Tamil and Noto Sans Devanagari (the PDFs already use those families).

## Screens that must work on a phone
- **Case timeline** (draft, filed, reply due, replied or deemed refused, appealed, closed): a vertical stack, one deadline per row. Date and label wrap; the "estimated" tag and the "recheck" warning stay visible beside the date, never hidden on small screens. No horizontal timeline that needs side-scrolling.
- **Question accept/edit list**: each question is a stacked card (original, rewritten, one-line reason) with Accept and Edit as large, full-width-on-phone targets. The edit textarea grows with its content (`min-h-*`) and the controls stay reachable with the on-screen keyboard open. If an action bar is pinned, pad the list so it never covers the last item.
- **Case dashboard**: cards below `md`, a table only from `md:` up. Any table that remains gets its own `overflow-x-auto` container so the page body never scrolls sideways.
- **Dialogs** (delete my data, confirm authority and address): `w-full max-w-[calc(100vw-1.5rem)]`, `max-h-[90dvh]`, content scrolls inside.

## Touch
Targets around 44px. Inputs at 16px or larger (smaller text makes iOS Safari zoom the page on focus). Nothing important is hover-only.

## Verify with Playwright screenshots
Add these checks to the web app's Playwright suite when `apps/web` exists. Look at the images; do not claim a pass from an assertion alone.
- Screenshot every touched screen at phone (360x800), tablet (768x1024) and desktop (1280x800).
- Capture text-heavy screens (question list, timeline, filing checklist) in en, hi and ta.
- Assert no page-level horizontal scroll: `document.documentElement.scrollWidth <= window.innerWidth`.
- Use fictional applicants only; screenshots must hold no real personal data (CLAUDE.md rule 3).

## Checklist
- [ ] No horizontal page scroll at 360px, in all three languages
- [ ] Nothing clipped, truncated or overlapping, including the longest Tamil string
- [ ] Timeline and question list are usable one-handed on a phone
- [ ] Wide content scrolls inside its own container; dialogs fit and scroll inside
- [ ] Touch targets are large enough; no hover-only controls
- [ ] Still usable at 200% zoom (see the `accessibility` skill)

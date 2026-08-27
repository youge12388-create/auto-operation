---
name: Signal Desk
description: Editorial operations workspace for advancing reviewed content into publication-ready drafts.
colors:
  workspace: "#f4f5fb"
  surface: "#ffffff"
  rule: "#dce0ed"
  rule-strong: "#c6cbdf"
  ink: "#20233d"
  muted-ink: "#5e627d"
  faint-ink: "#777c99"
  indigo-rail: "#171a3a"
  indigo-rail-hover: "#252958"
  indigo-rail-active: "#302f6d"
  commitment-violet: "#6d28d9"
  commitment-violet-hover: "#5b21b6"
  commitment-violet-soft: "#ede9fe"
  live-ocean: "#087ea4"
  live-ocean-soft: "#e0f2fe"
  success: "#18794e"
  success-soft: "#def7e7"
  attention: "#a64b00"
  attention-soft: "#fff0db"
  danger: "#bd3036"
  danger-soft: "#ffebeb"
typography:
  display:
    fontFamily: "ui-sans-serif, PingFang SC, Microsoft YaHei, Segoe UI, sans-serif"
    fontSize: "29px"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "-0.03em"
  title:
    fontFamily: "ui-sans-serif, PingFang SC, Microsoft YaHei, Segoe UI, sans-serif"
    fontSize: "19px"
    fontWeight: 750
    lineHeight: 1.35
    letterSpacing: "-0.02em"
  body:
    fontFamily: "ui-sans-serif, PingFang SC, Microsoft YaHei, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: "ui-sans-serif, PingFang SC, Microsoft YaHei, Segoe UI, sans-serif"
    fontSize: "11px"
    fontWeight: 750
    lineHeight: 1.45
    letterSpacing: "normal"
rounded:
  tag: "6px"
  compact: "9px"
  control: "10px"
  panel: "16px"
  decision: "18px"
spacing:
  tight: "8px"
  control: "12px"
  standard: "16px"
  panel: "24px"
  section: "28px"
  canvas: "40px"
components:
  button-primary:
    backgroundColor: "{colors.commitment-violet}"
    textColor: "#ffffff"
    typography: "{typography.label}"
    rounded: "{rounded.compact}"
    padding: "0 16px"
    height: "38px"
  button-primary-hover:
    backgroundColor: "{colors.commitment-violet-hover}"
  button-rail-create:
    backgroundColor: "#8057e7"
    textColor: "#ffffff"
    typography: "{typography.label}"
    rounded: "12px"
    padding: "0 16px"
    height: "44px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
    padding: "{spacing.panel}"
  tag-neutral:
    backgroundColor: "#eff0f7"
    textColor: "#555a76"
    typography: "{typography.label}"
    rounded: "{rounded.tag}"
    padding: "3px 10px"
  nav-active:
    backgroundColor: "#31336f"
    textColor: "#ffffff"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "0 13px"
    height: "40px"
---

## Overview

**Creative North Star: "The Editorial Signal Desk."** Content Ops is an Operate-mode desk for advancing reviewed content, not a generic administration console. A mineral-white work surface and deep indigo rail make the working context quiet; electric violet marks a commitment or active piece of work, while ocean blue is reserved for live system signal.

The visual story is attention -> content advancement -> automation state: make the next decision obvious, keep the consequence nearby, and carry the same context from source triage through topic selection, review, and WeChat draft delivery. Human review remains visible in the interface instead of being obscured by automation.

**The Decision-and-Consequence Rule.** Every primary work surface leads with the operator's next decision, then shows its queue, score, delivery state, or timeline in the same view.

**Key Characteristics:**

- Editorial, deliberate, and operational rather than dashboard-like or decorative.
- Ruled panels and compact information bands in place of a wall of elevated cards.
- Chinese-first system typography with tabular numerals for scores, times, and operational counts.
- Brief state transitions only; live feedback is visible but never theatrical.

## Colors

The token layer is normative. Treat mineral white as the default work surface and the indigo rail as the persistent context boundary. The commitment-violet family is for the action that moves work forward; it is not a general-purpose highlight. The ocean family denotes live signal, source intelligence, or system context.

**The Violet Commitment Rule.** Use commitment violet for the single next action adjacent to the item it changes, selected work, progress, and score emphasis. Do not use it to paint broad page backgrounds.

**The Ocean Signal Rule.** Use ocean blue only for live delivery, AI/source intelligence, or other system-signal context; it must remain distinguishable from a decision to commit work.

- Neutral foundation: workspace, surface, rule, rule-strong, ink, muted-ink, and faint-ink create the readable editorial plane.
- Navigation: indigo-rail, indigo-rail-hover, and indigo-rail-active keep orientation persistent without competing with the canvas.
- Operational state: success, attention, and danger each pair a dark foreground with a pale status band. These colors explain state; they do not replace written state labels.

## Typography

Use the compact Chinese system stack from the token layer throughout. Page titles use the display role; task titles and panel headings use title; supporting copy stays in the body role; labels, status bands, and small controls use label weight. Scores, timestamps, and counts use tabular numerals where the UI aligns them.

**The Compact Scan Rule.** Prefer short, specific Chinese labels and a clear hierarchy over oversized type. Keep explanatory copy readable, but make decisions, status, and countable evidence scannable first.

## Layout

The desktop shell is a fixed 256px indigo rail plus a 68px quiet command bar. The main canvas is centered, up to 1320px wide, with a 40px desktop inset; page heading, decision, and operational evidence appear in that order.

Use structured working layouts rather than stacked dashboard cards: the main dashboard pairs a decision-led queue with delivery context; material and detail views use a two-column split; review and publishing use a three-column workspace. Ruled dividers organize lists, metrics, and timelines inside panels.

**The First-Viewport Rule.** Before scrolling, show one clear decision and the immediate queue or delivery context that explains why it matters. Place its violet action beside the changed item.

At 1020px the rail's footer labels may collapse; at 860px canvas padding tightens; at 640px the rail becomes a 70px icon rail and dense summary grids become two or three columns. Preserve action visibility and readable status bands at every breakpoint.

## Elevation & Depth

The system is primarily flat: panels separate through mineral-white surfaces, quiet rules, and selected-state color rather than shadows. Ordinary cards and workspace panels have no elevation. The large popover is the intentional exception, using the existing large shadow token to sit above the command bar.

**The Ruled Depth Rule.** Establish hierarchy with dividers, tonal selection bands, and spacing first. Add a shadow only when a transient layer must clearly float over active work.

Motion is limited to approximately 150-160ms color, border, and position transitions. Respect `prefers-reduced-motion`; the live-state indicator is the only persistent motion role.

## Shapes

Panels are gently rounded and precise: standard work panels use the panel radius, decision banners may use the larger decision radius, controls use the compact/control radii, and tags use the smallest radius. Pills are reserved for compact statuses and controls, not for headings, large navigation blocks, or dense content containers.

**The Measured Corner Rule.** Use the smallest radius that identifies the object's role; preserve square ruled lists and metric subdivisions inside their shared panel.

## Components

### Primary actions

The primary button uses the commitment-violet token with white label text. It is a compact 38px control in the work canvas; the full-width rail creation control is 44px and uses its rail-specific violet. Hover darkens the work-canvas action to the primary hover token and may lift it by one pixel. Focus is a visible violet outline offset from the control.

### Navigation and command bar

The rail is a persistent indigo context frame. Navigation items are quiet by default, gain the rail hover surface on hover, and use a darker indigo active band with a violet left inset for the current location. The command bar remains white and restrained; search is a low-contrast field that gains a violet focus ring only when active.

### Panels, lists, and decision bands

Panels use the surface token, the panel radius, and a single rule border. List rows use ruled separation rather than independent floating cards. The dashboard decision band uses a pale violet, ocean, or danger tint to explain the next action's state, keeps the explanatory copy close, and places its action in the same band.

### Status, live signal, and timelines

Status tags are compact and label-weighted. Use the appropriate success, attention, danger, commitment, or ocean band with readable foreground text; never depend on color alone. Timeline marks and progress use violet for active/committed work, ocean for live signal, and success/danger only for completed or exceptional states.

### Inputs and selection

Inputs, textareas, selects, and search controls use a white or quiet neutral surface with the strong rule border. On focus, use the violet outline treatment. Selected rows use a pale violet background and a violet border; hover remains a subtle tonal change, not a shadow-heavy card effect.

## Do's and Don'ts

### Do:

- **Do** make the next operator decision and its queue, score, or delivery consequence visible together.
- **Do** use ruled dividers and compact status bands to show structure and automation state.
- **Do** reserve commitment violet for advancing or selecting work, and ocean blue for live system signal.
- **Do** keep review and publication actions explicit so human approval remains legible.
- **Do** maintain the responsive icon rail, visible actions, and reduced-motion behavior on compact screens.

### Don't:

- **Don't** turn the workspace into a generic metric-card dashboard or use shadows as the primary layout tool.
- **Don't** apply violet or ocean blue as interchangeable decoration, broad backgrounds, or unlabeled status indicators.
- **Don't** hide the next action far from the item or consequence it changes.
- **Don't** use large pill shapes for content regions, headings, or list layouts.

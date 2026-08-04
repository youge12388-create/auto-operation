# Candy AI visual system

## Direction contract

**THESIS:** Content operations should feel like a calm creative studio, not an admin console; the interface makes the next editorial decision obvious.

**OWN-WORLD:** A lilac worktable with saturated candy-pink actions, purple identity, cyan insight states, rounded 16–48px surfaces, pill navigation, and compact DM Sans / Chinese system typography.

**STORY:** The operator sees what needs attention, moves approved material into the library, turns live signals into a topic, and carries the same context into article review and WeChat preview.

**FIRST VIEWPORT:** A 256px persistent sidebar and quiet top bar frame a wide workbench. The main canvas opens with the queue, then separates work into a featured decision and a readable list; the primary action stays pink and close to the item it changes.

**FORM:** Operate mode; bento-like two-column workspaces for topics, material/detail split views, and a three-column review/publish workspace. The signature is the “editorial signal” treatment: score rings, insight panels, and live composition maps show why the next action is recommended.

## Durable tokens

- Background: `#fef7ff`; sidebar surface: `#f8eef8`; panel: `#ffffff`.
- Primary action: `#e040a0`; secondary identity: `#7c52aa`; information accent: `#0096cc`.
- Text: `#2e1a28`; muted text: `#604868`; outline: `#dcc8e0`.
- Cards use 16–24px radius; feature cards and navigation actions may use 9999px pills.
- Motion is restrained: hover lift and shadow only, with reduced-motion support.

## Scope note

This pass establishes the visual system across the existing pages. Product/API behavior remains in the current React Query and FastAPI contracts.

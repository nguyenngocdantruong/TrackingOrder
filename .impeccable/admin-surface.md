# Admin configuration surface

Direction: **Operate**. Extend the incumbent indigo/light neutral identity; do not create a separate visual world.

## Composition

Desktop uses a persistent section index and split section labels/settings. At 1000px, settings stack; at 650px, the index becomes a horizontal row above a single content column. The sticky save area keeps current/unsaved/submitting feedback beside the primary action, stacking on mobile.

## Interaction invariants

- Keep every input visibly labeled and keyboard focus discernible.
- Render secrets blank; show configured status and explain that an empty value preserves the current key.
- Announce unsaved changes, disable the action while submitting, and warn before leaving a dirty form.
- Reserve scrolling space for the sticky save area so fields remain reachable.
- Present errors in an alert region and honor reduced-motion settings for anchor scrolling.

## Review disposition

**Ship within UI scope**, based on the parent review's desktop and mobile synthetic screenshots. This is a visual and responsive review disposition, not evidence that production identity checks, secret persistence, or service restart behavior have been verified.

Source: `app/static/admin.css` and `app/templates/admin/index.html`. Shared visual authority: `app/templates/layout.html` and root `DESIGN.md`.

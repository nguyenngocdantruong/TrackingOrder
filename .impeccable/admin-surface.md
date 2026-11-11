# Admin configuration surface

Direction: **Operate**. Refine the established indigo and light neutral identity. This brief records the current admin composition and interaction contract; root `DESIGN.md` and `.impeccable/design.json` remain the shared visual authority and are unchanged by this refinement. Their older admin layout descriptions do not describe this surface's current implementation.

## Composition

Desktop uses a persistent section index (232px) beside content with a maximum width of 1120px. Settings occupy a white, bordered container: section title and description above two columns of fields, with switches spanning both columns. At 1000px and below, the index narrows to 208px and fields become one column. At 650px and below, navigation moves above content as horizontally scrollable links and the save controls stack with a full-width primary button.

The save area remains in normal document flow after the settings. It does not float over fields or obscure their labels, help, or validation messages.

## Interaction invariants

- Navigation progressively enhances hash-linked sections. With JavaScript, one section is visible and its link has an active state (`aria-current`); direct hashes and hash changes select the matching section. Without JavaScript, all sections remain available through normal anchor links.
- Keep every input visibly labeled, keyboard focus discernible, and the skip link available. Switches expose native checkbox behavior with a switch role and visible on/off text. Honor reduced-motion preferences.
- Render secret values blank. Show configured status and explain that an empty value preserves the existing key; never populate a stored secret into an input.
- Compare values with their initial state. Announce the number of changed fields and mark each affected section with a dot. Manually reverting values clears their dirty state, count, and section marker; returning all values to their initial state restores the clean status.
- Preserve edits across section changes. Warn before leaving a dirty form, and disable the save action with submitting feedback when a valid submission starts. Save status uses a polite live region.
- Reveal the section containing an invalid field before native validation attempts to focus it. Server errors appear in an alert region.
- The single save action applies the full form, including currently hidden sections. Its supporting copy explains that applying configuration restarts the service.

## Review disposition

**Ship within UI scope.** The parent review reported no blocking visual findings in synthetic desktop and mobile renders, including the wide desktop and mobile PayOS section. Review artifacts: [desktop](review/desktop.png), [mobile](review/mobile.png), [wide desktop](review/user-1920.png), and [mobile PayOS](review/mobile-payos.png).

The parent interaction checks covered section navigation, dirty counts and section markers, restoration to clean values, and revealing hidden invalid fields. These synthetic screenshots and interaction checks establish visual and client-side behavior only; they do not establish production authentication, configuration or secret persistence, or service restart behavior.

Implementation sources: `app/templates/admin/index.html`, `app/static/admin.css`, and `app/static/admin.js`. Shared visual sources: `app/templates/layout.html` and root `DESIGN.md`.

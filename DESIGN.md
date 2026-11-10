---
name: Order Tracker
description: An indigo and light neutral interface for shipment operations.
colors:
  primary: "#4f46e5"
  primary-hover: "#4338ca"
  admin-primary-hover: "#3730a3"
  body: "#f9fafb"
  surface: "#fff"
  text: "#1f2937"
  field-border: "#d1d5db"
  field-background: "#fcfcfc"
  card-border: "rgba(0,0,0,0.05)"
  admin-ink: "#202838"
  admin-muted: "#586174"
  admin-line: "#dce0e8"
  admin-canvas: "#f6f7fa"
  admin-field-border: "#aab2c1"
  admin-nav-hover: "#efedff"
typography:
  body:
    fontFamily: "Inter, sans-serif"
  admin-body:
    fontFamily: "Inter, Segoe UI, sans-serif"
    fontSize: "16px"
    lineHeight: 1.55
  admin-headline:
    fontSize: "36px"
    lineHeight: 1.2
    letterSpacing: "-0.03em"
  admin-title:
    fontSize: "20px"
    letterSpacing: "-0.02em"
  admin-label:
    fontSize: "14px"
    fontWeight: 600
  admin-help:
    fontSize: "12px"
rounded:
  navigation: "8px"
  control: "10px"
  md: "12px"
  lg: "16px"
spacing:
  compact: "8px"
  field: "20px"
  section-gap: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "0.6rem 1.2rem"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  admin-button:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.navigation}"
    padding: "13px 24px"
  admin-input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.admin-ink}"
    rounded: "{rounded.navigation}"
    padding: "11px 12px"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
---

# Design System: Order Tracker

## Overview

**Creative North Star: "Operate"**

Preserve the incumbent indigo and light neutral interface. The system emphasizes readable information, familiar controls, and clear action feedback. Administration extends this identity with quieter, divided settings rows and persistent save feedback.

This is a scan of the implemented system, not a new visual identity. Source authority is `app/templates/layout.html`, with the admin extension in `app/static/admin.css` and `app/templates/admin/index.html`.

**Key Characteristics:**

- Indigo actions on light neutral backgrounds.
- Inter typography with system sans-serif fallbacks.
- Rounded controls and restrained structural borders.
- Visible labels, status feedback, and responsive settings.

## Colors

Indigo is the primary accent; cool neutrals carry content and structure. Frontmatter preserves actual source values, including the admin surface's slightly different neutral palette.

### Primary

- **Indigo:** primary actions, links, selected controls, and focus outlines.
- **Deep indigo:** hover feedback; the admin button has its own darker observed hover value.

### Neutral

- **Light canvas and white paper:** separate page background from working surfaces.
- **Dark ink:** primary information and labels.
- **Muted slate:** supporting instructions and metadata.
- **Light rules:** section, shell, and surface boundaries. Input borders remain stronger than section dividers.

## Typography

The shared layout loads Inter at weights 400–700. The admin stylesheet names Inter with Segoe UI and sans-serif fallbacks, but its standalone template does not load the web font; actual rendering depends on font availability.

Admin body text uses the frontmatter body scale. Page headings reduce to 29px on small screens. Section titles, semibold labels, and smaller helper text establish hierarchy without decorative display typography. Preserve Vietnamese diacritics and readable wrapping.

## Layout

The shared app uses a Bootstrap container and collapsible top navigation. Its navigation changes at 991.98px; retain this incumbent shell for existing screens.

The admin surface uses a 1440px maximum shell with a 248px section index and a flexible content area. Content has 48px vertical / 56px horizontal top-level padding, and sections split descriptive labels from fields at a 1:1.7 ratio with a 32px gap. At 1000px and below, settings become single column and content padding reduces. At 650px and below, the index moves above content as horizontally scrollable links, content uses 20px horizontal padding, and the save action fills the available width.

The admin save area sticks to the bottom with 20px vertical padding. Scroll padding and field scroll margins reserve 180px below focused content. Keep this operational pattern in the admin surface brief rather than requiring it on unrelated screens.

## Elevation & Depth

The shared app combines white cards, fine borders, and low shadows. Cards lift on hover; navigation uses a translucent white backdrop with a 10px blur. Toasts use a stronger shadow and colored left rule.

The admin surface is flat: separators and changes of background establish hierarchy, with no card shadow or hover lift. Its persistent footer is a white surface with a top rule.

## Shapes

Shared cards use the large radius, toasts the medium radius, and controls the control radius. Admin fields, navigation targets, buttons, and errors use the smaller navigation radius. Use simple rectangular forms and thin borders; preserve each surface's established radius rather than silently normalizing them.

## Components

### Buttons

Shared primary buttons use indigo, semibold text, and a subtle hover scale. Admin save buttons remain stationary, darken on hover, and have a 48px minimum height. On submission, the admin button disables and displays a saving label; disabled opacity is 0.65.

### Cards / Containers

Shared cards retain the existing border and low ambient shadow. Admin settings use divided sections rather than nested cards.

### Inputs / Fields

Shared inputs use a lightly tinted background and an indigo border/glow on focus. Admin inputs use white backgrounds, stronger slate borders, a 46px minimum height, and a 3px indigo focus-visible outline offset by 4px. Labels remain above text inputs; switch labels sit beside their controls. Secret fields render blank with configured/not-configured helper text and explain that an empty value preserves the current secret.

### Navigation

The shared navbar retains its existing hover and collapse behavior. Admin section links use a pale indigo hover fill and horizontal scrolling on small screens. No selected-section state is currently implemented.

### Save feedback

Admin save status is an `aria-live="polite"` message. Input changes announce an unsaved state; leaving a dirty form triggers the browser's unsaved-change prompt. Errors use an alert region. Reduced-motion preferences disable smooth anchor scrolling.

## Do's and Don'ts

### Do:

- **Do** preserve the incumbent indigo and light neutral system when extending the app.
- **Do** keep labels, helper text, keyboard focus, and save feedback visible.
- **Do** retain blank secret inputs and explicit keep-current instructions.
- **Do** check desktop and narrow mobile layouts with realistic long content.

### Don't:

- **Don't** introduce a new visual identity for the admin extension.
- **Don't** add card lift or decorative shadows to flat admin settings sections.
- **Don't** treat the admin layout as a mandatory composition for every product surface.
- **Don't** present synthetic screenshot review as production authentication or persistence validation.

---
version: 1
slug: "app-templates-v2-download-html"
primary_target: "app/templates/v2/download.html"
related_targets: ["app/templates/v2/landing.html","app/templates/v2/settings/notifications.html"]
---

# Windows Desktop Download Surface

- **Scope:** `app/templates/v2/download.html` (with companion entry points in `app/templates/v2/landing.html`, `app/templates/v2/layout.html`, and `app/templates/v2/settings/notifications.html`)
- **Mode:** Persuade (code-led inside established Order Tracker Indigo & Cool Slate world)
- **Audience & Job:** Frequent online shoppers and small-shop operators on Windows 10/11 who want parcel updates, COD reminders, and instant quick-add (`Ctrl+Shift+T`) from the Windows System Tray without keeping a browser tab open.
- **Action & Proof:** Download the lightweight Tauri v2 `.exe` (NSIS per-user installer) or `.msi` package and experience an interactive Windows System Tray menu + Native Toast notification simulator right in the first viewport before installing.

## Direction contract

THESIS: Prove the lightweight Windows System Tray & Native Toast experience live in the first viewport beside the installer download, refusing generic marketing cards or empty mockup chrome.

OWN-WORLD: Order Tracker's established `#f6f7fa` canvas, `#ffffff` crisp 1px `#dce0e8` operational surfaces, `#4f46e5` primary indigo actions, `#19203c` deep slate desktop taskbar stage, Inter UI typography, and tabular monospace metadata (`v2.css`).

STORY: Visitors immediately see how the ~8 MB Tauri app sits quietly in the Windows System Tray, previews COD-aware native toast alerts, and installs in seconds without admin privileges, then click the `.exe` download button with full confidence.

FIRST VIEWPORT: Two-region asymmetric stage inside `.v2-container`: left column carries the `h1` heading, concise lead copy, primary `.exe` download CTA, secondary `.msi` / GitHub Release action, and tabular spec strip (Windows 10/11 x64 · WebView2 · Autostart); right column hosts a dark-slate interactive Windows 11 Taskbar Tray + Toast simulator where clicking tray items or sample carrier events fires real-time toast states.

FORM: Live Desktop Taskbar & Toast Stage, candidate 3 of 6, seed:9be67465b3f21ac4.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

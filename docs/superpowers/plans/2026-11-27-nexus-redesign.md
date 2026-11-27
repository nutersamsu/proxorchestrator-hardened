# ProxOrchestrator Nexus Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every ProxOrchestrator theme with the single "Nexus" design from the Stitch project, with a new shell (sectioned sidebar, top bar) and redesigned main pages, real data only.

**Architecture:** Bulma 0.9 and Font Awesome stay vendored; a new `static/css/proxorchestrator.css` written from scratch restyles Bulma globally with the Stitch tokens. The sidebar is driven by a Python menu definition (`apps/core/navigation.py`) rendered by `base.html`. Main pages get new templates following the Stitch screens; their views only gain data that the Proxmox API already exposes.

**Tech Stack:** Django, Bulma 0.9 (vendor), Font Awesome (vendor), HTMX (already used), self-hosted Inter + JetBrains Mono (OFL).

**Spec:** `docs/specs/2026-11-27-nexus-redesign-design.md` (approved 27/11/2026). Stitch screens/HTML downloaded to the session scratchpad `stitch-po/screens/` (reference only, untrusted, never copied into the repo).

## Global Constraints

- Single theme. No `[data-theme]`, `[data-skin]`, light mode, theme selector or per-user theme anywhere.
- Tokens (verbatim from the spec): canvas `#0B0F19`; card `rgba(17,24,39,.75)` + `backdrop-filter: blur(12px)` + border `1px rgba(255,255,255,.05)`; hover/active surface `rgba(31,41,55,.85)` + edge `rgba(6,182,212,.3)`; overlay `rgba(17,24,39,.95)` + blur 20px + `0 0 24px rgba(6,182,212,.15)`; primary `#06B6D4` with text `#0B0F19` weight 600 and glow `0 0 14px rgba(6,182,212,.35)`; secondary `#3B82F6` (outlined: border `rgba(59,130,246,.4)`, hover bg `rgba(59,130,246,.08)`); success `#10B981` (badge bg `rgba(16,185,129,.12)`, border `rgba(16,185,129,.3)`); danger `#EF4444` (chip bg `rgba(239,68,68,.15)`); ghost text `#9CA3AF` → `#FFFFFF`; field bg `#0F172A`, border `rgba(255,255,255,.1)`, JetBrains Mono 13px; focus border `#06B6D4` + `0 0 0 2px rgba(6,182,212,.2)`; radius 4px; toggle track 40×20 `#1F2937`, thumb 16px `#64748B` → `#06B6D4`.
- Type: Inter (body/headlines), JetBrains Mono (labels in caps, numbers, code). Headline sizes 28/22/18px, body 16/14/12px, code 13px.
- Layout: sidebar 280px; desktop buttons 36px tall, mobile hit targets ≥ 44px; sidebar becomes a drawer below 900px (existing behaviour); page never scrolls horizontally at 390px.
- No external requests from the browser (no CDN for fonts, icons or CSS).
- Real data only: no card, chip or number without a Proxmox/app source. No search box (the app has no global search).
- Proxmox logo: official media-kit SVG, unmodified, smaller than the "ProxOrchestrator" wordmark, wrapped in `<a href="https://www.proxmox.com" rel="noopener" target="_blank">`; footer notice exactly: `Proxmox® is a registered trademark of Proxmox Server Solutions GmbH in the EU, the U.S., and other countries.` (translated in pt-BR).
- All new UI text through `{% translate %}` / `gettext` with pt-BR entries in `locale/pt_BR/LC_MESSAGES/django.po`.
- Contrast ≥ 4.5:1 for text; visible focus; `prefers-reduced-motion: reduce` turns off pulsing/glow animations.
- No behaviour change to forms/actions. No deploy to VM 102 without the user asking.
- Commits: author `Nuter <84624762+nutersamsu@users.noreply.github.com>`, branch `hardening`; each task's commit only after the user approves its screenshots.

## Review Focus

- Non-staff user: menu, top bar and dashboard must not show or link staff-only pages (Node, Permissions, Setup Wizard, SMART card) — expect them absent, not broken.
- Proxmox unreachable or token 403: top-bar chips, dashboard cards and SMART card must render a short "unavailable" state, page still 200.
- Wizard not finished (`ProxmoxConfig.is_configured=False`): dashboard shows the setup call-to-action, top-bar chips endpoint returns 204 and the bar shows nothing.
- Long names (VM name 60 chars, node name, pt-BR labels): sidebar, chips and tables truncate with ellipsis instead of breaking layout at 1280px and 390px.
- Users who had a theme saved (old `localStorage.proxorchestrator_theme`, old `ui_theme` value): page loads in Nexus, no JS error.

---

### Task 0: Test runner and preview harness (scratchpad, not committed)

**Files (scratchpad only):**
- Create: `<scratch>/po-test/Dockerfile` — `FROM python:3.12-slim`, copies `requirements.txt` without `python-ldap`, `pip install`.
- Create: `<scratch>/po-test/run-tests.sh` — runs `python manage.py test <args>` in `po-test:dev` with the repo mounted read-only at `/src`, env `DJANGO_SETTINGS_MODULE=proxorchestrator.settings.base`, `SECRET_KEY=test`, `FIELD_ENCRYPTION_KEY=$(fresh Fernet key)`, `DB_PATH=/tmp/t.sqlite3`, `PYTHONDONTWRITEBYTECODE=1`, `--network none`.
- Create: `<scratch>/po-test/preview/fake_pve.py` + `run-preview.sh` — Django runserver on `127.0.0.1:8190` in the same image, with `ProxmoxConfig.get_api_client` patched to return fixture data (1 node "pve", 3 VMs incl. one 60-char name, 2 CTs, 4 disks with health PASSED/FAILED, 6 tasks, RRD points) and an admin + a non-staff user.
- Create: `<scratch>/po-test/shots.py` — CDP screenshots (Chromium `zenika/alpine-chrome:124`, `--remote-debugging-port=9223`, `suppress_origin=True`) of a list of URLs at 1440px and 390px, logged in as admin and as non-staff, reports JS console errors.

- [ ] **Step 1:** Build `po-test:dev`. Run `run-tests.sh` on the current `hardening` HEAD. Expected: all tests pass (≈215; Redis tests skipped).
- [ ] **Step 2:** Start the preview, run `shots.py` for `/` and `/vms/inventory/`. Expected: PNGs written, zero JS errors.

---

### Task 1: Remove the theme system

**Files:**
- Modify: `apps/core/context_processors.py` (delete `THEMES`, `THEME_KEYS`, `user_theme`, `theme_choices`; keep `css_version`)
- Modify: `apps/core/views.py` (delete `save_theme`), `apps/core/urls.py:26` (delete route)
- Modify: `apps/core/models.py` (delete `UserProfile.ui_theme`); Create: `apps/core/migrations/0006_remove_userprofile_ui_theme.py`
- Modify: `templates/base.html` (delete theme JS lines ~19-87, theme switch and `theme-picker` ~198-211; keep sidebar toggle script), `templates/wizard/settings.html` (delete theme selector block)
- Delete: `apps/core/tests/test_theme.py`; Create: `apps/core/tests/test_single_theme.py`

**Interfaces:** Produces: context key `css_version` only (no `user_theme`, `theme_choices`).

- [ ] **Step 1: Write failing tests** in `test_single_theme.py` (same setUp pattern as the old `test_theme.py`: LOCMEM cache, configured `ProxmoxConfig`, logged-in user):
  - `test_theme_endpoint_gone`: `POST /account/theme/` → 404.
  - `test_base_has_no_theme_machinery`: render `base.html` for the user; assert none of `theme-selector`, `data-skin`, `data-theme`, `proxorchestrator_theme`, `toggleTheme` in html.
  - `test_profile_has_no_ui_theme`: `"ui_theme" not in [f.name for f in UserProfile._meta.get_fields()]`.
  - `test_old_local_storage_is_harmless`: rendered html contains no inline script that reads `localStorage`.
- [ ] **Step 2:** Run `run-tests.sh apps.core.tests.test_single_theme`. Expected: 4 FAIL.
- [ ] **Step 3:** Make the deletions listed above; `makemigrations core` generates `0006` (RemoveField ui_theme).
- [ ] **Step 4:** Run the full suite. Expected: all pass, `makemigrations --check` clean.
- [ ] **Step 5:** Commit `Remove selectable themes (single Nexus theme follows)` — after Task 3's screenshots are approved (Tasks 1–3 ship together; the app is unstyled between them).

---

### Task 2: Fonts and the new stylesheet

**Files:**
- Create: `static/fonts/inter/` (Inter 400/500/600/700 woff2, latin + latin-ext, `OFL.txt`), `static/fonts/jetbrains-mono/` (400/500/600 woff2, `OFL.txt`) — from the official releases (rsms/inter, JetBrains/JetBrainsMono GitHub releases), checksums recorded in the commit message.
- Delete: `static/fonts/fira/`
- Replace: `static/css/proxorchestrator.css` (written from scratch) in this section order: `@font-face` → `:root` tokens (Global Constraints values as `--po-*` custom properties) → base (`html` 15px, body Inter, canvas) → Bulma components (button, input/select/textarea, card, table, tag, notification, tabs, modal, dropdown, progress, box, message, pagination, checkbox/radio, `.switch` toggle) → shell (`.sidebar`, `.topbar`, `.page-body`, `.taskbar`) → shared blocks (`.po-card`, `.po-metric`, `.po-label` caps mono, `.po-badge.is-ok|is-warn|is-bad` with 6px dot, `.po-bar` usage bar) → page sections (filled in by later tasks) → `@media (max-width: 900px)` → `@media (prefers-reduced-motion: reduce)`.
- Create: `apps/core/tests/test_stylesheet.py`

**Interfaces:** Produces CSS classes used by Tasks 3–8: `.po-card`, `.po-card-head`, `.po-metric`, `.po-metric-value`, `.po-label`, `.po-badge` (+ `.is-ok`, `.is-warn`, `.is-bad`, `.is-info`), `.po-bar` (child `i` with inline `width`), `.po-chip`, `.po-filters`, `.po-table` (on Bulma `.table`).

- [ ] **Step 1: Write failing tests** in `test_stylesheet.py` (read the CSS file as text):
  - `test_no_theme_selectors`: no `[data-theme` and no `[data-skin` in the CSS.
  - `test_tokens_present`: CSS contains `#0B0F19`, `#06B6D4`, `#3B82F6`, `#10B981`, `#EF4444` (case-insensitive) and `blur(12px)`.
  - `test_fonts_exist`: every `url(...)` inside `@font-face` resolves to an existing file under `static/`; families `Inter` and `JetBrains Mono` declared; `static/fonts/fira` does not exist.
  - `test_no_external_urls`: no `http://` or `https://` in the CSS.
  - `test_reduced_motion_block`: CSS contains `prefers-reduced-motion: reduce`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Add fonts, write the stylesheet.
- [ ] **Step 4:** Run full suite → PASS. Preview screenshots of `/`, a form page (`/vms/create/`), a table page, a modal: Bulma components readable, no unstyled controls.
- [ ] **Step 5:** Commit with Task 3.

---

### Task 3: Shell — sectioned sidebar, top bar, brand

**Files:**
- Create: `apps/core/navigation.py`, `templates/core/partials/sidebar.html`, `templates/core/partials/topbar_stats.html`
- Create: `static/images/proxmox/proxmox-logo-dark.svg` (official media-kit file for dark backgrounds, byte-identical; source URL in commit message)
- Modify: `templates/base.html` (sidebar → include; top bar), `apps/core/context_processors.py` (add `nav_sections`), `proxorchestrator/settings/base.py` (no change if processor already registered), `apps/core/views.py` + `apps/core/urls.py` (topbar stats endpoint)
- Create: `apps/core/tests/test_navigation.py`

**Interfaces:**
- Produces `navigation.NAV: list[Section]` where `Section = {"label": str, "items": list[Item]}` and `Item = {"label": str, "url_name": str, "icon": str (FA class), "staff_only": bool, "match": tuple[str, ...]}` (substrings of `resolver_match.url_name` that mark it active).
- Produces `navigation.sections_for(user, url_name: str) -> list[dict]` — filters staff items, sets `active: bool` per item, drops empty sections.
- Context processor key `nav_sections` (empty list for anonymous users).
- URL `topbar/stats/` name `topbar_stats` (login required): 204 when not configured, else renders `topbar_stats.html` with `summary` from `apps.core.node_summary.get_node_summary(config)`; on error renders the "unavailable" chip. HTMX `hx-trigger="load, every 30s"`.
- Menu content (labels exact, url names from the spec table): Datacenter & Cluster [Dashboard `dashboard`; Nodes & Health `node_page` staff; VMs & Guests `inventory`; LXC & Containers `lxc_list`] · Storage & Backups [Storage Pools `datastore_list`; Backup Jobs & Restore `backups_index`; Export & Import `export_index` (match also `lxc_export`, `px_`); Import files `storage_management`] · Cyber Defense [Firewall & Rules `firewall_index`; ACME TLS Certs `cert_settings`] · Tools & Automation [LXC Store `lxc_community_scripts`; VM Marketplace `vm_community_scripts`; Import Disk Wizard `importer_upload`; Setup Wizard `wizard_index` staff] · System & IAM [Permissions & API `pveaccess_page` staff; Task History & Logs `task_list`; Auth & MFA `auth_settings` (match also `mfa`); Users `user_list`; Proxmox `proxmox_settings`; Email `email_settings`].
- Top bar: menu button (mobile) · breadcrumb `datacenter / <default_node>` · page title block · stats chips (CPU %, RAM used/total) · buttons New VM (`vmcreator_create`, primary), LXC (`lxc_create`), Import (`importer_upload`) · page actions block · language switcher · Help · user menu (sign out). Sidebar footer: user + role, footer trademark notice.

- [ ] **Step 1: Write failing tests** in `test_navigation.py`:
  - `test_every_item_reverses`: `reverse(item["url_name"])` works for all items in `NAV`.
  - `test_staff_sees_all_items`: staff → item count == total items.
  - `test_non_staff_hides_admin_items`: non-staff → `node_page`, `pveaccess_page`, `wizard_index` absent.
  - `test_active_item`: `sections_for(staff, "lxc_export_index")` marks only "Export & Import" active.
  - `test_no_fake_pages`: no label in `("Security Audit", "Disks & Orphans")`.
  - `test_brand_and_trademark`: rendered `base.html` (logged in) contains `href="https://www.proxmox.com"`, `proxmox-logo-dark.svg`, and the exact trademark sentence.
  - `test_topbar_stats_not_configured`: with `is_configured=False` → 204.
  - `test_topbar_stats_ok` (patch `get_node_summary` → `{"summary": {"cpu_pct": 12.5, "memory": {"pct": 40.0, "text": "..."}}, "error": None, ...}`): 200, html contains `12.5` and `40`.
  - `test_topbar_stats_error`: summary `None`, error set → 200 and contains the translated "unavailable" text.
  - `test_topbar_stats_requires_login`: anonymous → 302 to `/login/`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `navigation.py`, context processor key, partials, endpoint, `base.html` shell, shell CSS section. Download the official logo from `https://www.proxmox.com/images/proxmox/logos/mediakit-proxmox-server-solutions-logos-dark.svg` (if that variant is dark-on-light, use `-light.svg`; pick the one legible on `#0B0F19`) into its own scratch dir, inspect it, then copy unmodified.
- [ ] **Step 4:** Full suite → PASS. Preview screenshots (admin + non-staff, 1440 + 390) compared with Stitch "Dashboard (Cluster Overview)" shell.
- [ ] **Step 5:** Show screenshots to the user; on approval commit Tasks 1–3 as three commits (`Remove selectable themes…`, `Nexus stylesheet and self-hosted Inter/JetBrains Mono`, `Nexus shell: sectioned sidebar, top bar, Proxmox logo`).

---

### Task 4: Dashboard (Stitch "Dashboard (Cluster Overview)")

**Files:**
- Modify: `templates/core/dashboard.html` (rewrite), `apps/core/views.py` (`dashboard` context), `templates/core/partials/node_summary.html` (new layout)
- Create: `templates/core/partials/dashboard_disks.html`; view `dashboard_disks` + URL `dashboard/disks/` name `dashboard_disks` (staff only, 403 otherwise)
- Test: `apps/core/tests/test_dashboard_nexus.py`

**Interfaces:**
- Consumes: `get_node_summary(config)` (keys `cpu_pct`, `cpu_desc`, `loadavg`, `memory{pct,text,present}`, `rootfs{…}`, `swap{…}`, `io_delay_pct`, `uptime`, `pveversion`, `kernel`), RRD endpoint `rrd_node` (existing), `tasks_recent` (existing partial), `api.get_vms(node)`, `api.get_lxcs(node)`.
- Produces context `guests: list[dict]` with keys `vmid:int, name:str, kind:"vm"|"ct", status:str, cpu_pct:float, mem_used:int, mem_total:int, url:str` sorted by vmid; existing `vm_*`/`ct_*` counts and `recent_jobs` kept.
- `dashboard_disks` renders `/nodes/{node}/disks/list` (cache 60 s, key `po:dash-disks:<config.pk>:<node>`): model, devpath, size, health badge (`PASSED`/`OK` → `is-ok`, anything else → `is-bad`), wearout.

Layout (top→bottom): status strip (node online badge, uptime, PVE version, cert days left if `cert_days_remaining`) · 4 metric cards: CPU (pct + model + load + RRD sparkline), Memory (used/total + ring), Storage rootfs (used/total + bar), Swap/IO delay · active task strip (first running task from `tasks_recent`, hidden when none) · guests table with client-side filter buttons All/VMs/LXCs/Running/Stopped (counts from `guests`) and "Deploy" button → `vmcreator_create` · right column: SMART card (staff, HTMX `dashboard_disks`), "Recent tasks" card (HTMX `tasks_recent`). Setup-required and cert-expiry notices keep their current conditions.

- [ ] **Step 1: Write failing tests** (patch `ProxmoxConfig.get_api_client` with a fake returning 2 VMs + 1 CT):
  - `test_guests_merged_and_sorted`: `response.context["guests"]` vmids `[100, 101, 105]`, kinds `["vm","ct","vm"]`.
  - `test_filter_counts_rendered`: html contains `data-filter="running"` and the running count.
  - `test_non_staff_no_smart_card`: non-staff html has no `dashboard/disks/`; `GET /dashboard/disks/` → 403.
  - `test_disks_health_badges`: staff, fake disks `PASSED` + `FAILED` → html has one `is-ok` and one `is-bad`.
  - `test_api_down_still_200`: api raises `ProxmoxAPIError` → 200, guests empty, "unavailable" text present.
  - `test_not_configured_shows_wizard_cta`: `is_configured=False` → contains `wizard` link, no guests table.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Suite PASS + preview screenshots vs Stitch. **Step 5:** User approval → commit `Nexus dashboard`.

---

### Task 5: VMs & Guests and LXC & Containers (Stitch "VMs & Guests Inventory")

**Files:** Modify `templates/inventory/list.html` (view `apps/inventory/views.py:list_vms`), `templates/lxc/list.html` (view `apps/lxc/views.py:list_lxcs`), page section of the CSS. Test: `apps/core/tests/test_inventory_nexus.py`.

**Interfaces:** Consumes the existing view contexts unchanged; adds no data. Uses `.po-filters`, `.po-table`, `.po-badge`, `.po-bar`.

Layout: header with counts (total/running/stopped) · filter bar (status buttons, client-side text filter input bound to `data-name`) · dense table: state dot + VMID, name (ellipsis, full name in `title`), type badge (QEMU/LXC CT), CPU bar, memory used/total, actions (existing buttons, unchanged URLs/forms).

- [ ] **Step 1: Tests:** `test_inventory_renders_rows` (3 fake VMs → 3 `<tr data-name=…>`), `test_long_name_has_title` (60-char name appears in a `title` attribute), `test_actions_unchanged` (every action form/URL present before the redesign is still present — compare the set of `href`/`action` values to a fixture captured from the old template in Step 0 of this task), same for LXC list.
- [ ] **Step 2–5:** fail → implement → pass + screenshots → approval → commit `Nexus inventory pages`.

---

### Task 6: LXC Store and VM Marketplace (Stitch "LXC 1-Click Store")

**Files:** Modify `templates/lxc/community_scripts.html` + `templates/lxc/partials/script_grid.html` and `templates/vmcreator/vm_community_scripts.html` + `templates/vmcreator/partials/vm_script_grid.html`; CSS section. Test: `apps/lxc/tests` / `apps/vmcreator/tests` new module `test_store_nexus.py`.

**Interfaces:** existing contexts (catalog with categories). Layout: category chips row, search input (client-side filter over the already-loaded catalog — real feature, not global search), card grid (logo if the catalog has one, name, category, short description, default port/resources if present, "Install" → existing URL).

- [ ] Tests: `test_cards_count_matches_catalog`, `test_install_links_unchanged`, `test_category_chips_from_catalog`. Then fail → implement → pass + screenshots → approval → commit `Nexus community script store`.

---

### Task 7: Firewall, Tasks, Storage/Backups, Node, Permissions

**Files:** `templates/firewall/index.html`, `templates/tasks/list.html` (+ task detail template), `templates/backups/storage_list.html`, `templates/backups/index.html`, `templates/node/node.html`, `templates/node/access.html`; CSS section. Test: `apps/core/tests/test_admin_pages_nexus.py`.

**Interfaces:** existing contexts only. Each page: header + `.po-card` sections + `.po-table`; status values as `.po-badge`; usage as `.po-bar`; log/terminal areas in JetBrains Mono on field bg. Layouts follow the Stitch screens "Firewall & Rules", "Tasks History & Logs", "Storage & Backups", "Node Health & Admin", "Permissions & API Tokens" minus their invented data.

- [ ] Tests: each page 200 for staff with fake API; non-staff → existing behaviour (403/redirect) unchanged; `test_no_inline_theme_colors` (no `style="…color: var(--text-` legacy variables left in these templates). Then fail → implement → pass + screenshots → approval → commit `Nexus admin pages`.

---

### Task 8: Login, MFA, password reset, Setup Wizard

**Files:** `templates/core/login.html`, `mfa_setup.html`, `mfa_verify.html`, `mfa_recovery_codes.html`, `mfa_email_recovery.html`, `password_reset_*.html`, `change_password.html`, `templates/wizard/*.html`; CSS section. Test: `apps/core/tests/test_auth_pages_nexus.py`.

Layout: centred glass card on the canvas (Stitch "Authentication, TOTP MFA & Password Recovery", "Setup Wizard & Proxmox Connection"), brand block (shield + ProxOrchestrator + small Proxmox logo with link + trademark line), wizard step indicator.

- [ ] Tests: login page renders without a session and contains the brand and trademark line; MFA verify form fields unchanged (names `code`, csrf); wizard steps 1–5 render for staff. Then fail → implement → pass + screenshots → approval → commit `Nexus login, MFA and setup wizard`.

---

### Task 9: Translations and final pass

**Files:** `locale/pt_BR/LC_MESSAGES/django.po` (+ compiled `.mo`), `apps/core/tests/test_i18n.py` (extend), `README.md` (theme section → "Nexus theme"), `SECURITY-HARDENING.md` untouched.

- [ ] **Step 1: Test** `test_new_strings_translated`: activate `pt-br`, render `base.html` and dashboard; assert pt-BR menu labels from the `.po` appear (e.g. the translation chosen for "Storage & Backups") and no English section label from `NAV` remains.
- [ ] **Step 2:** `makemessages -l pt_BR`, translate new msgids (none left fuzzy/empty among the new ones), `compilemessages`.
- [ ] **Step 3:** Full suite PASS; `makemigrations --check` clean; screenshot sweep of every menu page as admin and non-staff at 1440 and 390 → zero JS errors, no horizontal scroll at 390.
- [ ] **Step 4:** User approval → commit `Nexus redesign: pt-BR strings and README`; push `hardening` only when the user says "pode publicar". Deploy to VM 102 only on explicit request (`git archive hardening` → VM → `update.sh`).

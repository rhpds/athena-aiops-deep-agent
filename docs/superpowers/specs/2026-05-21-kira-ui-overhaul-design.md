# Kira UI Overhaul — Fed Aura-Inspired Redesign

## Goal

Transform Kira's dated Solarized dark interface into a modern, vibrant, professional look inspired by the Fed Aura Capital mortgage application. CSS variable reskin — no framework migration, no functionality changes.

## Reference

- **Fed Aura Capital** (multi-agent-loan-origination): React 19 + Tailwind CSS v4 + shadcn/ui
- Visual identity: navy blue header, clean white surfaces, red CTAs, Inter font, tinted pill badges, card shadows
- Source: https://github.com/rh-ai-quickstart/multi-agent-loan-origination

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Theme system | Light only — remove dark mode | Simplifies maintenance, matches reference. Terminal panel stays dark naturally. |
| Architecture | CSS variable reskin | 90% visual impact with ~20% of the work vs Tailwind migration. Lowest risk. |
| Chat FAB | Navy blue, subtle | Professional. Blends with header instead of competing for attention. |
| Font | Inter via Google Fonts CDN | Clean, modern sans-serif. Client-side load — no container rebuild dependency. |
| Image version | `kira-frontend:0.11.0` | Bumps past 0.10.x. Forces pull with IfNotPresent policy. |
| Deployment | Integration CI only via draft PR | Production stays on current tag. Zero risk to live labs. |

## Color Palette

### Core Tokens (themes.ts)

```
--kira-bg-page:        #f8fafc     (off-white page background)
--kira-bg-card:        #ffffff     (white card surfaces)
--kira-bg-input:       #ffffff     (white input fields)
--kira-text-primary:   #0f172a     (slate 900 — headings, body)
--kira-text-secondary: #334155     (slate 700 — secondary text)
--kira-text-muted:     #64748b     (slate 500 — labels, hints)
--kira-border:         #e2e8f0     (slate 200 — card borders)
--kira-border-subtle:  #f1f5f9     (slate 100 — row separators)
--kira-accent:         #1e3a5f     (navy — links, IDs, emphasis)
--kira-nav-bg:         #1e3a5f     (navy header background)
--kira-link:           #1e3a5f     (navy links)
--kira-btn-bg:         #cc0000     (Red Hat red — primary buttons)
--kira-btn-border:     #cc0000     (button border)
--kira-btn-text:       #ffffff     (white button text)
--kira-status-opacity: 0.12        (badge background opacity)
```

### New Tokens

```
--kira-nav-text:       rgba(255,255,255,0.7)   (nav link text)
--kira-nav-active:     #ffffff                  (active nav link)
--kira-nav-indicator:  #cc0000                  (active nav underline)
--kira-shadow-sm:      0 1px 2px rgba(0,0,0,0.05)
--kira-shadow-md:      0 1px 3px rgba(0,0,0,0.1)
--kira-radius:         8px                      (card border radius)
--kira-radius-pill:    12px                     (badge/lozenge radius)
```

### Lozenge Colors (Lozenge.tsx)

Tinted pill style: colored text on light tinted background, `border-radius: 12px`.

**Areas:**
| Area | Background | Text |
|------|-----------|------|
| linux | `#f3f0ff` | `#7c3aed` |
| kubernetes | `#eff6ff` | `#2563eb` |
| networking | `#ecfeff` | `#0891b2` |
| application | `#eef2ff` | `#6366f1` |
| database | `#ecfdf5` | `#059669` |
| storage | `#fffbeb` | `#d97706` |
| security | `#fef2f2` | `#dc2626` |

**Risk:**
| Level | Background | Text |
|-------|-----------|------|
| critical | `#fef2f2` | `#dc2626` |
| high | `#fef2f2` | `#dc2626` |
| medium | `#fffbeb` | `#d97706` |
| low | `#f0fdf4` | `#16a34a` |

**Status:**
| Status | Background | Text |
|--------|-----------|------|
| open | `#fef2f2` | `#dc2626` |
| acknowledged | `#fffbeb` | `#d97706` |
| in_progress | `#eff6ff` | `#2563eb` |
| resolved | `#f0fdf4` | `#16a34a` |
| closed | `#f1f5f9` | `#6b7280` |

**Stage:**
| Stage | Background | Text |
|-------|-----------|------|
| dev | `#f0fdf4` | `#16a34a` |
| test | `#fffbeb` | `#d97706` |
| production | `#fef2f2` | `#dc2626` |
| unknown | `#f1f5f9` | `#6b7280` |

**Confidence:**
| Range | Background | Text |
|-------|-----------|------|
| 80-100 | `#f0fdf4` | `#16a34a` |
| 50-79 | `#fffbeb` | `#d97706` |
| 0-49 | `#fef2f2` | `#dc2626` |

**Skill tags:** `background: #f1f5f9`, `color: #475569`, `border: 1px solid #e2e8f0`, `border-radius: 12px`.

## Component Changes

### Theme System

**`theme/themes.ts`**: Replace both themes with a single exported palette object. Remove `ThemeName` type, `darkTheme`, `lightTheme`, and the `themes` record. Export a single `theme: ThemeTokens` with the new palette values above.

**`theme/ThemeProvider.tsx`**: Simplify to apply the single theme on mount. Remove localStorage persistence of theme choice, remove toggle function from context. Keep the context provider pattern (components still consume via `useTheme()`) but the value is static.

### Layout & Navigation

**`components/Layout.tsx`**:
- Header: `background: var(--kira-nav-bg)` (navy)
- Logo: white text, `font-weight: 700`
- Nav links: `color: rgba(255,255,255,0.5)`, active link `color: white` with `border-bottom: 2px solid #cc0000`
- Remove theme toggle button (sun/moon emoji)
- Logout button: `background: rgba(255,255,255,0.15)`, white text, subtle rounded style
- User name: `color: rgba(255,255,255,0.6)`

### Badges / Lozenges

**`components/Lozenge.tsx`**: All lozenge variants switch from solid background + white text to tinted background + colored text. `border-radius` changes from `3px` to `12px`. Padding increases slightly for pill proportions: `padding: 3px 10px`.

### Chat Widget

**`components/ChatWidget.tsx`**:
- FAB button: `background: #1e3a5f`, `border-radius: 50%`, `box-shadow: 0 4px 12px rgba(30,58,95,0.3)`
- Chat panel header: `background: #1e3a5f`, white text
- Chat panel body: white background
- User message bubbles: `background: #1e3a5f`, white text, `border-radius: 8px 8px 2px 8px`
- Assistant message bubbles: `background: #f1f5f9`, dark text, `border-radius: 8px 8px 8px 2px`
- Send button: `background: #1e3a5f`, white text
- Input: white with `border: 1px solid #e2e8f0`

### Skill Tags

**`components/SkillTag.tsx`**: Light gray background `#f1f5f9`, dark text `#475569`, subtle border, pill radius `12px`.

### Value Edit Dialog

**`components/ValueEditDialog.tsx`**: White background, `border: 1px solid #e2e8f0`, `box-shadow` for elevation. Slider track and submit button use `#1e3a5f`.

### Issue Card

**`components/IssueCard.tsx`**: White card, `border-radius: 8px`, `box-shadow: 0 1px 2px rgba(0,0,0,0.05)`, `border: 1px solid #e2e8f0`.

### Terminal Panel

**`components/TerminalPanel.tsx`**: Minimal changes. The ttyd iframe is already dark-themed. Drag handle and panel chrome updated to use `--kira-border` and `--kira-bg-card`.

## Page Changes

### Dashboard

**`pages/Dashboard.tsx`**:
- Stat cards: white background, `border-radius: 8px`, subtle shadow, uppercase label text in `#64748b`
- Stat numbers: color-coded (open=`#dc2626`, in progress=`#2563eb`, resolved=`#16a34a`, confidence=`#1e3a5f`)
- Recharts bar chart: update `chartColors` to match area lozenge colors
- Page heading: `font-size: 18px`, `font-weight: 600`, `color: #0f172a`

### Ticket List / Issue List

**`pages/TicketList.tsx`**, **`pages/IssueList.tsx`**:
- Wrap table in white card with shadow and rounded corners
- Table header: uppercase `#64748b` labels with `letter-spacing: 0.6px`
- Row separators: `border-bottom: 1px solid #f1f5f9`
- Filter dropdowns: white background, `border: 1px solid #e2e8f0`, `border-radius: 6px`

### Ticket Detail / Issue Detail

**`pages/TicketDetail.tsx`**, **`pages/IssueDetail.tsx`**:
- Section cards with white background, shadow, rounded corners
- Headings: `#0f172a`, `font-weight: 600`
- Markdown content: clean typography with proper line-height
- Tab bar: subtle bottom border, active tab has `#cc0000` underline

### Create Ticket

**`pages/CreateTicket.tsx`**:
- Form inputs: white background, `border: 1px solid #e2e8f0`, `border-radius: 6px`
- Labels: `font-size: 12px`, `font-weight: 500`, `color: #334155`
- Submit button: `background: #cc0000`, white text

### Workspace

**`pages/Workspace.tsx`**:
- Chat panel: white background, navy header matching ChatWidget style
- Divider handle: uses `--kira-border`

### Login

**`pages/Login.tsx`**:
- Centered card on `#f8fafc` background
- Card: white, `border-radius: 12px`, `box-shadow: 0 4px 12px rgba(0,0,0,0.08)`
- Logo + "Sign In" heading at top
- Subtitle: "Access your incident dashboard"
- Submit button: `background: #cc0000`

### index.html

Add Inter font from Google Fonts CDN:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

Set `font-family: 'Inter', system-ui, -apple-system, sans-serif` as the body default.

## Deployment Strategy

1. **Code changes**: All in Kira source repo (`frontend/src/`)
2. **Build image**: `podman build --platform linux/amd64 -t quay.io/rhpds/kira-frontend:0.11.0 -f deploy/Dockerfile.frontend .`
3. **Push image**: `podman push quay.io/rhpds/kira-frontend:0.11.0`
4. **AgnosticV draft PR**: Update integration CI (`summit-2026.lb2645-agentic-devops-tenant.dev`) to use `kira-frontend:0.11.0`
5. **Production CI**: Stays on current tag — no changes until validated on integration
6. **Rollback**: Revert AgnosticV CI to previous tag if issues found

## Out of Scope

- No Tailwind CSS or shadcn/ui migration
- No new features or functionality changes
- No API changes
- No backend changes
- No production CI changes (integration only)
- No dark mode (removed entirely)

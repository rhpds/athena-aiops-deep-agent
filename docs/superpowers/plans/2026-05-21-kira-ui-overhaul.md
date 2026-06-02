# Kira UI Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Kira's Solarized dark UI into a modern, Fed Aura-inspired light design via CSS variable reskin.

**Architecture:** Replace theme tokens in `themes.ts`, simplify `ThemeProvider` to single-theme, update hardcoded colors in components and pages. No framework migration — inline styles stay, colors change.

**Tech Stack:** React 19, TypeScript, Vite, Recharts, react-markdown

**Kira repo:** `/Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira`
**Frontend root:** `frontend/`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/index.html` | Modify | Add Inter font, update title |
| `frontend/src/theme/themes.ts` | Rewrite | Single light theme palette |
| `frontend/src/theme/ThemeProvider.tsx` | Rewrite | Remove dark mode, static theme |
| `frontend/src/components/Layout.tsx` | Modify | Navy header, remove toggle |
| `frontend/src/components/Lozenge.tsx` | Modify | Tinted pill badges |
| `frontend/src/components/ChatWidget.tsx` | Modify | Navy FAB + panel |
| `frontend/src/components/SkillTag.tsx` | Modify | Pill style |
| `frontend/src/components/ValueEditDialog.tsx` | Modify | New palette colors |
| `frontend/src/components/IssueCard.tsx` | Modify | Tinted badges, card shadow |
| `frontend/src/pages/Login.tsx` | Modify | Centered card redesign |
| `frontend/src/pages/Dashboard.tsx` | Modify | Card shadows, chart colors |
| `frontend/src/pages/TicketList.tsx` | Modify | Card wrapper, shadows |
| `frontend/src/pages/IssueList.tsx` | Modify | Card wrapper, shadows |
| `frontend/src/pages/TicketDetail.tsx` | Modify | Section cards, tab styling |
| `frontend/src/pages/IssueDetail.tsx` | Modify | Section cards |
| `frontend/src/pages/CreateTicket.tsx` | Modify | Form styling |
| `frontend/src/pages/Workspace.tsx` | Modify | Chat panel styling |

---

### Task 1: Theme Foundation

**Files:**
- Modify: `frontend/index.html`
- Rewrite: `frontend/src/theme/themes.ts`
- Rewrite: `frontend/src/theme/ThemeProvider.tsx`

- [ ] **Step 1: Update index.html — add Inter font and title**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <title>Kira</title>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body { font-family: 'Inter', system-ui, -apple-system, sans-serif; -webkit-font-smoothing: antialiased; }
    </style>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Rewrite themes.ts — single light theme**

```typescript
export interface ThemeTokens {
  "--kira-bg-page": string;
  "--kira-bg-card": string;
  "--kira-bg-input": string;
  "--kira-text-primary": string;
  "--kira-text-secondary": string;
  "--kira-text-muted": string;
  "--kira-border": string;
  "--kira-border-subtle": string;
  "--kira-accent": string;
  "--kira-nav-bg": string;
  "--kira-link": string;
  "--kira-btn-bg": string;
  "--kira-btn-border": string;
  "--kira-btn-text": string;
  "--kira-status-opacity": string;
  "--kira-nav-text": string;
  "--kira-nav-active": string;
  "--kira-nav-indicator": string;
  "--kira-shadow-sm": string;
  "--kira-shadow-md": string;
  "--kira-radius": string;
  "--kira-radius-pill": string;
}

export const theme: ThemeTokens = {
  "--kira-bg-page": "#f8fafc",
  "--kira-bg-card": "#ffffff",
  "--kira-bg-input": "#ffffff",
  "--kira-text-primary": "#0f172a",
  "--kira-text-secondary": "#334155",
  "--kira-text-muted": "#64748b",
  "--kira-border": "#e2e8f0",
  "--kira-border-subtle": "#f1f5f9",
  "--kira-accent": "#1e3a5f",
  "--kira-nav-bg": "#1e3a5f",
  "--kira-link": "#1e3a5f",
  "--kira-btn-bg": "#cc0000",
  "--kira-btn-border": "#cc0000",
  "--kira-btn-text": "#ffffff",
  "--kira-status-opacity": "0.12",
  "--kira-nav-text": "rgba(255,255,255,0.7)",
  "--kira-nav-active": "#ffffff",
  "--kira-nav-indicator": "#cc0000",
  "--kira-shadow-sm": "0 1px 2px rgba(0,0,0,0.05)",
  "--kira-shadow-md": "0 1px 3px rgba(0,0,0,0.1)",
  "--kira-radius": "8px",
  "--kira-radius-pill": "12px",
};
```

- [ ] **Step 3: Rewrite ThemeProvider.tsx — remove dark mode**

```typescript
import { createContext, useContext, useEffect, type ReactNode } from "react";
import { theme, type ThemeTokens } from "./themes";

interface ThemeContextValue {
  theme: ThemeTokens;
}

const ThemeContext = createContext<ThemeContextValue>({ theme });

export function useTheme() {
  return useContext(ThemeContext);
}

function applyTheme() {
  const root = document.documentElement;
  for (const [key, value] of Object.entries(theme)) {
    root.style.setProperty(key, value);
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    applyTheme();
  }, []);

  return (
    <ThemeContext.Provider value={{ theme }}>
      {children}
    </ThemeContext.Provider>
  );
}
```

- [ ] **Step 4: Verify build compiles**

Run: `cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira/frontend && npm run build`
Expected: Build succeeds (may have warnings from Layout.tsx still importing `toggleTheme` — that's fixed in Task 2)

- [ ] **Step 5: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira
git add frontend/index.html frontend/src/theme/themes.ts frontend/src/theme/ThemeProvider.tsx
git commit -m "feat(frontend): replace Solarized themes with Fed Aura-inspired light palette"
```

---

### Task 2: Layout & Navigation

**Files:**
- Modify: `frontend/src/components/Layout.tsx`

- [ ] **Step 1: Rewrite Layout.tsx — navy header, remove theme toggle**

Replace the entire file with:

```typescript
import { Link, Outlet, useNavigate, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { User } from "../types";

export function Layout() {
  const [user, setUser] = useState<User | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    api.me().then(setUser).catch(() => navigate("/login"));
  }, [navigate]);

  const handleLogout = async () => {
    await api.logout();
    navigate("/login");
  };

  if (!user) return null;

  const navLink = (to: string, label: string) => {
    const active = to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
    return (
      <Link
        to={to}
        style={{
          color: active ? "var(--kira-nav-active)" : "var(--kira-nav-text)",
          fontSize: "13px",
          textDecoration: "none",
          fontWeight: active ? 500 : 400,
          borderBottom: active ? "2px solid var(--kira-nav-indicator)" : "2px solid transparent",
          paddingBottom: "6px",
        }}
      >
        {label}
      </Link>
    );
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--kira-bg-page)", color: "var(--kira-text-primary)" }}>
      <nav
        style={{
          background: "var(--kira-nav-bg)",
          padding: "10px 20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", gap: "24px", alignItems: "center" }}>
          <Link to="/" style={{ fontWeight: 700, fontSize: "17px", color: "var(--kira-nav-active)", textDecoration: "none", letterSpacing: "-0.5px" }}>
            Kira
          </Link>
          {navLink("/", "Dashboard")}
          {navLink("/tickets", "Tickets")}
          {navLink("/issues", "Backlog")}
          {user.role !== "viewer" && navLink("/workspace", "Workspace")}
          {user.role !== "viewer" && (
            <Link
              to="/tickets/new"
              style={{
                background: "var(--kira-btn-bg)",
                color: "var(--kira-btn-text)",
                padding: "5px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                textDecoration: "none",
                fontWeight: 500,
              }}
            >
              + New Ticket
            </Link>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "12px" }}>
            {user.display_name}
          </span>
          <button
            onClick={handleLogout}
            style={{
              background: "rgba(255,255,255,0.15)",
              border: "none",
              color: "var(--kira-nav-active)",
              padding: "5px 12px",
              borderRadius: "4px",
              cursor: "pointer",
              fontSize: "12px",
            }}
          >
            Logout
          </button>
        </div>
      </nav>
      <main style={{ padding: "20px", maxWidth: "1200px", margin: "0 auto" }}>
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira/frontend && npm run build`
Expected: PASS — no more `toggleTheme` import error

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira
git add frontend/src/components/Layout.tsx
git commit -m "feat(frontend): navy header with red active indicator, remove theme toggle"
```

---

### Task 3: Lozenge Redesign

**Files:**
- Modify: `frontend/src/components/Lozenge.tsx`

- [ ] **Step 1: Replace Lozenge.tsx with tinted pill style**

Replace the entire file with:

```typescript
import type { Area } from "../types";

const AREA_STYLES: Record<Area, { bg: string; color: string }> = {
  linux: { bg: "#f3f0ff", color: "#7c3aed" },
  kubernetes: { bg: "#eff6ff", color: "#2563eb" },
  networking: { bg: "#ecfeff", color: "#0891b2" },
  database: { bg: "#ecfdf5", color: "#059669" },
  storage: { bg: "#fffbeb", color: "#d97706" },
  security: { bg: "#fef2f2", color: "#dc2626" },
  application: { bg: "#eef2ff", color: "#6366f1" },
};

function riskStyle(value: number): { bg: string; color: string } {
  if (value >= 0.7) return { bg: "#fef2f2", color: "#dc2626" };
  if (value >= 0.4) return { bg: "#fffbeb", color: "#d97706" };
  return { bg: "#f0fdf4", color: "#16a34a" };
}

function confidenceStyle(value: number): { bg: string; color: string } {
  if (value >= 0.8) return { bg: "#f0fdf4", color: "#16a34a" };
  if (value >= 0.5) return { bg: "#fffbeb", color: "#d97706" };
  return { bg: "#fef2f2", color: "#dc2626" };
}

function riskColor(value: number): string {
  return riskStyle(value).color;
}

function confidenceColor(value: number): string {
  return confidenceStyle(value).color;
}

function label(value: number): string {
  if (value >= 0.7) return "high";
  if (value >= 0.4) return "med";
  return "low";
}

const pill = (bg: string, fg: string) =>
  ({
    background: bg,
    color: fg,
    padding: "3px 10px",
    borderRadius: "12px",
    fontSize: "11px",
    fontWeight: 500,
    display: "inline-block",
    whiteSpace: "nowrap" as const,
  }) as const;

export function AreaLozenge({ area }: { area: Area }) {
  const s = AREA_STYLES[area] || AREA_STYLES.application;
  return <span style={pill(s.bg, s.color)}>{area}</span>;
}

export function RiskLozenge({ value }: { value: number }) {
  const s = riskStyle(value);
  return <span style={pill(s.bg, s.color)}>{label(value)} {value.toFixed(1)}</span>;
}

export function ConfidenceLozenge({ value }: { value: number }) {
  const s = confidenceStyle(value);
  return <span style={pill(s.bg, s.color)}>{label(value)} {value.toFixed(1)}</span>;
}

const STAGE_STYLES: Record<string, { bg: string; color: string }> = {
  dev: { bg: "#f0fdf4", color: "#16a34a" },
  test: { bg: "#fffbeb", color: "#d97706" },
  production: { bg: "#fef2f2", color: "#dc2626" },
  unknown: { bg: "#f1f5f9", color: "#6b7280" },
};

export function StageLozenge({ stage }: { stage: string }) {
  const s = STAGE_STYLES[stage] || STAGE_STYLES.unknown;
  return <span style={pill(s.bg, s.color)}>{stage}</span>;
}

const STATUS_STYLES: Record<string, { bg: string; color: string }> = {
  open: { bg: "#fef2f2", color: "#dc2626" },
  acknowledged: { bg: "#fffbeb", color: "#d97706" },
  in_progress: { bg: "#eff6ff", color: "#2563eb" },
  resolved: { bg: "#f0fdf4", color: "#16a34a" },
  closed: { bg: "#f1f5f9", color: "#6b7280" },
};

export function StatusLozenge({ status }: { status: string }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.open;
  return <span style={pill(s.bg, s.color)}>{status.replace("_", " ")}</span>;
}

export { riskColor, confidenceColor, label as valueLabel };

interface EditableLozengeProps {
  value: number;
  onClick: () => void;
}

export function EditableRiskLozenge({ value, onClick }: EditableLozengeProps) {
  const s = riskStyle(value);
  return (
    <span onClick={onClick} style={{ ...pill(s.bg, s.color), cursor: "pointer" }} title="Click to edit risk">
      {label(value)} {value.toFixed(1)} &#9998;
    </span>
  );
}

export function EditableConfidenceLozenge({ value, onClick }: EditableLozengeProps) {
  const s = confidenceStyle(value);
  return (
    <span onClick={onClick} style={{ ...pill(s.bg, s.color), cursor: "pointer" }} title="Click to edit confidence">
      {label(value)} {value.toFixed(1)} &#9998;
    </span>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira/frontend && npm run build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira
git add frontend/src/components/Lozenge.tsx
git commit -m "feat(frontend): tinted pill badges for lozenges"
```

---

### Task 4: Chat Widget — Navy FAB

**Files:**
- Modify: `frontend/src/components/ChatWidget.tsx`

- [ ] **Step 1: Update ChatWidget styles**

Changes to make (inline edits, not full rewrite):

1. **FAB button** (the `!open` branch, ~line 143-166): Change `background` from `"var(--kira-accent)"` to `"#1e3a5f"`, change `boxShadow` from `"0 4px 12px rgba(0,0,0,0.3)"` to `"0 4px 12px rgba(30,58,95,0.3)"`.

2. **Chat container** (~line 170-184): Change `boxShadow` from `"0 8px 24px rgba(0,0,0,0.4)"` to `"0 8px 24px rgba(0,0,0,0.12)"`, change `borderRadius` from `"8px"` to `"12px"`.

3. **Header** (~line 187-196): Change background to `"#1e3a5f"`, remove `borderBottom`. Update text color in header to `"white"`. Update model select border to `"1px solid rgba(255,255,255,0.2)"`, background `"rgba(255,255,255,0.1)"`, color `"rgba(255,255,255,0.8)"`.

4. **"ticket context" badge** (~line 228-233): Change background to `"rgba(255,255,255,0.2)"`.

5. **Header buttons** (clear context, clear history ~line 244-269): Change border to `"1px solid rgba(255,255,255,0.2)"`, color to `"rgba(255,255,255,0.7)"`.

6. **Minimize button** (~line 271-282): Change color to `"rgba(255,255,255,0.7)"`.

7. **User message bubbles** (~line 319-326): Change `background` for user role to `"#1e3a5f"`, keep assistant as `"var(--kira-bg-input)"` which is now `#ffffff` — change to `"#f1f5f9"`. Change `borderRadius` for user to `"8px 8px 2px 8px"`, for assistant to `"8px 8px 8px 2px"`.

8. **Send button** (~line 365-376): Change the enabled background from `"var(--kira-accent)"` to `"#1e3a5f"`, change `borderRadius` to `"6px"`.

9. **Input** (~line 347-362): Change `borderRadius` to `"6px"`.

- [ ] **Step 2: Verify build**

Run: `cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira/frontend && npm run build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira
git add frontend/src/components/ChatWidget.tsx
git commit -m "feat(frontend): navy FAB and chat panel styling"
```

---

### Task 5: Small Components

**Files:**
- Modify: `frontend/src/components/SkillTag.tsx`
- Modify: `frontend/src/components/ValueEditDialog.tsx`
- Modify: `frontend/src/components/IssueCard.tsx`

- [ ] **Step 1: Update SkillTag.tsx — pill style**

Replace the span style object:

```typescript
style={{
  background: "#f1f5f9",
  color: "#475569",
  padding: "2px 8px",
  borderRadius: "12px",
  fontSize: "10px",
  fontWeight: 500,
  display: "inline-flex",
  alignItems: "center",
  gap: "3px",
  whiteSpace: "nowrap",
  border: "1px solid #e2e8f0",
}}
```

- [ ] **Step 2: Update ValueEditDialog.tsx**

Changes:
1. Dialog `boxShadow`: change to `"0 8px 24px rgba(0,0,0,0.12)"`, `borderRadius` to `"12px"`
2. Preview lozenge (~line 73-81): replace `background: colorFn(value)` + `color: "white"` with tinted pill style. Import `riskStyle`/`confidenceStyle` from Lozenge if needed, or duplicate the logic inline since the dialog already has its own `riskColor`/`confidenceColor`. Simplest: just leave the preview lozenge as-is (it shows the color well) but update `borderRadius` to `"12px"`.
3. Cancel button: already uses CSS vars, which now map to the new palette — no changes needed.
4. Save button: already uses `var(--kira-accent)` — now resolves to `#1e3a5f`. Fine.
5. Textarea `borderRadius`: change from `"4px"` to `"6px"`.

- [ ] **Step 3: Update IssueCard.tsx — tinted severity badges, card shadow**

Changes:
1. `SEVERITY_COLORS` stays as-is (the colors are still used for left-border accent).
2. `STATUS_COLORS` stays as-is.
3. Outer card div: add `boxShadow: "0 1px 2px rgba(0,0,0,0.05)"`, change `borderRadius` from `"6px"` to `"8px"`.
4. Severity badge (~line 78-87): change from solid `background: SEVERITY_COLORS[issue.severity]` + `color: "white"` to tinted style. Add a new map:

```typescript
const SEVERITY_TINTS: Record<Severity, { bg: string; color: string }> = {
  critical: { bg: "#fef2f2", color: "#dc2626" },
  high: { bg: "#fff7ed", color: "#ea580c" },
  medium: { bg: "#fffbeb", color: "#d97706" },
  low: { bg: "#eff6ff", color: "#2563eb" },
  info: { bg: "#f1f5f9", color: "#6b7280" },
};
```

Then update the badge to: `background: SEVERITY_TINTS[issue.severity].bg`, `color: SEVERITY_TINTS[issue.severity].color`, `borderRadius: "12px"`.

5. Status badge (~line 116-125): already uses tinted style (`${STATUS_COLORS[issue.status]}22`). Change `borderRadius` to `"12px"`.

6. "Add to Backlog" button (~line 266-275): change `background` from `"#8b5cf6"` to `"var(--kira-accent)"`, `borderRadius` to `"6px"`.

7. "Promote" button (~line 395-407): change `background` from `"#8b5cf6"` to `"var(--kira-accent)"`, `borderRadius` to `"6px"`.

- [ ] **Step 4: Verify build**

Run: `cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira/frontend && npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira
git add frontend/src/components/SkillTag.tsx frontend/src/components/ValueEditDialog.tsx frontend/src/components/IssueCard.tsx
git commit -m "feat(frontend): update small components to new palette"
```

---

### Task 6: Pages — Dashboard, Lists, Login

**Files:**
- Modify: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/pages/TicketList.tsx`
- Modify: `frontend/src/pages/IssueList.tsx`

- [ ] **Step 1: Rewrite Login.tsx**

```typescript
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.login(username, password);
      navigate("/");
    } catch {
      setError("Invalid credentials");
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--kira-bg-page)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          background: "var(--kira-bg-card)",
          padding: "32px",
          borderRadius: "12px",
          width: "340px",
          boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
          border: "1px solid var(--kira-border)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
          <span style={{ fontSize: "20px", fontWeight: 700, color: "var(--kira-accent)" }}>Kira</span>
        </div>
        <h2 style={{ fontSize: "20px", fontWeight: 600, color: "var(--kira-text-primary)", marginBottom: "4px" }}>Sign In</h2>
        <p style={{ fontSize: "13px", color: "var(--kira-text-muted)", marginBottom: "20px" }}>
          Access your incident dashboard
        </p>
        {error && (
          <div style={{ color: "#dc2626", fontSize: "13px", marginBottom: "12px", textAlign: "center" }}>
            {error}
          </div>
        )}
        <div style={{ marginBottom: "12px" }}>
          <label style={{ fontSize: "12px", fontWeight: 500, color: "var(--kira-text-secondary)", display: "block", marginBottom: "4px" }}>
            Username
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            style={{
              width: "100%",
              padding: "10px",
              background: "var(--kira-bg-input)",
              border: "1px solid var(--kira-border)",
              borderRadius: "6px",
              color: "var(--kira-text-primary)",
              fontSize: "14px",
              boxSizing: "border-box",
            }}
          />
        </div>
        <div style={{ marginBottom: "20px" }}>
          <label style={{ fontSize: "12px", fontWeight: 500, color: "var(--kira-text-secondary)", display: "block", marginBottom: "4px" }}>
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{
              width: "100%",
              padding: "10px",
              background: "var(--kira-bg-input)",
              border: "1px solid var(--kira-border)",
              borderRadius: "6px",
              color: "var(--kira-text-primary)",
              fontSize: "14px",
              boxSizing: "border-box",
            }}
          />
        </div>
        <button
          type="submit"
          style={{
            width: "100%",
            padding: "10px",
            background: "var(--kira-btn-bg)",
            color: "var(--kira-btn-text)",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
            fontSize: "14px",
            fontWeight: 500,
          }}
        >
          Sign In
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Update Dashboard.tsx**

Changes:
1. Stat cards (~line 43-52): change `borderRadius` from `"6px"` to `"8px"`, add `boxShadow: "var(--kira-shadow-sm)"`, add `border: "1px solid var(--kira-border)"`, remove `borderLeft`.
2. Stat card colors: change `{ label: "Open", value: stats.open, color: "#ef4444" }` to `color: "#dc2626"`, `"In Progress"` from `"#f59e0b"` to `"#2563eb"`, `"Resolved"` from `"#22c55e"` to `"#16a34a"`.
3. Chart containers (~line 56, 67): change `borderRadius` from `"6px"` to `"8px"`, add `boxShadow: "var(--kira-shadow-sm)"`, add `border: "1px solid var(--kira-border)"`.
4. Recent tickets card (~line 84): change `borderRadius` to `"8px"`, add `boxShadow: "var(--kira-shadow-sm)"`, add `border: "1px solid var(--kira-border)"`.
5. Bar chart area chart: use area-specific colors per bar using `Cell` component. Replace the single `fill="var(--kira-accent)"` Bar with individual Cell fills. Add a mapping:

```typescript
const AREA_CHART_COLORS: Record<string, string> = {
  linux: "#7c3aed",
  kubernetes: "#2563eb",
  networking: "#0891b2",
  database: "#059669",
  storage: "#d97706",
  security: "#dc2626",
  application: "#6366f1",
};
```

Then update the Bar element for area chart to use Cell components like the risk chart already does.

- [ ] **Step 3: Update TicketList.tsx**

Changes:
1. Table wrapper (~line 68): add `border: "1px solid var(--kira-border)"`, change `borderRadius` to `"8px"`, add `boxShadow: "var(--kira-shadow-sm)"`.
2. Table header (~line 71): add `letterSpacing: "0.5px"`, add `fontWeight: 600`.
3. Filter selects (~line 42, 56): add `borderRadius: "6px"`, `fontSize: "12px"`.
4. Ticket number column: change `color` from `"var(--kira-text-muted)"` to `"var(--kira-accent)"`.

- [ ] **Step 4: Update IssueList.tsx with same table card pattern**

Same changes as TicketList: card wrapper with border/shadow/radius, table header letter-spacing, ticket number accent color.

- [ ] **Step 5: Verify build**

Run: `cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira/frontend && npm run build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira
git add frontend/src/pages/Login.tsx frontend/src/pages/Dashboard.tsx frontend/src/pages/TicketList.tsx frontend/src/pages/IssueList.tsx
git commit -m "feat(frontend): restyle pages — login card, dashboard stats, list tables"
```

---

### Task 7: Detail Pages & Workspace

**Files:**
- Modify: `frontend/src/pages/TicketDetail.tsx`
- Modify: `frontend/src/pages/IssueDetail.tsx`
- Modify: `frontend/src/pages/CreateTicket.tsx`
- Modify: `frontend/src/pages/Workspace.tsx`

- [ ] **Step 1: Update TicketDetail.tsx**

These are style-only changes — search for inline `style={{` objects and update:

1. Section containers (any `borderRadius: "6px"` + `var(--kira-bg-card)`): change to `borderRadius: "8px"`, add `boxShadow: "var(--kira-shadow-sm)"`, add `border: "1px solid var(--kira-border)"`.
2. Tab buttons: change active tab `borderBottom` color from `"var(--kira-accent)"` to `"var(--kira-nav-indicator)"` (which is `#cc0000`).
3. Recommended action section: keep the amber left-border as-is (it's a visual accent that still works).
4. Comment author badges: keep existing colors (agent blue, user purple) — they work well on white.
5. Terminal button: update `background` for selected state from `"#30363d"` to `"var(--kira-accent)"`, `color` from `"#58a6ff"` to `"white"`.

- [ ] **Step 2: Update IssueDetail.tsx**

Same pattern as TicketDetail: section containers get `borderRadius: "8px"`, `boxShadow`, `border`.

- [ ] **Step 3: Update CreateTicket.tsx**

1. Section containers: `borderRadius: "8px"`, add `boxShadow: "var(--kira-shadow-sm)"`, add `border: "1px solid var(--kira-border)"`.
2. Input/textarea: change `borderRadius` from `"4px"` to `"6px"`.
3. Labels: change `fontSize` from `"11px"` to `"12px"`, add `fontWeight: 500`, change `color` to `"var(--kira-text-secondary)"`.
4. Submit button: already uses `var(--kira-accent)` for background — now resolves to `#1e3a5f`. If it should be the red CTA, change to `var(--kira-btn-bg)`.

- [ ] **Step 4: Update Workspace.tsx**

1. Chat header area: if it has its own header styling, align with ChatWidget navy style.
2. Terminal drag handle: change `background` from `"#30363d"` to `"var(--kira-border)"`.
3. Any hardcoded dark colors in the chat portion should use the new palette.

- [ ] **Step 5: Verify build**

Run: `cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira/frontend && npm run build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira
git add frontend/src/pages/TicketDetail.tsx frontend/src/pages/IssueDetail.tsx frontend/src/pages/CreateTicket.tsx frontend/src/pages/Workspace.tsx
git commit -m "feat(frontend): restyle detail pages and workspace"
```

---

### Task 8: Build, Push, and Test

**Files:**
- None (deployment task)

- [ ] **Step 1: Run full build**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira/frontend && npm run build
```

Expected: Clean build, no errors.

- [ ] **Step 2: Test locally (optional)**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira/frontend && npm run dev
```

Open http://localhost:5173 and verify login, dashboard, ticket list, ticket detail pages render with the new palette.

- [ ] **Step 3: Build container image**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira
podman build --platform linux/amd64 -t quay.io/rhpds/kira-frontend:0.11.0 -f deploy/Dockerfile.frontend .
```

- [ ] **Step 4: Push image**

```bash
podman push quay.io/rhpds/kira-frontend:0.11.0
```

- [ ] **Step 5: Test on cluster**

```bash
oc login --insecure-skip-tls-verify=false --username admin --password 9coGueyOf5YAGwgC https://api.cluster-8vhnp.dyn.redhatworkshops.io:6443
oc project user-vqpz5
oc set image deployment/kira-frontend kira-frontend=quay.io/rhpds/kira-frontend:0.11.0
oc rollout status deployment/kira-frontend
```

Verify: open the Kira route in a browser and check login, dashboard, ticket list, ticket detail.

- [ ] **Step 6: Git push Kira changes**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/kira-jira-replacement-tok/kira
git push
```

---

### Task 9: AgnosticV Draft PR

**Files:**
- The integration CI in AgnosticV repo

- [ ] **Step 1: Clone AgnosticV and create branch**

```bash
cd /tmp
git clone https://github.com/rhpds/agnosticv.git agnosticv-kira-ui
cd agnosticv-kira-ui
git checkout -b feat/kira-frontend-0.11.0
```

- [ ] **Step 2: Find and update the integration CI**

Find the CI file for `summit-2026.lb2645-agentic-devops-tenant.dev` and update the Kira frontend image tag from the current version to `0.11.0`.

- [ ] **Step 3: Create draft PR**

```bash
gh pr create --draft --title "feat: Kira frontend 0.11.0 — UI overhaul" --body "$(cat <<'EOF'
## Summary

- Updates Kira frontend image to 0.11.0 in integration CI only
- Fed Aura-inspired redesign: navy header, clean white surfaces, tinted pill badges
- Production CI unchanged

## Test plan

- [ ] Deploy integration CI tenant
- [ ] Verify login page renders with new centered card design
- [ ] Verify dashboard stat cards and charts use new palette
- [ ] Verify ticket list shows tinted pill badges
- [ ] Verify chat widget has navy FAB
- [ ] Verify terminal panel still works

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Commit**

```bash
git push -u origin feat/kira-frontend-0.11.0
```

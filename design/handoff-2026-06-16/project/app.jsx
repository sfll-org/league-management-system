/* global window, React, ReactDOM, Icons */
// SFLL LMS — root app: shell, navigation, command palette, tweaks.

const { useState, useEffect, useRef, useMemo } = React;
const { Button, Pill } = window.UI;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "palette": "pacific",
  "type": "humanist-display",
  "density": "balanced",
  "nav": "sidebar"
}/*EDITMODE-END*/;

const PALETTE_OPTIONS = [
  ["#0F2A47", "#D14C3A", "#F8F5F0"], // pacific
  ["#1B2D55", "#CC2027", "#FCF8EF"], // civic
  ["#3F5168", "#C46A4B", "#F5F2EE"], // fog
  ["#0F1422", "#E0AC3A", "#1A1F2D"], // twilight
];

const ROUTES = [
  { name: "dashboard",  label: "Dashboard",  icon: "Dashboard" },
  { name: "roster",     label: "Roster",     icon: "Players",   count: 702 },
  { name: "family",     label: "Families",   icon: "Family",    id: "fam-hernandez" },
  { name: "ses",        label: "SES Sessions", icon: "Calendar" },
  { name: "draft",      label: "Draft",      icon: "Draft", dot: true },
  { name: "field",      label: "Phone",      icon: "Phone" },
  { name: "ipad",       label: "iPad",       icon: "Field" },
  { name: "print",      label: "Print",      icon: "Print" },
];

const ADMIN_ROUTES = [
  { name: "imports",    label: "Imports",     icon: "Imports" },
  { name: "compliance", label: "Compliance",  icon: "Compliance" },
  { name: "audit",      label: "Audit log",   icon: "Audit" },
  { name: "settings",   label: "Settings",    icon: "Settings" },
];

function App() {
  const [route, setRoute] = useState({ name: "dashboard" });
  const [cmdOpen, setCmdOpen] = useState(false);

  const [tweaks, setTweak] = window.useTweaks(TWEAK_DEFAULTS);

  // Apply tweaks → DOM
  useEffect(() => {
    document.documentElement.setAttribute("data-palette", tweaks.palette);
    document.documentElement.setAttribute("data-type", tweaks.type);
    document.documentElement.setAttribute("data-density", tweaks.density);
  }, [tweaks.palette, tweaks.type, tweaks.density]);

  // Keyboard: ⌘K
  useEffect(() => {
    function onKey(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdOpen(o => !o);
      }
      if (e.key === "Escape") setCmdOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function go(name, id) {
    setRoute({ name, id });
    setCmdOpen(false);
    const scroll = document.querySelector(".scroll");
    if (scroll) scroll.scrollTop = 0;
  }

  const currentScreen = useMemo(() => renderScreen(route, go), [route]);

  return (
    <div className="app-shell" data-nav={tweaks.nav}>
      {/* Sidebar */}
      <Sidebar route={route} go={go} setCmdOpen={setCmdOpen} />

      <div className="main">
        {/* Top nav (only when nav=top) */}
        <TopNav route={route} go={go} />

        {/* Top bar */}
        <div className="topbar">
          <Crumbs route={route} go={go} />
          <div className="search-omni" onClick={() => setCmdOpen(true)}>
            <Icons.Search size={13} />
            <span>Find a player, family, team…</span>
            <span className="search-omni__kbd">⌘K</span>
          </div>
          <button className="iconbtn" title="Help"><Icons.Info size={16} /></button>
          <button className="iconbtn" title="Notifications" style={{ position: "relative" }}>
            <Icons.Bell size={16} />
            <span style={{ position: "absolute", top: 5, right: 5, width: 7, height: 7, borderRadius: "50%", background: "var(--accent)" }}/>
          </button>
        </div>

        <div className="scroll">
          {currentScreen}
        </div>
      </div>

      {cmdOpen ? <CommandPalette go={go} close={() => setCmdOpen(false)} /> : null}

      <Tweaks tweaks={tweaks} setTweak={setTweak} />
    </div>
  );
}

function Sidebar({ route, go, setCmdOpen }) {
  return (
    <nav className="sidebar">
      <div className="sidebar__brand" onClick={() => go("dashboard")} style={{ cursor: "pointer" }}>
        <div className="brand-mark brand-mark--diamond" />
        <div className="sidebar__brand-text">
          <strong>SFLL</strong>
          <span>League Management</span>
        </div>
      </div>

      <button className="season-switch">
        <span className="season-switch__dot" />
        <div className="season-switch__label">
          <strong>Spring 2026</strong>
          <span>Active · 14 days to Opening Day</span>
        </div>
        <Icons.Caret size={12} className="season-switch__caret" />
      </button>

      <div className="nav-section">
        <div className="nav-section__title">Operations</div>
        {ROUTES.map(r => (
          <NavItem key={r.name} route={r} active={route.name === r.name} go={go} />
        ))}
      </div>

      <div className="nav-section">
        <div className="nav-section__title">Admin</div>
        {ADMIN_ROUTES.map(r => (
          <NavItem key={r.name} route={r} active={route.name === r.name} go={go} />
        ))}
      </div>

      <div className="sidebar__bottom">
        <button className="search-omni" style={{ width: "100%", marginBottom: 8 }} onClick={() => setCmdOpen(true)}>
          <Icons.Search size={13} />
          <span>Search</span>
          <span className="search-omni__kbd">⌘K</span>
        </button>
        <div className="user-chip">
          <div className="avatar avatar--sm" style={{ background: "var(--primary)", color: "var(--primary-ink)" }}>NP</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="user-chip__name">Nate Prodromou</div>
            <div className="user-chip__role">Operations Lead · CTO</div>
          </div>
          <Icons.Caret size={12} style={{ color: "var(--ink-3)" }} />
        </div>
      </div>
    </nav>
  );
}

function NavItem({ route: r, active, go }) {
  const Icon = Icons[r.icon];
  return (
    <div className={"nav-item " + (active ? "nav-item--active" : "")} onClick={() => go(r.name, r.id)}>
      <Icon size={15} className="nav-item__icon" />
      <span>{r.label}</span>
      {r.count ? <span className="nav-item__count">{r.count}</span> : null}
      {r.dot && !r.count ? <span className="nav-item__dot" /> : null}
    </div>
  );
}

function TopNav({ route, go }) {
  return (
    <nav className="topnav">
      <div className="brand-mark brand-mark--diamond" style={{ marginRight: 14 }} />
      {ROUTES.map(r => {
        const Icon = Icons[r.icon];
        return (
          <div key={r.name} className={"nav-item " + (route.name === r.name ? "nav-item--active" : "")} onClick={() => go(r.name, r.id)}>
            <Icon size={14} className="nav-item__icon" />
            <span>{r.label}</span>
          </div>
        );
      })}
    </nav>
  );
}

function Crumbs({ route, go }) {
  const labels = {
    dashboard: "Dashboard", roster: "Roster", player: "Player", family: "Family",
    ses: "SES Session", draft: "Draft", field: "Phone views", ipad: "iPad views", print: "Print",
    imports: "Imports", compliance: "Compliance", audit: "Audit log", settings: "Settings",
    comms: "Communications",
  };
  return (
    <div className="crumbs">
      <span style={{ cursor: "pointer" }} onClick={() => go("dashboard")}>SFLL</span>
      <span className="crumbs__sep">/</span>
      <strong>{labels[route.name] || route.name}</strong>
    </div>
  );
}

function renderScreen(route, go) {
  switch (route.name) {
    case "dashboard": return <window.Dashboard go={go} />;
    case "roster":    return <window.Roster go={go} divisionId={route.id} />;
    case "player":    return <window.PlayerDetail go={go} playerId={route.id} />;
    case "family":    return <window.FamilyDetail go={go} familyId={route.id} />;
    case "ses":       return <window.SES go={go} sessionId={route.id} />;
    case "draft":     return <window.Draft go={go} />;
    case "field":     return <window.FieldMode go={go} />;
    case "ipad":      return <window.IPad go={go} />;
    case "print":     return <window.Print go={go} />;
    default:
      return <StubScreen route={route} go={go} />;
  }
}

function StubScreen({ route, go }) {
  const labels = {
    imports: ["Imports", "SportsConnect sync history. Last run 1h ago — 14 new players, 3 flagged."],
    compliance: ["Compliance", "Background checks, concussion certs, coach training, mandated reporter. Lives here, surfaces only when something breaks."],
    audit: ["Audit log", "Every change, who made it, what changed. Volunteers churn — this is how we keep memory."],
    settings: ["Settings", "Division config, evaluation stations, role assignments, SportsConnect URL."],
    comms: ["Communications", "Email blast composer, RSVP tracking, snack-stand schedule."],
  };
  const [title, sub] = labels[route.name] || ["Stub", ""];
  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">{title}</h1>
          <div className="page-sub">{sub}</div>
        </div>
      </div>
      <div className="empty" style={{ background: "var(--surface)", borderRadius: "var(--radius)", border: "1px dashed var(--border-2)", padding: 60 }}>
        <strong>Not designed yet.</strong>
        On the priority list for the next pass. Try the dashboard, roster, player detail, draft board, or field mode.
        <div style={{ marginTop: 14 }}>
          <Button variant="primary" onClick={() => go("dashboard")}>← Back to dashboard</Button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────── Command Palette ───────────────────────

function CommandPalette({ go, close }) {
  const [q, setQ] = useState("");
  const inputRef = useRef(null);
  useEffect(() => { inputRef.current?.focus(); }, []);

  const { PLAYERS, FAMILIES, TEAMS, SESSIONS } = window.SFLL_DATA;

  const items = useMemo(() => {
    const qq = q.toLowerCase().trim();
    const groups = [
      {
        title: "Go to",
        items: [
          { kind: "page", id: "dashboard", label: "Dashboard", icon: "Dashboard" },
          { kind: "page", id: "roster",    label: "Roster",    icon: "Players" },
          { kind: "page", id: "draft",     label: "Draft Board", icon: "Draft" },
          { kind: "page", id: "ses",       label: "SES Sessions", icon: "Calendar" },
          { kind: "page", id: "field",     label: "Phone views (coach + parent)", icon: "Phone" },
          { kind: "page", id: "ipad",      label: "iPad views (check-in + draft)", icon: "Field" },
          { kind: "page", id: "print",     label: "Print dugout cards", icon: "Print" },
          { kind: "page", id: "compliance",label: "Compliance",   icon: "Compliance" },
          { kind: "page", id: "imports",   label: "Imports",      icon: "Imports" },
        ],
      },
      {
        title: "Players",
        items: PLAYERS.slice(0,40).map(p => ({
          kind: "player", id: p.id,
          label: `${p.first} ${p.last}`,
          sub: `${p.positions.join("/")}  · #${p.topRank} · ${(TEAMS.find(t => t.id === p.team) || {}).name || "Unassigned"}`,
          icon: "Players",
        })),
      },
      {
        title: "Families",
        items: Object.values(FAMILIES).map(f => ({
          kind: "family", id: f.id, label: `The ${f.surname} family`, sub: f.neighborhood, icon: "Family",
        })),
      },
      {
        title: "Actions",
        items: [
          { kind: "action", id: "new-season",   label: "Start new season…", icon: "Plus" },
          { kind: "action", id: "import",       label: "Run SportsConnect import", icon: "Imports" },
          { kind: "action", id: "email-noshow", label: "Email no-shows from last SES", icon: "Mail" },
        ],
      },
    ];
    if (!qq) return groups;
    return groups
      .map(g => ({ ...g, items: g.items.filter(i => (i.label + " " + (i.sub||"")).toLowerCase().includes(qq)) }))
      .filter(g => g.items.length > 0);
  }, [q]);

  const flat = useMemo(() => items.flatMap(g => g.items), [items]);
  const [active, setActive] = useState(0);
  useEffect(() => { setActive(0); }, [q]);

  function handleSelect(it) {
    if (it.kind === "page") go(it.id);
    else if (it.kind === "player") go("player", it.id);
    else if (it.kind === "family") go("family", it.id);
    else close();
  }

  function onKeyDown(e) {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive(a => Math.min(flat.length - 1, a + 1)); }
    if (e.key === "ArrowUp")   { e.preventDefault(); setActive(a => Math.max(0, a - 1)); }
    if (e.key === "Enter")     { e.preventDefault(); if (flat[active]) handleSelect(flat[active]); }
  }

  return (
    <div className="cmdk-backdrop" onClick={close}>
      <div className="cmdk" onClick={e => e.stopPropagation()}>
        <input
          ref={inputRef}
          className="cmdk__input"
          placeholder="Type a player, family, team, or command…"
          value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="cmdk__results">
          {flat.length === 0 ? (
            <div className="cmdk__empty">No match. Try "Mendoza", "draft", or "Hernández".</div>
          ) : items.map((g, gi) => (
            <div key={gi}>
              <div className="cmdk__section-title">{g.title}</div>
              {g.items.map(it => {
                const flatIdx = flat.indexOf(it);
                const Icon = Icons[it.icon] || Icons.Search;
                return (
                  <div
                    key={it.id}
                    className={"cmdk__item " + (flatIdx === active ? "cmdk__item--active" : "")}
                    onMouseEnter={() => setActive(flatIdx)}
                    onClick={() => handleSelect(it)}
                  >
                    <Icon size={14} style={{ color: "var(--ink-3)" }} />
                    <span>{it.label}</span>
                    {it.sub ? <span className="text-xs text-muted" style={{ marginLeft: 6 }}>{it.sub}</span> : null}
                    {flatIdx === active ? <span className="cmdk__item__kbd">↵</span> : null}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────── Tweaks panel ───────────────────────

function Tweaks({ tweaks, setTweak }) {
  const { TweaksPanel, TweakSection, TweakColor, TweakRadio, TweakSelect } = window;
  const currentPalette = PALETTE_OPTIONS.find(o => paletteKey(o) === tweaks.palette) || PALETTE_OPTIONS[0];
  return (
    <TweaksPanel>
      <TweakSection label="Palette" />
      <TweakColor
        label="Theme"
        value={currentPalette}
        options={PALETTE_OPTIONS}
        onChange={(v) => setTweak("palette", paletteKey(v))}
      />
      <TweakSection label="Type" />
      <TweakSelect
        label="Family"
        value={tweaks.type}
        options={[
          { value: "humanist-display", label: "Humanist + display" },
          { value: "humanist-plain",   label: "Humanist (plain)" },
          { value: "geometric",        label: "Geometric" },
          { value: "editorial",        label: "Editorial (serif display)" },
        ]}
        onChange={(v) => setTweak("type", v)}
      />
      <TweakSection label="Density" />
      <TweakRadio
        label="Rows"
        value={tweaks.density}
        options={[
          { value: "compact",  label: "Compact" },
          { value: "balanced", label: "Balanced" },
          { value: "airy",     label: "Airy" },
        ]}
        onChange={(v) => setTweak("density", v)}
      />
      <TweakSection label="Navigation" />
      <TweakRadio
        label="Chrome"
        value={tweaks.nav}
        options={[
          { value: "sidebar", label: "Sidebar" },
          { value: "top",     label: "Top" },
          { value: "cmd",     label: "⌘K" },
        ]}
        onChange={(v) => setTweak("nav", v)}
      />
    </TweaksPanel>
  );
}

const PALETTE_KEYS = ["pacific","civic","fog","twilight"];
function paletteKey(arr) {
  const i = PALETTE_OPTIONS.findIndex(o => o[0] === arr[0]);
  return PALETTE_KEYS[i >= 0 ? i : 0];
}

window.SFLLApp = App;

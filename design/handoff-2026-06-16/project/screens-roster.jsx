/* global window, React, Icons */
// Roster (player list) + Player detail.

const { useState, useMemo } = React;
const { Avatar, TeamSwatch, Pill, Button, Card, Chip, SearchInput, EditableText, EditableSelect } = window.UI;

function Roster({ go, divisionId }) {
  const { PLAYERS, DIVISIONS, TEAMS } = window.SFLL_DATA;
  const [q, setQ] = useState("");
  const [div, setDiv] = useState(divisionId || "majors");
  const [team, setTeam] = useState("all");
  const [sub, setSub] = useState("all");
  const [showFilters, setShowFilters] = useState(true);
  const [showTop4Only, setShowTop4Only] = useState(false);

  const division = DIVISIONS.find(d => d.id === div);

  const rows = useMemo(() => {
    let list = PLAYERS.filter(p => p.division === div);
    if (q) {
      const qq = q.toLowerCase();
      list = list.filter(p =>
        p.first.toLowerCase().includes(qq) ||
        p.last.toLowerCase().includes(qq) ||
        (p.positions || []).some(pos => pos.toLowerCase().includes(qq))
      );
    }
    if (team !== "all") list = list.filter(p => p.team === team || (team === "unassigned" && !p.team));
    if (sub !== "all") list = list.filter(p => p.sub === sub);
    if (showTop4Only) list = list.filter(p => p.top4);
    return list.sort((a,b) => a.last.localeCompare(b.last));
  }, [q, div, team, sub, showTop4Only, PLAYERS]);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Roster</h1>
          <div className="page-sub">{division ? `${division.name} · ${division.ages}` : "All divisions"} · {rows.length} players shown</div>
        </div>
        <div className="page-header__actions">
          <Button variant="ghost" leadingIcon={Icons.Print} onClick={() => go("print")}>Dugout cards</Button>
          <Button variant="ghost" leadingIcon={Icons.Imports}>Export CSV</Button>
          <Button variant="primary" leadingIcon={Icons.Plus}>Add player</Button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="toolbar">
        <div className="toolbar__search">
          <SearchInput value={q} onChange={setQ} placeholder="Search players by name or position…" />
        </div>
        <Button variant="ghost" leadingIcon={Icons.Filter} onClick={() => setShowFilters(!showFilters)}>
          {showFilters ? "Hide filters" : "Filters"}
        </Button>
        <div style={{ marginLeft: "auto" }}>
          <div className="seg">
            <button className="seg__btn seg__btn--active">List</button>
            <button className="seg__btn">By team</button>
            <button className="seg__btn">By family</button>
          </div>
        </div>
      </div>

      {showFilters ? (
        <div className="toolbar" style={{ marginBottom: 18, gap: 6 }}>
          <span className="text-xs text-muted" style={{ marginRight: 6 }}>Division</span>
          {DIVISIONS.map(d => (
            <Chip key={d.id} active={div === d.id} onClick={() => setDiv(d.id)}>{d.name}</Chip>
          ))}
          <span style={{ width: 16 }} />
          <span className="text-xs text-muted" style={{ marginRight: 6 }}>Sub-league</span>
          <Chip active={sub === "all"} onClick={() => setSub("all")}>All</Chip>
          <Chip active={sub === "American"} onClick={() => setSub("American")}>American</Chip>
          <Chip active={sub === "National"} onClick={() => setSub("National")}>National</Chip>
          <span style={{ width: 16 }} />
          <Chip active={showTop4Only} onClick={() => setShowTop4Only(!showTop4Only)}>
            Top-4 only
          </Chip>
          <Chip active={team === "unassigned"} onClick={() => setTeam(team === "unassigned" ? "all" : "unassigned")}>
            Unassigned
          </Chip>
        </div>
      ) : null}

      {/* Table */}
      <Card padding={false}>
        <table className="table table--clickable">
          <thead>
            <tr>
              <th style={{ width: 28 }}></th>
              <th>Player</th>
              <th style={{ width: 64 }} className="col-num">Age</th>
              <th>Positions</th>
              <th>B / T</th>
              <th>Team</th>
              <th>Sub-league</th>
              <th>Status</th>
              <th className="col-num">Rank</th>
              <th className="col-actions"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(p => (
              <tr key={p.id} onClick={() => go("player", p.id)}>
                <td><Avatar player={p} size="sm" /></td>
                <td>
                  <div className="player-cell">
                    <div>
                      <div className="player-cell__name">
                        {p.first} {p.last}
                        {p.top4 ? <span style={{ color: "var(--accent)", marginLeft: 6 }} title="Top-4 protected"><Icons.Top4 size={12} /></span> : null}
                        {p.coachChild ? <span style={{ color: "var(--ink-3)", marginLeft: 4 }} title="Coach's child"><Icons.Coach size={12} /></span> : null}
                      </div>
                      <div className="player-cell__sub">DOB {p.dob}</div>
                    </div>
                  </div>
                </td>
                <td className="col-num">{p.age}</td>
                <td className="text-sm text-muted">{p.positions.join(" · ")}</td>
                <td className="text-sm mono">{p.bats}/{p.throws}</td>
                <td>
                  {p.team
                    ? <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
                        <TeamSwatch teamId={p.team} size="sm" />
                        {(TEAMS.find(t => t.id === p.team) || {}).name}
                      </span>
                    : <span className="text-muted">—</span>}
                </td>
                <td className="text-sm text-muted">{p.sub}</td>
                <td>
                  {p.status === "active" ? <Pill kind="success" dot>Active</Pill>
                  : p.status === "unassigned" ? <Pill kind="warn" dot>Unassigned</Pill>
                  : <Pill kind="neutral">{p.status}</Pill>}
                </td>
                <td className="col-num text-muted">
                  {p.topRank ? <span style={{ fontWeight: 600, color: p.topRank <= 4 ? "var(--accent)" : "var(--ink-2)" }}>#{p.topRank}</span> : "—"}
                </td>
                <td className="col-actions">
                  <Icons.Chevron size={14} style={{ color: "var(--ink-4)" }} />
                </td>
              </tr>
            ))}
            {rows.length === 0 ? (
              <tr><td colSpan={10}>
                <div className="empty"><strong>No players match.</strong>Try clearing a filter or two.</div>
              </td></tr>
            ) : null}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

// ─────────────────────── Player detail ───────────────────────

function PlayerDetail({ go, playerId }) {
  const { PLAYERS, TEAMS, FAMILIES, DIVISIONS } = window.SFLL_DATA;
  const initial = PLAYERS.find(p => p.id === playerId) || PLAYERS[0];
  const [p, setP] = useState(initial);
  const [activeTab, setActiveTab] = useState("overview");
  const family = Object.values(FAMILIES).find(f => f.players.includes(p.id));
  const team = TEAMS.find(t => t.id === p.team);

  const update = (patch) => setP({ ...p, ...patch });

  return (
    <div className="page">
      <div style={{ marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
        <button className="btn btn--ghost btn--sm" onClick={() => go("roster", p.division)}>
          <Icons.ArrowLeft size={14} /> Roster
        </button>
        <span style={{ color: "var(--ink-4)" }}>/</span>
        <span className="text-sm text-muted">{DIVISIONS.find(d => d.id === p.division)?.name}</span>
      </div>

      <div className="page-header" style={{ alignItems: "center" }}>
        <Avatar player={p} size="xl" />
        <div style={{ marginLeft: 14 }}>
          <h1 className="page-title">
            <EditableText value={p.first} onChange={v => update({ first: v })} />{" "}
            <EditableText value={p.last} onChange={v => update({ last: v })} />
          </h1>
          <div className="page-sub" style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 6 }}>
            <span>Age {p.age} · {DIVISIONS.find(d => d.id === p.division)?.name} · #{p.jersey ?? "—"}</span>
            {p.top4 ? <Pill kind="danger" icon={<Icons.Top4 size={11} />}>Top-4 protected</Pill> : null}
            {p.coachChild ? <Pill kind="primary" icon={<Icons.Coach size={11} />}>Coach's child</Pill> : null}
            {team ? <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <TeamSwatch teamId={team.id} size="sm" /> {team.name}
            </span> : <Pill kind="warn">No team</Pill>}
          </div>
        </div>
        <div className="page-header__actions">
          <Button variant="ghost" leadingIcon={Icons.Mail}>Email family</Button>
          <Button variant="ghost" leadingIcon={Icons.Print}>Print card</Button>
          <Button variant="primary" leadingIcon={Icons.Edit}>Edit registration</Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {[
          { v: "overview", label: "Overview" },
          { v: "season",   label: "Season" },
          { v: "evals",    label: "Evaluations · 4" },
          { v: "history",  label: "History" },
          { v: "audit",    label: "Audit log" },
        ].map(t => (
          <div key={t.v} className={"tab " + (activeTab === t.v ? "tab--active" : "")} onClick={() => setActiveTab(t.v)}>
            {t.label}
          </div>
        ))}
      </div>

      {activeTab === "overview" ? (
        <div className="detail-grid">
          <div>
            <Card title="Player">
              <div className="detail-row">
                <div className="detail-row__label">First name</div>
                <div className="detail-row__value">
                  <EditableText value={p.first} onChange={v => update({ first: v })} />
                </div>
              </div>
              <div className="detail-row">
                <div className="detail-row__label">Last name</div>
                <div className="detail-row__value">
                  <EditableText value={p.last} onChange={v => update({ last: v })} />
                </div>
              </div>
              <div className="detail-row">
                <div className="detail-row__label">Date of birth</div>
                <div className="detail-row__value">
                  <EditableText type="date" value={p.dob} onChange={v => update({ dob: v })} suffix={`(${p.age})`} />
                </div>
              </div>
              <div className="detail-row">
                <div className="detail-row__label">Jersey #</div>
                <div className="detail-row__value">
                  <EditableText type="number" value={p.jersey || ""} onChange={v => update({ jersey: parseInt(v) || null })} placeholder="assign on draft" />
                </div>
              </div>
              <div className="detail-row">
                <div className="detail-row__label">Bats</div>
                <div className="detail-row__value">
                  <EditableSelect value={p.bats} onChange={v => update({ bats: v })} options={[
                    { value: "R", label: "Right" }, { value: "L", label: "Left" }, { value: "S", label: "Switch" }
                  ]} />
                </div>
              </div>
              <div className="detail-row">
                <div className="detail-row__label">Throws</div>
                <div className="detail-row__value">
                  <EditableSelect value={p.throws} onChange={v => update({ throws: v })} options={[
                    { value: "R", label: "Right" }, { value: "L", label: "Left" }
                  ]} />
                </div>
              </div>
              <div className="detail-row">
                <div className="detail-row__label">Positions</div>
                <div className="detail-row__value">{p.positions.join(", ")}</div>
              </div>
              <div className="detail-row">
                <div className="detail-row__label">SportsConnect ID</div>
                <div className="detail-row__value mono text-muted">SC-{10000 + parseInt(p.id.slice(1))}</div>
              </div>
            </Card>

            <div style={{ height: "var(--gap-lg)" }} />

            <Card title="This season" sub="Spring 2026">
              <div className="detail-row">
                <div className="detail-row__label">Division</div>
                <div className="detail-row__value">
                  <EditableSelect value={p.division} onChange={v => update({ division: v })}
                    options={DIVISIONS.map(d => ({ value: d.id, label: d.name }))} />
                </div>
              </div>
              <div className="detail-row">
                <div className="detail-row__label">Sub-league</div>
                <div className="detail-row__value">
                  <EditableSelect value={p.sub} onChange={v => update({ sub: v })}
                    options={[{value:"American",label:"American"},{value:"National",label:"National"}]} />
                </div>
              </div>
              <div className="detail-row">
                <div className="detail-row__label">Team</div>
                <div className="detail-row__value">
                  <EditableSelect value={p.team || ""} onChange={v => update({ team: v || null })}
                    options={[{value:"",label:"— Unassigned —"}, ...TEAMS.filter(t => t.subLeague === p.sub).map(t => ({ value: t.id, label: t.name }))]} />
                </div>
              </div>
              <div className="detail-row">
                <div className="detail-row__label">Top-4</div>
                <div className="detail-row__value">
                  <label style={{ display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
                    <input type="checkbox" checked={p.top4} onChange={e => update({ top4: e.target.checked })} />
                    <span>{p.top4 ? "Yes — protected" : "No"}</span>
                  </label>
                </div>
              </div>
              <div className="detail-row">
                <div className="detail-row__label">Coach's child</div>
                <div className="detail-row__value">
                  <label style={{ display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
                    <input type="checkbox" checked={p.coachChild} onChange={e => update({ coachChild: e.target.checked })} />
                    <span>{p.coachChild ? "Linked to coach" : "No"}</span>
                  </label>
                </div>
              </div>
              <div className="detail-row">
                <div className="detail-row__label">Draft rank</div>
                <div className="detail-row__value">
                  <span style={{ fontWeight: 600, color: p.topRank <= 4 ? "var(--accent)" : "var(--ink)", fontFamily: "var(--font-num)" }}>
                    #{p.topRank}
                  </span>
                  <span style={{ color: "var(--ink-3)", marginLeft: 8 }}>of 132 in division</span>
                </div>
              </div>
            </Card>
          </div>

          {/* Right column */}
          <div className="flex-col" style={{ gap: "var(--gap-lg)" }}>
            <Card title="Family" action={family ? <Button size="sm" variant="ghost" icon={Icons.Chevron} onClick={() => go("family", family.id)}>Open</Button> : null}>
              {family ? (
                <div>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>{family.surname}</div>
                  <div className="text-muted text-sm mb-2">{family.neighborhood} · {family.address.split(",")[0]}</div>
                  <div className="detail-row" style={{ borderTop: 0, padding: "6px 0" }}>
                    <div className="detail-row__label">Primary</div>
                    <div className="detail-row__value text-sm">{family.primary}</div>
                  </div>
                  <div className="detail-row" style={{ padding: "6px 0" }}>
                    <div className="detail-row__label">Phone</div>
                    <div className="detail-row__value text-sm mono">{family.phone}</div>
                  </div>
                  <div className="detail-row" style={{ padding: "6px 0" }}>
                    <div className="detail-row__label">Email</div>
                    <div className="detail-row__value text-sm">{family.email}</div>
                  </div>
                  <div className="detail-row" style={{ padding: "6px 0" }}>
                    <div className="detail-row__label">Balance</div>
                    <div className="detail-row__value">
                      {family.balance === 0
                        ? <Pill kind="success">Paid in full</Pill>
                        : family.balance < 0
                          ? <Pill kind="warn">${Math.abs(family.balance)} credit</Pill>
                          : <Pill kind="danger">${family.balance} due</Pill>}
                    </div>
                  </div>
                </div>
              ) : <div className="empty"><strong>No family linked.</strong>Add one via SportsConnect import.</div>}
            </Card>

            <Card title="Recent activity" padding={false}>
              <div className="card__list">
                <div className="alert">
                  <div className="alert__icon alert__icon--success"><Icons.Check size={14} /></div>
                  <div className="alert__body">
                    <div className="alert__title">Checked in at Sunday SES</div>
                    <div className="alert__sub">Big Rec, 10:34 AM</div>
                  </div>
                  <div className="alert__meta">2d</div>
                </div>
                <div className="alert">
                  <div className="alert__icon alert__icon--info"><Icons.Eval size={14} /></div>
                  <div className="alert__body">
                    <div className="alert__title">4 evals submitted</div>
                    <div className="alert__sub">Coaches: Chen, Park, O'Brien, Tanaka</div>
                  </div>
                  <div className="alert__meta">2d</div>
                </div>
                <div className="alert">
                  <div className="alert__icon alert__icon--info"><Icons.Draft size={14} /></div>
                  <div className="alert__body">
                    <div className="alert__title">Drafted by Giants</div>
                    <div className="alert__sub">Round 1, pick #3 · Wei Chen</div>
                  </div>
                  <div className="alert__meta">6d</div>
                </div>
                <div className="alert">
                  <div className="alert__icon alert__icon--info"><Icons.Imports size={14} /></div>
                  <div className="alert__body">
                    <div className="alert__title">Imported from SportsConnect</div>
                    <div className="alert__sub">Order ORD-1001, fee paid</div>
                  </div>
                  <div className="alert__meta">3w</div>
                </div>
              </div>
            </Card>

            <Card title="Hint" padding={true}>
              <p className="text-sm text-muted" style={{ margin: 0 }}>
                Any field with a soft outline on hover is <strong style={{ color: "var(--ink)" }}>inline-editable</strong>.
                Click → type → <kbd className="mono" style={{ padding: "1px 5px", background: "var(--bg-3)", borderRadius: 4 }}>Enter</kbd> to save.
                Changes are audited automatically.
              </p>
            </Card>
          </div>
        </div>
      ) : null}

      {activeTab === "evals" ? <EvalsTab player={p} /> : null}
      {activeTab !== "overview" && activeTab !== "evals" ? (
        <div className="empty">
          <strong>This tab is stubbed for the prototype.</strong>
          The real one shows {activeTab} for this player.
        </div>
      ) : null}
    </div>
  );
}

function EvalsTab({ player }) {
  const stations = window.SFLL_DATA.STATIONS;
  // Fabricated eval scores
  const seed = (player.topRank || 10);
  const score = (s) => Math.min(10, Math.max(2, 10 - seed * 0.18 + s * 0.4));
  return (
    <div className="detail-grid">
      <Card title="Coach evaluations" sub="4 of 4 submitted" padding={false}>
        <table className="table">
          <thead>
            <tr>
              <th>Station</th>
              {["Chen","Park","O'Brien","Tanaka"].map(c => <th key={c} className="col-num">{c}</th>)}
              <th className="col-num">Avg</th>
            </tr>
          </thead>
          <tbody>
            {stations.map((s, i) => {
              const scores = [score(i+0), score(i+1.2), score(i+0.8), score(i+1.5)];
              const avg = scores.reduce((a,b)=>a+b,0)/4;
              return (
                <tr key={s.id}>
                  <td><strong>{s.name}</strong> <span className="text-muted text-xs">{s.fields.join(" · ")}</span></td>
                  {scores.map((sc, j) => <td key={j} className="col-num tabular">{sc.toFixed(1)}</td>)}
                  <td className="col-num tabular" style={{ fontWeight: 700 }}>{avg.toFixed(1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
      <Card title="Composite">
        <div style={{ fontFamily: "var(--font-display)", fontSize: 56, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1 }}>
          {(10 - seed * 0.18 + 1.2).toFixed(1)}
        </div>
        <div className="text-muted text-sm mb-3">composite score</div>
        <div className="text-sm">Rank in division: <strong>#{player.topRank}</strong> of 132</div>
        <div className="text-sm text-muted mt-1">90th percentile · would be Top-4 if 4 weren't already taken.</div>
      </Card>
    </div>
  );
}

window.Roster = Roster;
window.PlayerDetail = PlayerDetail;

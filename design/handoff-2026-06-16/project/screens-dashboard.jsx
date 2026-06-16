/* global window, React, Icons */
// Operations dashboard — Nate's daily view.

const { useState } = React;
const { Avatar, TeamSwatch, Pill, Button, Card, Stat, Segmented, ComplianceBadge } = window.UI;

function Dashboard({ go }) {
  const { ATTENTION, DIVISIONS, SESSIONS, PLAYERS } = window.SFLL_DATA;
  const [filter, setFilter] = useState("all");

  const filteredAttention = ATTENTION.filter(a =>
    filter === "all" ? true :
    filter === "today" ? ["6d","2d","Thu","1h","now"].includes(a.meta) :
    a.level === filter
  );

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Good morning, Nate</h1>
          <div className="page-sub">Spring 2026 · 14 days until Opening Day · 8 things need a human</div>
        </div>
        <div className="page-header__actions">
          <Button variant="ghost" leadingIcon={Icons.Calendar}>This week</Button>
          <Button variant="primary" leadingIcon={Icons.Plus}>New season</Button>
        </div>
      </div>

      {/* Stat row */}
      <div className="stats">
        <Stat label="Registered players" value="702" delta="↑ 18 since Friday" deltaKind="up" />
        <Stat label="Unassigned" value="2" delta="Both Top-4. Probably not your fault." deltaKind="down" />
        <Stat label="Coach certs valid" value={<span>18<span style={{ color: "var(--ink-3)" }}>/24</span></span>} delta="6 to chase this week" deltaKind="flat" />
        <Stat label="SES completion" value="92%" delta="One makeup on Thu" deltaKind="up" />
      </div>

      <div className="dashboard-grid">
        {/* Attention inbox */}
        <div>
          <Card
            title="Needs attention"
            sub="this week"
            action={
              <Segmented
                value={filter}
                onChange={setFilter}
                options={[
                  { value: "all", label: "All" },
                  { value: "danger", label: "Blockers" },
                  { value: "warn", label: "Warnings" },
                  { value: "today", label: "Today" },
                ]}
              />
            }
            padding={false}
          >
            {filteredAttention.length === 0 ? (
              <div className="empty">
                <strong>Nothing in this bucket.</strong>
                Touch some grass.
              </div>
            ) : (
              <div className="card__list">
                {filteredAttention.map(a => (
                  <div key={a.id} className="alert" onClick={() => a.route && go(a.route.name, a.route.id)}>
                    <div className={"alert__icon alert__icon--" + a.level}>
                      {a.level === "danger" ? <Icons.Warn size={15} />
                       : a.level === "warn" ? <Icons.Bell size={15} />
                       : a.level === "success" ? <Icons.Check size={15} />
                       : <Icons.Info size={15} />}
                    </div>
                    <div className="alert__body">
                      <div className="alert__title">{a.title}</div>
                      <div className="alert__sub">{a.sub}</div>
                    </div>
                    <div className="alert__meta">{a.meta}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Division breakdown */}
          <div style={{ marginTop: "var(--gap-lg)" }}>
            <Card title="Divisions" sub="Spring 2026" padding={false}
              action={<Button size="sm" variant="ghost" icon={Icons.Chevron} onClick={() => go("roster")}>Open roster</Button>}
            >
              <table className="table table--clickable">
                <thead>
                  <tr>
                    <th>Division</th>
                    <th>Ages</th>
                    <th className="col-num">Players</th>
                    <th className="col-num">Teams</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {DIVISIONS.map(d => (
                  <tr key={d.id} onClick={() => go("roster", d.id)}>
                    <td>
                      <strong>{d.name}</strong>
                      {d.track !== "baseball" ? <span className="text-xs text-muted" style={{ marginLeft: 8, textTransform: "capitalize" }}>{d.track}</span> : null}
                    </td>
                      <td className="text-muted">{d.ages}</td>
                      <td className="col-num">{d.players}</td>
                      <td className="col-num">{d.teams}</td>
                      <td>{
                        d.id === "majors" ? <Pill kind="success" dot>Drafted</Pill>
                        : d.id === "aaa" ? <Pill kind="warn" dot>Drafting Tue</Pill>
                        : d.id === "aa" ? <Pill kind="warn" dot>Drafting Thu</Pill>
                        : d.id === "juniors" ? <Pill kind="success" dot>Drafted</Pill>
                        : d.id === "seniors" ? <Pill kind="success" dot>Drafted</Pill>
                        : d.id === "chall" ? <Pill kind="primary" dot>Buddies assigned</Pill>
                        : d.id === "softball" ? <Pill kind="warn" dot>Drafting Sat</Pill>
                        : <Pill kind="primary" dot>Registering</Pill>
                      }</td>
                      <td className="col-actions"><Icons.Chevron size={14} style={{ color: "var(--ink-3)" }} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>
        </div>

        {/* Right column */}
        <div className="flex-col" style={{ gap: "var(--gap-lg)" }}>
          <Card title="Up next" sub="SES sessions" padding={false}>
            <div className="card__list">
              {SESSIONS.slice(0,3).map(s => (
                <div key={s.id} className="alert" onClick={() => go("ses", s.id)}>
                  <div className="alert__icon alert__icon--info">
                    <Icons.Calendar size={14} />
                  </div>
                  <div className="alert__body">
                    <div className="alert__title">{s.name}</div>
                    <div className="alert__sub">{s.date} · {s.time} · {s.location}</div>
                  </div>
                  <div className="alert__meta tabular">{s.checkedIn}/{s.expected}</div>
                </div>
              ))}
            </div>
          </Card>

          <Card title="Top of the draft board" sub="Majors" padding={false}
            action={<Button size="sm" variant="ghost" icon={Icons.Chevron} onClick={() => go("draft")}>Open</Button>}
          >
            <div className="card__list">
              {PLAYERS.filter(p => p.topRank <= 4).sort((a,b) => a.topRank - b.topRank).map(p => (
                <div key={p.id} className="alert" style={{ padding: "10px 14px" }} onClick={() => go("player", p.id)}>
                  <div style={{ width: 30, textAlign: "center", fontFamily: "var(--font-num)", color: "var(--accent)", fontWeight: 700, fontSize: 14 }}>
                    #{p.topRank}
                  </div>
                  <div className="alert__body">
                    <div className="alert__title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      {p.first} {p.last}
                      {p.top4 ? <Pill kind="danger" icon={<Icons.Top4 size={11} />}>Top-4</Pill> : null}
                    </div>
                    <div className="alert__sub">{p.positions.join(" · ")} · Bats {p.bats}/Throws {p.throws}</div>
                  </div>
                  <TeamSwatch teamId={p.team} size="sm" />
                </div>
              ))}
            </div>
          </Card>

          <Card title="Recent imports" sub="SportsConnect" padding={false}>
            <div className="card__list">
              <div className="alert">
                <div className="alert__icon alert__icon--success"><Icons.Check size={14} /></div>
                <div className="alert__body">
                  <div className="alert__title">Auto-import · 14 new players</div>
                  <div className="alert__sub">3 flagged for review · 11 clean</div>
                </div>
                <div className="alert__meta">1h ago</div>
              </div>
              <div className="alert">
                <div className="alert__icon alert__icon--info"><Icons.Imports size={14} /></div>
                <div className="alert__body">
                  <div className="alert__title">Auto-import · 0 changes</div>
                  <div className="alert__sub">Quiet hour. Everyone's at brunch.</div>
                </div>
                <div className="alert__meta">3h ago</div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

window.Dashboard = Dashboard;

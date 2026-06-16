/* global window, React, Icons */
// SES Session detail

const { useState } = React;
const { Avatar, Pill, Button, Card, Segmented } = window.UI;

function SES({ go, sessionId }) {
  const { SESSIONS, STATIONS, PLAYERS } = window.SFLL_DATA;
  const session = SESSIONS.find(s => s.id === sessionId) || SESSIONS[0];
  const [tab, setTab] = useState("roster");

  const roster = PLAYERS.filter(p => p.division === session.division).slice(0, 18);
  const checkedIn = roster.slice(0, session.checkedIn);
  const noShow = roster.slice(session.checkedIn);

  return (
    <div className="page">
      <div style={{ marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
        <button className="btn btn--ghost btn--sm" onClick={() => go("dashboard")}>
          <Icons.ArrowLeft size={14} /> Back
        </button>
        <span style={{ color: "var(--ink-4)" }}>/</span>
        <span className="text-sm text-muted">SES sessions</span>
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">{session.name}</h1>
          <div className="page-sub" style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 6 }}>
            <span><Icons.Calendar size={13} style={{ verticalAlign: "-2px", marginRight: 4 }} />{session.date}, {session.time}</span>
            <span><Icons.Pin size={13} style={{ verticalAlign: "-2px", marginRight: 4 }} />{session.location}</span>
            <Pill kind="primary">Majors · 12 teams</Pill>
            {session.checkedIn === session.expected
              ? <Pill kind="success" dot>All checked in</Pill>
              : <Pill kind="warn" dot>{session.expected - session.checkedIn} no-show</Pill>}
          </div>
        </div>
        <div className="page-header__actions">
          <Button variant="ghost" leadingIcon={Icons.Print}>Print station sheets</Button>
          <Button variant="ghost" leadingIcon={Icons.Mail}>Email no-shows</Button>
          <Button variant="primary" leadingIcon={Icons.Plus}>Add walk-in</Button>
        </div>
      </div>

      <div className="stats">
        <Stat label="Checked in" value={`${session.checkedIn}/${session.expected}`} delta={`${Math.round(session.checkedIn / session.expected * 100)}% turnout`} deltaKind="up" />
        <Stat label="Evaluations" value={`${session.evals}/${session.evalsExpected}`} delta={`${session.evalsExpected - session.evals} pending`} deltaKind="flat" />
        <Stat label="Coaches present" value="11/12" delta="Walker covering for Patel" deltaKind="flat" />
        <Stat label="Stations" value="5" delta="20 min rotations" deltaKind="flat" />
      </div>

      {/* Station progress */}
      <h3 className="display" style={{ fontSize: 18, margin: "8px 0 12px", fontWeight: 600 }}>Station progress</h3>
      <div className="station-grid">
        {STATIONS.map((s, i) => {
          const total = session.expected;
          const done = Math.min(total, Math.round(total * (0.85 - i * 0.08)));
          const pct = Math.round(done / total * 100);
          return (
            <div key={s.id} className="station-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{s.name}</div>
                  <div className="text-xs text-muted" style={{ marginTop: 2 }}>{s.fields.join(" · ")}</div>
                </div>
                <Pill kind={pct === 100 ? "success" : pct > 70 ? "primary" : "warn"}>{pct}%</Pill>
              </div>
              <div className="bar"><div className={"bar__fill " + (pct === 100 ? "bar__fill--ok" : pct < 50 ? "bar__fill--warn" : "")} style={{ width: pct + "%" }} /></div>
              <div className="station-card__row">
                <span>{done}/{total} evaluated</span>
                <span>Coach {["Chen","Park","O'Brien","Walker","Tanaka"][i]}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: 24 }}>
        <div className="tabs">
          {[
            { v: "roster", label: `Check-in roster · ${session.expected}` },
            { v: "noshow", label: `No-shows · ${session.expected - session.checkedIn}` },
            { v: "evals",  label: `Evaluations · ${session.evals}` },
          ].map(t => (
            <div key={t.v} className={"tab " + (tab === t.v ? "tab--active" : "")} onClick={() => setTab(t.v)}>
              {t.label}
            </div>
          ))}
        </div>

        {tab === "roster" ? (
          <Card padding={false}>
            <table className="table table--clickable">
              <thead>
                <tr>
                  <th style={{ width: 28 }}></th>
                  <th>Player</th>
                  <th>Checked in</th>
                  <th>Hitting</th>
                  <th>Pitching</th>
                  <th>Infield</th>
                  <th>Outfield</th>
                  <th>Speed</th>
                  <th className="col-actions"></th>
                </tr>
              </thead>
              <tbody>
                {checkedIn.map((p, i) => (
                  <tr key={p.id} onClick={() => go("player", p.id)}>
                    <td><Avatar player={p} size="sm" /></td>
                    <td>
                      <div className="player-cell__name">{p.first} {p.last}</div>
                      <div className="player-cell__sub">Age {p.age}</div>
                    </td>
                    <td className="text-sm mono">
                      <span style={{ color: "var(--success)" }}>✓</span>{" "}
                      {String(9 + Math.floor(i/12)).padStart(2,"0")}:{String(((i*7)%55)).padStart(2,"0")}
                    </td>
                    {[0,1,2,3,4].map(s => {
                      const done = i + s < 14;
                      return <td key={s}>
                        {done
                          ? <span className="tabular" style={{ fontWeight: 600 }}>{(6.5 + Math.random()*2.5).toFixed(1)}</span>
                          : <Pill kind="ghost">queued</Pill>}
                      </td>;
                    })}
                    <td className="col-actions"><Icons.Chevron size={14} style={{ color: "var(--ink-3)" }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        ) : null}

        {tab === "noshow" ? (
          <Card padding={false}>
            {noShow.length === 0 ? (
              <div className="empty">
                <strong>Nobody missed it.</strong>
                That literally never happens. Take a screenshot.
              </div>
            ) : (
              <table className="table table--clickable">
                <thead>
                  <tr>
                    <th style={{ width: 28 }}></th>
                    <th>Player</th>
                    <th>RSVP'd</th>
                    <th>Family contact</th>
                    <th>Last reminder</th>
                    <th>Makeup</th>
                    <th className="col-actions"></th>
                  </tr>
                </thead>
                <tbody>
                  {noShow.map((p, i) => (
                    <tr key={p.id} onClick={() => go("player", p.id)}>
                      <td><Avatar player={p} size="sm" /></td>
                      <td>
                        <div className="player-cell__name">{p.first} {p.last}</div>
                        <div className="player-cell__sub">Age {p.age} · {p.sub}</div>
                      </td>
                      <td>{i % 2 === 0 ? <Pill kind="success">Yes</Pill> : <Pill kind="neutral">No reply</Pill>}</td>
                      <td className="text-sm mono">(415) 555-01{String(20+i).padStart(2,"0")}</td>
                      <td className="text-sm text-muted">Thu, 9:14 AM</td>
                      <td><Pill kind="warn" dot>Needs date</Pill></td>
                      <td className="col-actions">
                        <Button size="sm" variant="ghost">Reschedule</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        ) : null}

        {tab === "evals" ? (
          <Card padding={false}>
            <div className="empty">
              <strong>Evaluations submit per-coach, per-station.</strong>
              The full grid is rolled into the Draft Board view.
            </div>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

function Stat({ label, value, delta, deltaKind }) {
  return (
    <div className="stat">
      <div className="stat__label">{label}</div>
      <div className="stat__value tabular">{value}</div>
      {delta ? <div className={"stat__delta stat__delta--" + (deltaKind || "flat")}>{delta}</div> : null}
    </div>
  );
}

window.SES = SES;

/* global window, React, Icons */
// Print preview — Dugout roster card (one half-sheet per team).

const { useState } = React;
const { Pill, Button, TeamSwatch } = window.UI;

function Print({ go }) {
  const { PLAYERS, TEAMS } = window.SFLL_DATA;
  const [teamId, setTeamId] = useState("t-giants");
  const team = TEAMS.find(t => t.id === teamId);
  const roster = PLAYERS.filter(p => p.team === teamId);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Print · Dugout roster cards</h1>
          <div className="page-sub">Half-sheet per team. Folds into a Ziploc, sticks to a clipboard, survives a Mission burrito.</div>
        </div>
        <div className="page-header__actions">
          <Button variant="ghost" leadingIcon={Icons.Print} onClick={() => window.print()}>Print this</Button>
          <Button variant="primary" leadingIcon={Icons.Imports}>Print all 12</Button>
        </div>
      </div>

      <div className="toolbar" style={{ marginBottom: 8 }}>
        <span className="text-xs text-muted">Team:</span>
        {TEAMS.map(t => (
          <button key={t.id} className={"chip " + (teamId === t.id ? "chip--active" : "")} onClick={() => setTeamId(t.id)}>
            {t.name}
          </button>
        ))}
      </div>

      <DugoutCard team={team} roster={roster} />
    </div>
  );
}

function DugoutCard({ team, roster }) {
  return (
    <div className="print-frame">
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-end", borderBottom: "3px solid #111", paddingBottom: 10, marginBottom: 14 }}>
        <div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 30, fontWeight: 700, letterSpacing: "-0.025em", lineHeight: 1 }}>
            {team?.name || "—"}
          </div>
          <div style={{ fontSize: 13, color: "#444", marginTop: 4 }}>
            Majors · {team?.subLeague || "—"} League · Spring 2026
          </div>
        </div>
        <div style={{ marginLeft: "auto", textAlign: "right", fontSize: 11, color: "#444", lineHeight: 1.4 }}>
          <div style={{ fontWeight: 600, color: "#111", fontSize: 13 }}>SFLL</div>
          <div>San Francisco Little League</div>
          <div>sfll.org</div>
        </div>
      </div>

      {/* Coaches strip */}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#222", marginBottom: 14, gap: 18 }}>
        <div>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", color: "#666", fontWeight: 600 }}>Head Coach</div>
          <div style={{ fontWeight: 600, marginTop: 2 }}>{team?.coach || "TBD"}</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>(415) 555-0193</div>
        </div>
        <div>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", color: "#666", fontWeight: 600 }}>Asst. Coach</div>
          <div style={{ fontWeight: 600, marginTop: 2 }}>R. Walker</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>(415) 555-0227</div>
        </div>
        <div>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", color: "#666", fontWeight: 600 }}>Team Parent</div>
          <div style={{ fontWeight: 600, marginTop: 2 }}>K. O'Brien</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>(415) 555-0381</div>
        </div>
        <div>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", color: "#666", fontWeight: 600 }}>Home Field</div>
          <div style={{ fontWeight: 600, marginTop: 2 }}>Big Rec</div>
          <div style={{ fontSize: 11, color: "#444" }}>GG Park · Stanyan</div>
        </div>
      </div>

      {/* Roster table */}
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginBottom: 16 }}>
        <thead>
          <tr style={{ borderBottom: "1.5px solid #111" }}>
            <th style={{ textAlign: "left",  padding: "6px 4px", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "#444", width: 36 }}>#</th>
            <th style={{ textAlign: "left",  padding: "6px 4px", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "#444" }}>Player</th>
            <th style={{ textAlign: "left",  padding: "6px 4px", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "#444", width: 56 }}>Age</th>
            <th style={{ textAlign: "left",  padding: "6px 4px", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "#444", width: 80 }}>Pos</th>
            <th style={{ textAlign: "left",  padding: "6px 4px", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "#444", width: 48 }}>B / T</th>
            <th style={{ textAlign: "left",  padding: "6px 4px", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "#444" }}>Parent</th>
            <th style={{ textAlign: "left",  padding: "6px 4px", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "#444", width: 120 }}>Phone</th>
          </tr>
        </thead>
        <tbody>
          {roster.map((p, i) => (
            <tr key={p.id} style={{ borderBottom: "1px dashed #ddd" }}>
              <td style={{ padding: "8px 4px", fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 13 }}>{p.jersey || "—"}</td>
              <td style={{ padding: "8px 4px", fontWeight: 600 }}>
                {p.first} {p.last}
                {p.top4 ? <span style={{ color: "#b22", marginLeft: 6, fontSize: 10, verticalAlign: "1px" }}>★</span> : null}
              </td>
              <td style={{ padding: "8px 4px" }}>{p.age}</td>
              <td style={{ padding: "8px 4px" }}>{p.positions.join("/")}</td>
              <td style={{ padding: "8px 4px", fontFamily: "var(--font-mono)" }}>{p.bats}/{p.throws}</td>
              <td style={{ padding: "8px 4px", color: "#444" }}>
                {["Wei Chen","Maria Hernández","Sofia Garcia","Carlos Martínez","Linh Tran","Jin Park","Susan Lee","Kate O'Brien","Patrick Park","Ana Lopez","David Kim","Esteban Vega","Jamie Russo"][i % 13]}
              </td>
              <td style={{ padding: "8px 4px", fontFamily: "var(--font-mono)" }}>(415) 555-{String(120 + i * 13).padStart(4,"0")}</td>
            </tr>
          ))}
          {Array.from({ length: Math.max(0, 12 - roster.length) }).map((_, i) => (
            <tr key={"blank"+i} style={{ borderBottom: "1px dashed #ddd" }}>
              <td style={{ padding: "8px 4px", color: "#ccc", fontFamily: "var(--font-mono)" }}>—</td>
              <td colSpan={6} style={{ padding: "8px 4px", color: "#bbb", fontStyle: "italic" }}>open slot</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Schedule strip */}
      <div style={{ borderTop: "1.5px solid #111", paddingTop: 12, marginBottom: 12 }}>
        <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", color: "#666", fontWeight: 600, marginBottom: 6 }}>Next 5 games</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, fontSize: 11 }}>
          {[
            ["4/12","Sat 10:00","Red Sox",  "Big Rec"],
            ["4/16","Tue 6:00", "@ Athletics","West Sunset"],
            ["4/20","Sun 12:00","Yankees",   "Big Rec"],
            ["4/26","Sat 1:00", "@ Rangers", "Funston"],
            ["4/30","Wed 6:00", "Rays",      "Big Rec"],
          ].map(([d, t, opp, loc]) => (
            <div key={d} style={{ border: "1px solid #ddd", borderRadius: 4, padding: "6px 8px" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 12 }}>{d}</div>
              <div style={{ color: "#444", fontSize: 10 }}>{t}</div>
              <div style={{ fontWeight: 600, marginTop: 3 }}>{opp}</div>
              <div style={{ color: "#444", fontSize: 10 }}>{loc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Emergencies */}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#666", borderTop: "1px solid #eee", paddingTop: 8 }}>
        <span>Emergency: 911 · SFLL Safety Officer: (415) 555-0911 · UC Mission Bay ER: 2.1 mi</span>
        <span>Printed Apr 9, 2026 · v.2026.1</span>
      </div>
    </div>
  );
}

window.Print = Print;

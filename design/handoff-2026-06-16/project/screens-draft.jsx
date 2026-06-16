/* global window, React, Icons */
// Draft board — snake draft, Majors American sub-league.

const { useState, useMemo } = React;
const { Avatar, Pill, Button, Card, TeamSwatch } = window.UI;

function Draft({ go }) {
  const { PLAYERS, TEAMS } = window.SFLL_DATA;
  // 6 American teams in the snake.
  const teamOrder = ["t-giants","t-athletics","t-yankees","t-redsox","t-rangers","t-rays"];
  const teams = teamOrder.map(id => TEAMS.find(t => t.id === id));

  // Pre-draft picks for the prototype. Round → Pos → playerId (or null)
  // Snake: R1 fwd, R2 rev, R3 fwd, R4 rev, R5 fwd
  const picks = [
    // R1 (fwd): Giants, Athletics, Yankees, Red Sox, Rangers, Rays
    ["p001","p006","p004","p003","p008","p011"],
    // R2 (rev): Rays, Rangers, Red Sox, Yankees, Athletics, Giants
    ["p020","p019","p018","p017","p016","p002"],
    // R3 (fwd): Giants, Athletics, Yankees, Red Sox, Rangers, Rays
    ["p005","p016b","p017b","p018b","p008b","p020b"],
    // R4 (rev): Rays(✓), Rangers(✓), [current → Red Sox], Yankees, Athletics, Giants
    ["p011b","p019b", "CURRENT", null, null, null],
    [null, null, null, null, null, null],
  ];

  // Available player queue (unpicked, sorted by topRank).
  const pickedIds = picks.flat().filter(x => x && x !== "CURRENT" && !x.endsWith("b"));
  const availableQueue = PLAYERS
    .filter(p => p.sub === "American" && p.division === "majors" && !pickedIds.includes(p.id))
    .sort((a,b) => a.topRank - b.topRank)
    .slice(0, 12);

  const currentRound = 4;
  const currentPick = 3;
  const totalPicks = 6 * 5;
  const madePicks = picks.flat().filter(x => x && x !== "CURRENT").length;

  // For "on the clock"
  const onClockTeamIdx = 2; // Red Sox in snake-reverse R4 (pos 3)
  const nextThreeTeams = [
    { team: teams[3], pick: "R4 · #3", on: true },   // Red Sox
    { team: teams[2], pick: "R4 · #4", on: false },
    { team: teams[1], pick: "R4 · #5", on: false },
    { team: teams[0], pick: "R4 · #6", on: false },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Draft · Majors (American)</h1>
          <div className="page-sub" style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 6 }}>
            <Pill kind="primary" icon={<Icons.Draft size={11} />}>Snake · 6 teams · 11 rounds</Pill>
            <span>Round <strong style={{ color: "var(--ink)" }}>{currentRound}</strong> of 11 · Pick <strong style={{ color: "var(--ink)" }}>{(currentRound-1)*6 + currentPick}</strong> of 66</span>
            <Pill kind="warn" dot>Live</Pill>
          </div>
        </div>
        <div className="page-header__actions">
          <Button variant="ghost" leadingIcon={Icons.Print}>Print board</Button>
          <Button variant="ghost">Pause</Button>
          <Button variant="primary" leadingIcon={Icons.Sparkle}>Suggest pick</Button>
        </div>
      </div>

      <div className="stats" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <div className="stat">
          <div className="stat__label">On the clock</div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 6 }}>
            <TeamSwatch teamId={teams[3].id} />
            <div>
              <div style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>{teams[3].name}</div>
              <div className="text-xs text-muted">Coach Park · 1:38 on clock</div>
            </div>
          </div>
        </div>
        <Stat label="Picks made" value={`${madePicks}/${totalPicks}`} delta="Last: Doyle → Rangers" />
        <Stat label="Top-4 placed" value="4/4" delta="All to their assigned teams" deltaKind="up" />
        <Stat label="Coach's kids placed" value="6/8" delta="2 to go" deltaKind="flat" />
      </div>

      <div className="draft-grid">
        {/* Left: team order */}
        <Card title="Draft order" sub="Snake" padding={false}>
          <div style={{ padding: 8 }}>
            {nextThreeTeams.map((t, i) => (
              <div key={i} className={"draft-team " + (t.on ? "draft-team--on-clock" : "")}>
                <span className="draft-team__pos">{i + 1}</span>
                <TeamSwatch teamId={t.team.id} size="sm" />
                <span className="draft-team__name">{t.team.name}</span>
                <span className="draft-team__picks">{t.pick}</span>
              </div>
            ))}
          </div>
          <div style={{ padding: "10px 14px", borderTop: "1px solid var(--border)" }}>
            <div className="text-xs text-muted" style={{ marginBottom: 8 }}>Suggested next pick</div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 8, background: "var(--primary-soft)", borderRadius: 8 }}>
              <div className="avatar avatar--sm" style={{ background: "var(--primary)", color: "#fff" }}>EV</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 13 }}>Eliana Vázquez</div>
                <div className="text-xs text-muted">#13 · P · 9.1 composite</div>
              </div>
              <Pill kind="primary">Best avail.</Pill>
            </div>
          </div>
        </Card>

        {/* Center: draft grid */}
        <div>
          <div className="draft-board-grid" style={{ gridTemplateColumns: "32px repeat(6, 1fr)" }}>
            {/* Header row */}
            <div className="draft-cell draft-cell--header"></div>
            {teams.map(t => (
              <div key={t.id} className="draft-cell draft-cell--header" title={t.name}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4 }}>
                  <TeamSwatch teamId={t.id} size="sm" />
                  {t.name.length > 6 ? t.name.slice(0,3) + "." : t.name}
                </div>
              </div>
            ))}

            {/* Rows */}
            {picks.map((round, ri) => {
              const reversed = (ri + 1) % 2 === 0;
              // Display order is always team order left→right. But snake means pick order reverses.
              return (
                <React.Fragment key={ri}>
                  <div className="draft-cell draft-cell--rownum">R{ri+1}</div>
                  {teams.map((team, ti) => {
                    // pick index in this round, mapped to team's display column
                    const pickIdxInRound = reversed ? (5 - ti) : ti;
                    const playerId = round[pickIdxInRound];
                    if (playerId === "CURRENT") {
                      return (
                        <div key={ti} className="draft-cell draft-cell--current">
                          <div style={{ fontSize: 10, color: "var(--primary-soft-ink)", fontWeight: 600 }}>ON THE CLOCK</div>
                          <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 4 }}>Park · 1:38</div>
                        </div>
                      );
                    }
                    if (!playerId) {
                      return <div key={ti} className="draft-cell"></div>;
                    }
                    // Resolve player. "pXXXb" → second-pick fake placeholder.
                    const realId = playerId.endsWith("b") ? playerId.slice(0,-1) : playerId;
                    const player = PLAYERS.find(p => p.id === realId);
                    if (!player) return <div key={ti} className="draft-cell"></div>;
                    const isTop4 = player.top4 && !playerId.endsWith("b");
                    const isChild = player.coachChild && !playerId.endsWith("b") && !isTop4;
                    const classes = ["draft-cell", "draft-cell--filled"];
                    if (isTop4) classes.push("draft-cell--top4");
                    if (isChild) classes.push("draft-cell--child");
                    return (
                      <div key={ti} className={classes.join(" ")} onClick={() => go("player", realId)} style={{ cursor: "pointer" }}>
                        <div className="pn" style={{ display: "flex", alignItems: "center", gap: 3 }}>
                          {isTop4 ? <Icons.Top4 size={9} style={{ color: "var(--accent)" }}/> : null}
                          {isChild ? <Icons.Coach size={9} style={{ color: "var(--primary-soft-ink)" }}/> : null}
                          {player.last}{playerId.endsWith("b") ? "*" : ""}
                        </div>
                        <div className="pos">{player.positions.slice(0,2).join("·")} · #{player.topRank}{playerId.endsWith("b") ? "+" : ""}</div>
                      </div>
                    );
                  })}
                </React.Fragment>
              );
            })}
          </div>
          <div className="text-xs text-muted mt-2" style={{ display: "flex", gap: 16 }}>
            <span><span style={{ display: "inline-block", width: 10, height: 10, background: "var(--accent)", verticalAlign: "middle", marginRight: 6, borderRadius: 2 }} /> Top-4 protected</span>
            <span><span style={{ display: "inline-block", width: 10, height: 10, background: "var(--primary-soft)", verticalAlign: "middle", marginRight: 6, borderRadius: 2 }} /> Coach's child</span>
            <span>* second-round placeholder data</span>
          </div>
        </div>

        {/* Right: available queue */}
        <Card title="Available" sub={`${availableQueue.length} top players`} padding={false}>
          <div className="card__list">
            {availableQueue.map(p => (
              <div key={p.id} className="alert" style={{ padding: "10px 14px" }} onClick={() => go("player", p.id)}>
                <div style={{ width: 28, textAlign: "center", fontFamily: "var(--font-num)", color: p.topRank <= 4 ? "var(--accent)" : "var(--ink-2)", fontWeight: 700, fontSize: 13 }}>
                  #{p.topRank}
                </div>
                <div className="alert__body">
                  <div className="alert__title" style={{ fontSize: 13 }}>{p.first} {p.last}</div>
                  <div className="alert__sub" style={{ fontSize: 11.5 }}>
                    {p.positions.join(" · ")} · {p.bats}/{p.throws}
                    {p.top4 ? <span style={{ color: "var(--accent)", marginLeft: 6 }}><Icons.Top4 size={10} /></span> : null}
                    {p.coachChild ? <span style={{ color: "var(--ink-3)", marginLeft: 4 }}><Icons.Coach size={10} /></span> : null}
                  </div>
                </div>
                <Button size="sm" variant="ghost">Pick</Button>
              </div>
            ))}
          </div>
        </Card>
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

window.Draft = Draft;

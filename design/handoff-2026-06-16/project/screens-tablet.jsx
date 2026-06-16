/* global window, React, Icons */
// iPad views — SES Check-In Kiosk + Draft Room.

const { useState, useMemo } = React;
const { Pill, Avatar, TeamSwatch, Button, SearchInput } = window.UI;

// ─────────────────────── iPad frame ───────────────────────
function IPadFrame({ children, width = 980, height = 740, orientation = "landscape" }) {
  // 4:3 aspect; bezel ~16px; rounded ~32px; camera dot
  const w = orientation === "portrait" ? height : width;
  const h = orientation === "portrait" ? width : height;
  return (
    <div style={{
      width: w + 32,
      height: h + 32,
      borderRadius: 36,
      background: "#15171b",
      padding: 16,
      boxShadow: "0 40px 80px rgba(0,0,0,0.18), 0 0 0 1px rgba(0,0,0,0.12)",
      position: "relative",
      flexShrink: 0,
    }}>
      {/* camera */}
      <div style={{
        position: "absolute",
        top: 16, left: "50%", transform: "translateX(-50%)",
        width: 7, height: 7, borderRadius: "50%",
        background: "#2a2c33",
      }} />
      <div style={{
        width: w,
        height: h,
        borderRadius: 22,
        background: "var(--bg)",
        overflow: "hidden",
        fontFamily: "var(--font-body)",
        position: "relative",
      }}>
        {children}
      </div>
    </div>
  );
}

// ─────────────────────── iPad screen container ───────────────────────
function IPad({ go }) {
  const [view, setView] = useState("checkin"); // checkin | draft

  return (
    <div className="page" style={{ maxWidth: 1400 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">iPad views</h1>
          <div className="page-sub">
            Two views that earn their keep on a tablet. Both designed for landscape, mounted on a clipboard.
          </div>
        </div>
        <div className="page-header__actions">
          <div className="seg">
            <button className={"seg__btn " + (view === "checkin" ? "seg__btn--active" : "")} onClick={() => setView("checkin")}>Check-In Kiosk</button>
            <button className={"seg__btn " + (view === "draft" ? "seg__btn--active" : "")} onClick={() => setView("draft")}>Draft Room</button>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "center", padding: "10px 0 30px" }}>
        <IPadFrame width={1000} height={740}>
          {view === "checkin" ? <CheckInKiosk /> : <DraftRoomTablet />}
        </IPadFrame>
      </div>

      <p className="text-sm text-muted" style={{ textAlign: "center" }}>
        Both views read from the same live data as desktop. Theming follows the Tweaks panel.
      </p>
    </div>
  );
}

// ─────────────────────── Front-Desk SES Check-In ───────────────────────
function CheckInKiosk() {
  const { PLAYERS } = window.SFLL_DATA;
  const roster = useMemo(() => PLAYERS.filter(p => p.division === "majors").slice(0, 30), [PLAYERS]);
  const [q, setQ] = useState("");
  const [checked, setChecked] = useState(() => new Set(roster.slice(0, 17).map(p => p.id)));
  const [confirming, setConfirming] = useState(null);
  const [filter, setFilter] = useState("all");

  const filtered = roster.filter(p => {
    if (q) {
      const qq = q.toLowerCase();
      if (!`${p.first} ${p.last}`.toLowerCase().includes(qq)) return false;
    }
    if (filter === "remaining") return !checked.has(p.id);
    if (filter === "checked")   return checked.has(p.id);
    return true;
  });

  const recent = roster
    .filter(p => checked.has(p.id))
    .slice(-5)
    .reverse();

  function handleConfirm() {
    if (confirming) {
      const next = new Set(checked);
      next.add(confirming.id);
      setChecked(next);
      setConfirming(null);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", color: "var(--ink)" }}>
      {/* Header */}
      <div style={{ padding: "18px 24px", borderBottom: "1px solid var(--border)", background: "var(--bg-2)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div className="brand-mark brand-mark--diamond" style={{ width: 36, height: 36 }} />
          <div style={{ flex: 1 }}>
            <div className="display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", lineHeight: 1.1 }}>
              Check in · Majors SES
            </div>
            <div className="text-sm text-muted" style={{ marginTop: 2 }}>
              <Icons.Calendar size={12} style={{ verticalAlign: "-2px", marginRight: 4 }} />
              Sat Mar 1, 2026 · 9:00 AM · Big Rec, Golden Gate Park
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="display" style={{ fontSize: 32, fontWeight: 700, letterSpacing: "-0.02em", lineHeight: 1 }}>
              {checked.size}<span style={{ color: "var(--ink-3)", fontWeight: 500 }}>/{roster.length}</span>
            </div>
            <div className="text-xs text-muted">checked in</div>
          </div>
          <button className="iconbtn" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}><Icons.Settings size={16} /></button>
        </div>
      </div>

      {/* Body: grid + recent */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 280px", minHeight: 0 }}>
        {/* Left: search + tile grid */}
        <div style={{ display: "flex", flexDirection: "column", minHeight: 0, padding: "16px 20px 20px" }}>
          <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
            <div style={{ flex: 1 }}>
              <SearchInput value={q} onChange={setQ} placeholder="Search by name…" />
            </div>
            <div className="seg">
              <button className={"seg__btn " + (filter === "all" ? "seg__btn--active" : "")} onClick={() => setFilter("all")}>All · {roster.length}</button>
              <button className={"seg__btn " + (filter === "remaining" ? "seg__btn--active" : "")} onClick={() => setFilter("remaining")}>Remaining · {roster.length - checked.size}</button>
              <button className={"seg__btn " + (filter === "checked" ? "seg__btn--active" : "")} onClick={() => setFilter("checked")}>Checked · {checked.size}</button>
            </div>
          </div>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(6, 1fr)",
            gap: 10,
            overflowY: "auto",
            paddingRight: 4,
          }}>
            {filtered.map(p => {
              const isIn = checked.has(p.id);
              return (
                <button key={p.id}
                  onClick={() => isIn ? null : setConfirming(p)}
                  style={{
                    background: isIn ? "var(--success-soft)" : "var(--surface)",
                    border: "1px solid " + (isIn ? "var(--success)" : "var(--border)"),
                    borderRadius: 14,
                    padding: "14px 10px 12px",
                    cursor: isIn ? "default" : "pointer",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 6,
                    minHeight: 110,
                    position: "relative",
                    transition: "transform .1s",
                    fontFamily: "inherit",
                    color: "inherit",
                    opacity: isIn ? 0.8 : 1,
                  }}>
                  <Avatar player={p} size="lg" />
                  <div style={{ fontWeight: 600, fontSize: 12.5, lineHeight: 1.15, textAlign: "center" }}>
                    {p.first}<br/>{p.last}
                  </div>
                  {isIn ? (
                    <div style={{ position: "absolute", top: 6, right: 6, width: 22, height: 22, borderRadius: "50%", background: "var(--success)", color: "#fff", display: "grid", placeItems: "center" }}>
                      <Icons.Check size={12} />
                    </div>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: just-checked-in feed */}
        <div style={{
          borderLeft: "1px solid var(--border)",
          background: "var(--bg-2)",
          padding: "16px 16px 12px",
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
        }}>
          <div className="display" style={{ fontSize: 14, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--ink-3)", marginBottom: 10 }}>
            Just checked in
          </div>
          <div style={{ flex: 1, overflowY: "auto" }}>
            {recent.map((p, i) => (
              <div key={p.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 6px", borderBottom: "1px solid var(--border)" }}>
                <Avatar player={p} size="md" />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13.5 }}>{p.first} {p.last}</div>
                  <div className="text-xs text-muted">Just now · by walk-up</div>
                </div>
                <Icons.Check size={14} style={{ color: "var(--success)" }} />
              </div>
            ))}
          </div>
          <div style={{ marginTop: 10, padding: 12, background: "var(--surface)", borderRadius: 12, border: "1px solid var(--border)" }}>
            <div className="display" style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>Don't see them?</div>
            <button className="btn" style={{ width: "100%", justifyContent: "center" }}>
              <Icons.Plus size={14} /> Walk-in registration
            </button>
            <button className="btn btn--ghost" style={{ width: "100%", justifyContent: "center", marginTop: 6 }}>
              <Icons.Phone size={14} /> Call Nate
            </button>
          </div>
        </div>
      </div>

      {/* Confirm modal */}
      {confirming ? (
        <div style={{ position: "absolute", inset: 0, background: "rgba(15,20,30,0.4)", display: "grid", placeItems: "center", zIndex: 20 }} onClick={() => setConfirming(null)}>
          <div style={{ background: "var(--surface)", borderRadius: 18, padding: 28, width: 440, boxShadow: "var(--shadow-lg)" }} onClick={e => e.stopPropagation()}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <Avatar player={confirming} size="xl" />
              <div>
                <div className="display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", lineHeight: 1.1 }}>{confirming.first} {confirming.last}</div>
                <div className="text-sm text-muted" style={{ marginTop: 2 }}>Age {confirming.age} · {confirming.positions.join(" · ")}</div>
                <div className="text-sm" style={{ marginTop: 2 }}>
                  Family: <strong>{["Maria Hernández","Wei Chen","Jin Park","Kate O'Brien"][parseInt(confirming.id.slice(1)) % 4]}</strong>
                </div>
              </div>
            </div>
            <div style={{ background: "var(--bg-2)", borderRadius: 12, padding: 12, marginTop: 16, fontSize: 13 }}>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                <span className="text-muted">Photo release</span>
                <Pill kind="success" dot>On file</Pill>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                <span className="text-muted">Medical form</span>
                <Pill kind="success" dot>On file</Pill>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                <span className="text-muted">Balance</span>
                <Pill kind="success">Paid in full</Pill>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
              <button className="btn" style={{ flex: 1, justifyContent: "center", padding: "12px" }} onClick={() => setConfirming(null)}>Cancel</button>
              <button className="btn btn--primary" style={{ flex: 2, justifyContent: "center", padding: "12px", fontSize: 14 }} onClick={handleConfirm}>
                <Icons.Check size={16} /> Check in {confirming.first}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

// ─────────────────────── Draft Room (iPad) ───────────────────────
function DraftRoomTablet() {
  const { PLAYERS, TEAMS } = window.SFLL_DATA;
  const order = ["t-giants","t-athletics","t-yankees","t-redsox","t-rangers","t-rays"];
  const teams = order.map(id => TEAMS.find(t => t.id === id));
  const onClock = teams[3]; // Red Sox
  const onDeck = teams[2];

  const available = PLAYERS
    .filter(p => p.sub === "American" && p.division === "majors" && !["p001","p003","p004","p006","p008","p011","p020","p019","p018","p017","p016","p002"].includes(p.id))
    .sort((a,b) => a.topRank - b.topRank)
    .slice(0, 12);

  const [selected, setSelected] = useState(available[0]?.id);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", color: "var(--ink)" }}>
      {/* Top bar */}
      <div style={{ padding: "14px 22px", borderBottom: "1px solid var(--border)", background: "var(--bg-2)", display: "flex", alignItems: "center", gap: 16 }}>
        <div className="brand-mark brand-mark--diamond" style={{ width: 32, height: 32 }} />
        <div>
          <div className="display" style={{ fontSize: 17, fontWeight: 700, letterSpacing: "-0.02em" }}>Draft Room · Majors American</div>
          <div className="text-xs text-muted">Round 4 of 11 · Pick 21 of 66</div>
        </div>
        <div style={{ flex: 1 }} />
        <Pill kind="warn" dot>Live</Pill>
        <div className="mono" style={{ fontFamily: "var(--font-num)", fontSize: 15, fontWeight: 600, color: "var(--ink)" }}>01:38</div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", flex: 1, minHeight: 0 }}>
        {/* Available + selection */}
        <div style={{ display: "flex", flexDirection: "column", minHeight: 0, padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <h3 className="display" style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>Available · {available.length}</h3>
            <Pill kind="primary">Sorted by composite</Pill>
            <div style={{ marginLeft: "auto" }} className="text-sm text-muted">Tap a player to preview, double-tap to draft.</div>
          </div>
          <div style={{ flex: 1, overflowY: "auto", display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8, gridAutoRows: "min-content", alignContent: "start" }}>
            {available.map(p => {
              const isSel = p.id === selected;
              return (
                <button key={p.id}
                  onClick={() => setSelected(p.id)}
                  style={{
                    background: isSel ? "var(--primary-soft)" : "var(--surface)",
                    border: "1px solid " + (isSel ? "var(--primary)" : "var(--border)"),
                    borderRadius: 12,
                    padding: "12px 14px",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    cursor: "pointer",
                    fontFamily: "inherit",
                    color: "inherit",
                    textAlign: "left",
                  }}>
                  <div style={{ width: 36, textAlign: "center", fontFamily: "var(--font-num)", fontWeight: 700, fontSize: 18, color: p.topRank <= 4 ? "var(--accent)" : "var(--ink-2)" }}>
                    #{p.topRank}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{p.first} {p.last}
                      {p.top4 ? <span style={{ color: "var(--accent)", marginLeft: 6 }}><Icons.Top4 size={11} /></span> : null}
                      {p.coachChild ? <span style={{ color: "var(--ink-3)", marginLeft: 4 }}><Icons.Coach size={11} /></span> : null}
                    </div>
                    <div className="text-xs text-muted">
                      {p.positions.join(" · ")} · Bats {p.bats}/Throws {p.throws} · Age {p.age}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* On-clock panel */}
        <div style={{ borderLeft: "1px solid var(--border)", background: "var(--bg-2)", padding: "16px 18px", display: "flex", flexDirection: "column", minHeight: 0 }}>
          <div className="display" style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.08em" }}>On the clock</div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8 }}>
            <TeamSwatch teamId={onClock.id} size="lg" />
            <div>
              <div className="display" style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em", lineHeight: 1.05 }}>{onClock.name}</div>
              <div className="text-xs text-muted">Coach {onClock.coach} · R4 · P3</div>
            </div>
          </div>

          {/* Picking */}
          {selected ? (() => {
            const p = available.find(x => x.id === selected);
            return (
              <div style={{ marginTop: 14, padding: 14, background: "var(--surface)", borderRadius: 12, border: "1px solid var(--border)" }}>
                <div className="text-xs text-muted" style={{ fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>Drafting</div>
                <div className="display" style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.02em", marginTop: 2 }}>{p.first} {p.last}</div>
                <div className="text-xs text-muted" style={{ marginTop: 1 }}>#{p.topRank} · {p.positions.join("/")} · {p.bats}/{p.throws}</div>
                <button className="btn btn--primary" style={{ width: "100%", justifyContent: "center", padding: "12px", marginTop: 12, fontSize: 14 }}>
                  <Icons.Check size={16} /> Confirm pick to {onClock.name}
                </button>
                <button className="btn btn--ghost" style={{ width: "100%", justifyContent: "center", padding: "8px", marginTop: 4, fontSize: 12 }}>
                  Pass to next
                </button>
              </div>
            );
          })() : null}

          <div style={{ marginTop: 14 }}>
            <div className="display" style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Up next</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 6, padding: "8px 10px", background: "var(--surface)", borderRadius: 10, border: "1px solid var(--border)" }}>
              <TeamSwatch teamId={onDeck.id} size="sm" />
              <div style={{ flex: 1, fontWeight: 600, fontSize: 13 }}>{onDeck.name}</div>
              <span className="text-xs text-muted">R4 · P4</span>
            </div>
          </div>

          <div style={{ flex: 1 }} />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 12 }}>
            <div style={{ padding: 10, background: "var(--surface)", borderRadius: 10, border: "1px solid var(--border)" }}>
              <div className="text-xs text-muted">Picks made</div>
              <div className="display" style={{ fontWeight: 700, fontSize: 20, marginTop: 2 }}>20<span className="text-muted" style={{ fontSize: 13, fontWeight: 500 }}>/66</span></div>
            </div>
            <div style={{ padding: 10, background: "var(--surface)", borderRadius: 10, border: "1px solid var(--border)" }}>
              <div className="text-xs text-muted">Time on clock</div>
              <div className="display mono" style={{ fontWeight: 700, fontSize: 20, marginTop: 2, fontFamily: "var(--font-num)" }}>01:38</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.IPad = IPad;

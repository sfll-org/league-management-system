/* global window, React, Icons, IOSDevice */
// Field Mode — phone views for coach AND parent. Both wrapped in IOSDevice.

const { useState } = React;
const { Pill, Avatar, TeamSwatch } = window.UI;

function FieldMode({ go }) {
  const [persona, setPersona] = useState("coach"); // coach | parent
  const [tab, setTab] = useState("today");

  return (
    <div className="page" style={{ paddingTop: 16, maxWidth: 1200 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Field Mode · phone</h1>
          <div className="page-sub">
            Same data model, two very different jobs. Toggle to see what each role sees on game day.
          </div>
        </div>
        <div className="page-header__actions">
          <div className="seg">
            <button className={"seg__btn " + (persona === "coach" ? "seg__btn--active" : "")} onClick={() => { setPersona("coach"); setTab("today"); }}>Head Coach</button>
            <button className={"seg__btn " + (persona === "parent" ? "seg__btn--active" : "")} onClick={() => { setPersona("parent"); setTab("today"); }}>Parent</button>
          </div>
        </div>
      </div>

      <div className="field-mode" style={{ gap: 40, justifyContent: "center" }}>
        {persona === "coach" ? (
          <CoachPhone tab={tab} setTab={setTab} />
        ) : (
          <ParentPhone tab={tab} setTab={setTab} />
        )}
      </div>

      <p className="text-sm text-muted" style={{ textAlign: "center", marginTop: 16 }}>
        Bottom tabs work. Theme tracks the live Tweaks panel.
      </p>
    </div>
  );
}

// ───────────────────────────── Coach phone ─────────────────────────────
function CoachPhone({ tab, setTab }) {
  return (
    <IOSDevice width={390} height={780}>
      <div style={{
        background: "var(--bg)",
        color: "var(--ink)",
        minHeight: "100%",
        fontFamily: "var(--font-body)",
        display: "flex",
        flexDirection: "column",
        paddingTop: 56, // status bar
      }}>
        <CoachHeader />
        <div style={{ flex: 1 }}>
          {tab === "today" ? <CoachToday /> : null}
          {tab === "roster" ? <CoachRoster /> : null}
          {tab === "lineup" ? <CoachLineup /> : null}
          {tab === "comms" ? <CoachInbox /> : null}
        </div>
        <PhoneTabBar tab={tab} setTab={setTab} tabs={[
          { v: "today",  icon: Icons.Home,    label: "Today" },
          { v: "roster", icon: Icons.Players, label: "Roster" },
          { v: "lineup", icon: Icons.Eval,    label: "Lineup" },
          { v: "comms",  icon: Icons.Mail,    label: "Inbox" },
        ]} />
      </div>
    </IOSDevice>
  );
}

function CoachHeader() {
  return (
    <div style={{ padding: "8px 18px 14px", display: "flex", alignItems: "center", gap: 10, background: "var(--bg)" }}>
      <div className="avatar avatar--giants" style={{ width: 36, height: 36 }}>G</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 17, letterSpacing: "-0.01em", lineHeight: 1.1 }}>Giants · Majors</div>
        <div className="text-xs text-muted">Head Coach · Wei Chen</div>
      </div>
      <button className="iconbtn" style={{ background: "var(--bg-2)" }}><Icons.Bell size={16} /></button>
    </div>
  );
}

function CoachToday() {
  return (
    <div style={{ padding: "0 16px 24px" }}>
      <div style={{ background: "var(--surface)", borderRadius: 16, padding: 16, border: "1px solid var(--border)", marginBottom: 14 }}>
        <div className="text-xs text-muted" style={{ fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>Up next · Saturday</div>
        <div className="display" style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginTop: 4 }}>
          Giants vs. Red Sox
        </div>
        <div className="text-sm text-muted" style={{ marginTop: 2 }}>
          <Icons.Calendar size={12} style={{ verticalAlign: "-2px", marginRight: 4 }} />
          Sat 4/12 · 10:00 AM · Big Rec
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button className="btn btn--primary" style={{ flex: 1, justifyContent: "center", padding: "10px 12px" }}>
            <Icons.Pin size={14} /> Directions
          </button>
          <button className="btn" style={{ flex: 1, justifyContent: "center", padding: "10px 12px" }}>
            <Icons.Mail size={14} /> Notify team
          </button>
        </div>
      </div>

      <div style={{ background: "var(--surface)", borderRadius: 16, padding: 16, border: "1px solid var(--border)", marginBottom: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <div className="display" style={{ fontSize: 16, fontWeight: 600 }}>RSVPs · 9 of 11</div>
          <span className="text-xs text-muted">2 not replied</span>
        </div>
        <div style={{ display: "flex", marginTop: 10, gap: 6, flexWrap: "wrap" }}>
          {[
            ["MH","y"],["SC","y"],["LO","y"],["DR","y"],["OK","y"],
            ["AT","y"],["RM","y"],["WS","y"],["FA","y"],
            ["BL","?"],["QD","?"],
          ].map(([name, status], i) => (
            <div key={i} className="avatar avatar--giants" style={{ position: "relative", opacity: status === "y" ? 1 : 0.35 }}>
              {name}
              {status === "?" ? <span style={{ position: "absolute", bottom: -2, right: -2, width: 14, height: 14, borderRadius: "50%", background: "var(--warn)", border: "2px solid var(--surface)" }}/> : null}
            </div>
          ))}
        </div>
      </div>

      <div style={{ background: "var(--surface)", borderRadius: 16, padding: 16, border: "1px solid var(--border)", marginBottom: 14 }}>
        <div className="display" style={{ fontSize: 16, fontWeight: 600 }}>This week</div>
        <div style={{ marginTop: 8 }}>
          <PhoneRow icon={<Icons.Calendar size={14} />} title="Practice · Tue 4/8" sub="6:00 PM · West Sunset" />
          <PhoneRow icon={<Icons.Calendar size={14} />} title="Practice · Thu 4/10" sub="6:00 PM · West Sunset" />
          <PhoneRow icon={<Icons.Trophy size={14} />} title="Game · Sat 4/12" sub="10:00 AM · Big Rec" emphasis last />
        </div>
      </div>

      <div style={{ background: "var(--warn-soft)", borderRadius: 16, padding: 14, border: "1px solid var(--border)", display: "flex", gap: 12, alignItems: "flex-start" }}>
        <div className="alert__icon alert__icon--warn"><Icons.Warn size={15} /></div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 13.5 }}>Your concussion training expires Tuesday</div>
          <div className="text-xs text-muted" style={{ marginTop: 2 }}>10 minutes, online, free. Don't let Nate find out the hard way.</div>
        </div>
        <button className="btn btn--sm">Renew</button>
      </div>
    </div>
  );
}

function PhoneRow({ icon, title, sub, emphasis, last }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: last ? "" : "1px solid var(--border)" }}>
      <div style={{ width: 32, height: 32, borderRadius: 9, background: emphasis ? "var(--primary-soft)" : "var(--bg-3)", color: emphasis ? "var(--primary-soft-ink)" : "var(--ink-2)", display: "grid", placeItems: "center" }}>
        {icon}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, fontWeight: emphasis ? 600 : 500 }}>{title}</div>
        <div className="text-xs text-muted">{sub}</div>
      </div>
      <Icons.Chevron size={14} style={{ color: "var(--ink-3)" }} />
    </div>
  );
}

function CoachRoster() {
  const { PLAYERS } = window.SFLL_DATA;
  const roster = PLAYERS.filter(p => p.team === "t-giants");
  return (
    <div style={{ padding: "0 16px 24px" }}>
      <div style={{ background: "var(--surface)", borderRadius: 16, border: "1px solid var(--border)", overflow: "hidden" }}>
        {roster.map((p, i) => (
          <div key={p.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", borderBottom: i < roster.length - 1 ? "1px solid var(--border)" : "" }}>
            <Avatar player={p} size="lg" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 14.5 }}>
                #{p.jersey} {p.first} {p.last}
              </div>
              <div className="text-xs text-muted">
                {p.positions.join(" · ")} · Bats {p.bats}
              </div>
            </div>
            <a href="tel:" className="iconbtn" style={{ background: "var(--bg-2)" }}><Icons.Phone size={14} /></a>
            <a href="mailto:" className="iconbtn" style={{ background: "var(--bg-2)" }}><Icons.Mail size={14} /></a>
          </div>
        ))}
      </div>
    </div>
  );
}

function CoachLineup() {
  const order = [
    { pos: "CF", name: "Hernández", bats: "R", num: 7 },
    { pos: "SS", name: "Chen", bats: "R", num: 9 },
    { pos: "1B", name: "Kim", bats: "L", num: 5 },
    { pos: "3B", name: "Ramos", bats: "R", num: 21 },
    { pos: "C",  name: "Bryant", bats: "R", num: 31 },
    { pos: "2B", name: "Johansson", bats: "R", num: 17 },
    { pos: "LF", name: "Mercer", bats: "R", num: 22 },
    { pos: "RF", name: "Russo", bats: "L", num: 8 },
    { pos: "P",  name: "Park", bats: "L", num: 2 },
  ];
  return (
    <div style={{ padding: "0 16px 24px" }}>
      <div style={{ background: "var(--surface)", borderRadius: 16, border: "1px solid var(--border)", padding: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
          <div className="display" style={{ fontSize: 16, fontWeight: 600 }}>Today's lineup</div>
          <span className="pill pill--primary">Draft</span>
        </div>
        {order.map((p, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0", borderBottom: i < order.length - 1 ? "1px solid var(--border)" : "" }}>
            <div style={{ width: 22, fontFamily: "var(--font-num)", color: "var(--ink-3)", fontWeight: 600, fontSize: 13 }}>{i+1}</div>
            <div style={{ width: 32, height: 28, background: "var(--primary)", color: "var(--primary-ink)", borderRadius: 6, fontFamily: "var(--font-num)", display: "grid", placeItems: "center", fontWeight: 700, fontSize: 13 }}>{p.pos}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 14.5 }}>#{p.num} {p.name}</div>
              <div className="text-xs text-muted">Bats {p.bats}</div>
            </div>
            <Icons.Edit size={14} style={{ color: "var(--ink-3)" }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function CoachInbox() {
  return (
    <div style={{ padding: "0 16px 24px" }}>
      <div style={{ background: "var(--surface)", borderRadius: 16, border: "1px solid var(--border)", overflow: "hidden" }}>
        {[
          { from: "Maria Hernández", subj: "Mateo will be late Saturday", time: "8m", unread: true },
          { from: "Nate (SFLL)", subj: "Snack stand schedule — please share", time: "1h" },
          { from: "Patrick O'Brien", subj: "Catching warmup before Sat?", time: "3h" },
          { from: "Umpire-in-Chief", subj: "Plate ump confirmed for 4/12", time: "1d" },
          { from: "SFLL Board", subj: "All-Stars timeline", time: "2d" },
        ].map((m, i) => (
          <div key={i} style={{ padding: "12px 14px", borderBottom: i < 4 ? "1px solid var(--border)" : "", display: "flex", gap: 10, alignItems: "flex-start" }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: m.unread ? "var(--primary)" : "transparent", marginTop: 7 }} />
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{m.from}</div>
                <div className="text-xs text-muted">{m.time}</div>
              </div>
              <div className="text-sm text-muted" style={{ marginTop: 2 }}>{m.subj}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ───────────────────────────── Parent phone ─────────────────────────────
function ParentPhone({ tab, setTab }) {
  return (
    <IOSDevice width={390} height={780}>
      <div style={{
        background: "var(--bg)",
        color: "var(--ink)",
        minHeight: "100%",
        fontFamily: "var(--font-body)",
        display: "flex",
        flexDirection: "column",
        paddingTop: 56,
      }}>
        <ParentHeader />
        <div style={{ flex: 1 }}>
          {tab === "today"    ? <ParentToday /> : null}
          {tab === "schedule" ? <ParentSchedule /> : null}
          {tab === "account"  ? <ParentAccount /> : null}
          {tab === "comms"    ? <ParentInbox /> : null}
        </div>
        <PhoneTabBar tab={tab} setTab={setTab} tabs={[
          { v: "today",    icon: Icons.Home,     label: "Today" },
          { v: "schedule", icon: Icons.Calendar, label: "Schedule" },
          { v: "account",  icon: Icons.Trophy,   label: "Account" },
          { v: "comms",    icon: Icons.Mail,     label: "Inbox" },
        ]} />
      </div>
    </IOSDevice>
  );
}

function ParentHeader() {
  return (
    <div style={{ padding: "8px 18px 14px", display: "flex", alignItems: "center", gap: 10 }}>
      <div className="avatar" style={{ background: "var(--primary-soft)", color: "var(--primary-soft-ink)", width: 36, height: 36, fontSize: 13 }}>MH</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 17, letterSpacing: "-0.01em", lineHeight: 1.1 }}>Hi, María</div>
        <div className="text-xs text-muted">Hernández family · 1 player</div>
      </div>
      <button className="iconbtn" style={{ background: "var(--bg-2)" }}><Icons.Bell size={16} /></button>
    </div>
  );
}

function ParentToday() {
  return (
    <div style={{ padding: "0 16px 24px" }}>
      {/* Player card */}
      <div style={{ background: "var(--surface)", borderRadius: 16, padding: 14, border: "1px solid var(--border)", marginBottom: 14, display: "flex", gap: 12, alignItems: "center" }}>
        <div className="avatar avatar--giants" style={{ width: 56, height: 56, fontSize: 18 }}>MH</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 17 }}>Mateo Hernández</div>
          <div className="text-sm text-muted">Age 12 · Majors · #7</div>
          <div className="text-sm" style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 6 }}>
            <TeamSwatch teamId="t-giants" size="sm" />
            <span>Giants — Coach Chen</span>
          </div>
        </div>
      </div>

      {/* Next game CTA with RSVP */}
      <div style={{ background: "var(--surface)", borderRadius: 16, padding: 16, border: "1px solid var(--border)", marginBottom: 14 }}>
        <div className="text-xs text-muted" style={{ fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>Next game</div>
        <div className="display" style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.02em", marginTop: 4 }}>Giants vs. Red Sox</div>
        <div className="text-sm text-muted">Sat 4/12 · 10:00 AM · Big Rec, GG Park</div>
        <div className="text-xs text-muted" style={{ marginTop: 6 }}>Arrive 30 min early. Snack assignment: orange slices.</div>
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button className="btn btn--primary" style={{ flex: 1, justifyContent: "center", padding: "10px 12px" }}>
            <Icons.Check size={14} /> Mateo will be there
          </button>
          <button className="btn" style={{ padding: "10px 12px" }}>
            <Icons.X size={14} />
          </button>
        </div>
      </div>

      {/* RSVP for SES, volunteer */}
      <div style={{ background: "var(--surface)", borderRadius: 16, border: "1px solid var(--border)", overflow: "hidden", marginBottom: 14 }}>
        <PhoneRow icon={<Icons.Calendar size={14} />} title="Practice · Tue 4/8" sub="6:00 PM · West Sunset · You drive" />
        <PhoneRow icon={<Icons.Trophy size={14} />} title="Volunteer · Sat 4/12" sub="Snack stand 2–4 PM · with C. Martínez" />
        <PhoneRow icon={<Icons.Eval size={14} />} title="SES makeup · Thu 4/10" sub="Big Rec · 6:00 PM (Mateo missed Mar 1)" last />
      </div>

      {/* Compliance note */}
      <div style={{ background: "var(--primary-soft)", borderRadius: 16, padding: 14, border: "1px solid var(--border)", display: "flex", gap: 12, alignItems: "flex-start" }}>
        <div className="alert__icon alert__icon--info"><Icons.Sparkle size={15} /></div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 13.5 }}>Your photo release is on file. Thanks.</div>
          <div className="text-xs text-muted" style={{ marginTop: 2 }}>Renewed Feb 12. Good through this season + All-Stars.</div>
        </div>
      </div>
    </div>
  );
}

function ParentSchedule() {
  const games = [
    { d: "Sat 4/12", t: "10:00 AM", opp: "vs. Red Sox", loc: "Big Rec",   meta: "Home" },
    { d: "Tue 4/16", t: "6:00 PM",  opp: "@ Athletics", loc: "West Sunset", meta: "Away · You drive" },
    { d: "Sun 4/20", t: "12:00 PM", opp: "vs. Yankees", loc: "Big Rec",   meta: "Home · Picture day" },
    { d: "Sat 4/26", t: "1:00 PM",  opp: "@ Rangers",   loc: "Funston",   meta: "Away" },
    { d: "Wed 4/30", t: "6:00 PM",  opp: "vs. Rays",    loc: "Big Rec",   meta: "Home" },
  ];
  return (
    <div style={{ padding: "0 16px 24px" }}>
      <div style={{ background: "var(--surface)", borderRadius: 16, border: "1px solid var(--border)", overflow: "hidden" }}>
        {games.map((g, i) => (
          <div key={i} style={{ padding: "14px", borderBottom: i < games.length - 1 ? "1px solid var(--border)" : "", display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 60, textAlign: "center" }}>
              <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>{g.d.split(" ")[0]}</div>
              <div className="display" style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.01em", lineHeight: 1 }}>{g.d.split(" ")[1]}</div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{g.opp}</div>
              <div className="text-xs text-muted">{g.t} · {g.loc}</div>
              <div className="text-xs" style={{ color: "var(--primary-soft-ink)", marginTop: 2 }}>{g.meta}</div>
            </div>
            <Icons.Chevron size={14} style={{ color: "var(--ink-3)" }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function ParentAccount() {
  return (
    <div style={{ padding: "0 16px 24px" }}>
      <div style={{ background: "var(--surface)", borderRadius: 16, padding: 16, border: "1px solid var(--border)", marginBottom: 14 }}>
        <div className="text-xs text-muted" style={{ textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>Balance</div>
        <div className="display" style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.02em", marginTop: 4, color: "var(--success)" }}>
          $0.00
        </div>
        <div className="text-xs text-muted">Paid in full · $425 · Feb 14</div>
      </div>

      <div style={{ background: "var(--surface)", borderRadius: 16, border: "1px solid var(--border)", overflow: "hidden", marginBottom: 14 }}>
        <PhoneRow icon={<Icons.Check size={14} />} title="Volunteer deposit · $150" sub="Held. Returned after 4 hours of shifts." />
        <PhoneRow icon={<Icons.Trophy size={14} />} title="Shifts completed · 2 of 4" sub="2 more before season ends" last />
      </div>

      <div style={{ background: "var(--surface)", borderRadius: 16, border: "1px solid var(--border)", overflow: "hidden" }}>
        <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border)", fontWeight: 600, fontSize: 13 }}>Documents</div>
        <PhoneRow icon={<Icons.Compliance size={14} />} title="Birth certificate · uploaded" sub="Feb 7" />
        <PhoneRow icon={<Icons.Compliance size={14} />} title="Photo release · signed" sub="Feb 12" />
        <PhoneRow icon={<Icons.Compliance size={14} />} title="Medical form · signed" sub="Feb 12" last />
      </div>
    </div>
  );
}

function ParentInbox() {
  return (
    <div style={{ padding: "0 16px 24px" }}>
      <div style={{ background: "var(--surface)", borderRadius: 16, border: "1px solid var(--border)", overflow: "hidden" }}>
        {[
          { from: "Coach Chen", subj: "Practice moved to West Sunset", time: "2h", unread: true },
          { from: "SFLL", subj: "Picture day 4/20 — order info", time: "Yesterday" },
          { from: "Coach Chen", subj: "Welcome to the Giants!", time: "5d" },
          { from: "SFLL", subj: "Your registration is confirmed", time: "3w" },
        ].map((m, i) => (
          <div key={i} style={{ padding: "12px 14px", borderBottom: i < 3 ? "1px solid var(--border)" : "", display: "flex", gap: 10, alignItems: "flex-start" }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: m.unread ? "var(--primary)" : "transparent", marginTop: 7 }} />
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{m.from}</div>
                <div className="text-xs text-muted">{m.time}</div>
              </div>
              <div className="text-sm text-muted" style={{ marginTop: 2 }}>{m.subj}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────── tab bar (shared) ───────────────────────
function PhoneTabBar({ tab, setTab, tabs }) {
  return (
    <div style={{
      background: "color-mix(in oklch, var(--surface) 88%, transparent)",
      backdropFilter: "blur(10px)",
      borderTop: "1px solid var(--border)",
      display: "flex",
      padding: "8px 0 30px",
    }}>
      {tabs.map(t => {
        const active = tab === t.v;
        return (
          <button key={t.v} onClick={() => setTab(t.v)} style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 3,
            padding: "6px 0",
            background: "transparent",
            border: 0,
            color: active ? "var(--primary)" : "var(--ink-3)",
            cursor: "pointer",
          }}>
            <t.icon size={20} />
            <span style={{ fontSize: 10.5, fontWeight: active ? 600 : 500 }}>{t.label}</span>
          </button>
        );
      })}
    </div>
  );
}

window.FieldMode = FieldMode;

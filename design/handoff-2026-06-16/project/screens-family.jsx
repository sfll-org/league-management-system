/* global window, React, Icons */
// Family detail

const { useState } = React;
const { Avatar, Pill, Button, Card, EditableText, TeamSwatch } = window.UI;

function FamilyDetail({ go, familyId }) {
  const { FAMILIES, PLAYERS, TEAMS } = window.SFLL_DATA;
  const family = FAMILIES[familyId] || FAMILIES["fam-hernandez"];
  const players = family.players.map(pid => PLAYERS.find(p => p.id === pid)).filter(Boolean);

  return (
    <div className="page">
      <div style={{ marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
        <button className="btn btn--ghost btn--sm" onClick={() => go("dashboard")}>
          <Icons.ArrowLeft size={14} /> Back
        </button>
        <span style={{ color: "var(--ink-4)" }}>/</span>
        <span className="text-sm text-muted">Families</span>
      </div>

      <div className="page-header" style={{ alignItems: "center" }}>
        <div className="avatar avatar--xl" style={{ background: "var(--primary-soft)", color: "var(--primary-soft-ink)" }}>
          {family.surname[0]}
        </div>
        <div style={{ marginLeft: 14 }}>
          <h1 className="page-title">The {family.surname} family</h1>
          <div className="page-sub" style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 6 }}>
            <Icons.Pin size={13} />
            {family.address}
            <Pill kind="neutral">{family.neighborhood}</Pill>
          </div>
        </div>
        <div className="page-header__actions">
          <Button variant="ghost" leadingIcon={Icons.Phone}>Call</Button>
          <Button variant="ghost" leadingIcon={Icons.Mail}>Email</Button>
          <Button variant="primary" leadingIcon={Icons.Edit}>Edit</Button>
        </div>
      </div>

      <div className="detail-grid">
        <div className="flex-col" style={{ gap: "var(--gap-lg)" }}>
          {/* Players */}
          <Card title="Players" sub={`${players.length} kid${players.length === 1 ? "" : "s"} in the league`} padding={false}>
            <div className="card__list">
              {players.map(p => {
                const team = TEAMS.find(t => t.id === p.team);
                return (
                  <div key={p.id} className="alert" onClick={() => go("player", p.id)}>
                    <Avatar player={p} size="lg" />
                    <div className="alert__body">
                      <div className="alert__title">
                        {p.first} {p.last}
                        {p.top4 ? <span style={{ color: "var(--accent)", marginLeft: 6 }}><Icons.Top4 size={12} /></span> : null}
                      </div>
                      <div className="alert__sub">
                        Age {p.age} · {p.positions.join(" · ")} ·{" "}
                        {team
                          ? <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                              <TeamSwatch teamId={team.id} size="sm" /> {team.name}
                            </span>
                          : <span style={{ color: "var(--warn)" }}>No team yet</span>}
                      </div>
                    </div>
                    <Icons.Chevron size={14} style={{ color: "var(--ink-3)" }} />
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Contacts */}
          <Card title="Contacts">
            <div className="detail-row" style={{ borderTop: 0 }}>
              <div className="detail-row__label">Primary</div>
              <div className="detail-row__value"><EditableText value={family.primary} onChange={() => {}} /></div>
            </div>
            <div className="detail-row">
              <div className="detail-row__label">Secondary</div>
              <div className="detail-row__value"><EditableText value={family.secondary} onChange={() => {}} /></div>
            </div>
            <div className="detail-row">
              <div className="detail-row__label">Phone</div>
              <div className="detail-row__value mono"><EditableText value={family.phone} onChange={() => {}} /></div>
            </div>
            <div className="detail-row">
              <div className="detail-row__label">Email</div>
              <div className="detail-row__value"><EditableText value={family.email} onChange={() => {}} /></div>
            </div>
            <div className="detail-row">
              <div className="detail-row__label">Additional</div>
              <div className="detail-row__value text-muted"><EditableText value={family.secondaryEmail} onChange={() => {}} /></div>
            </div>
            <div className="detail-row">
              <div className="detail-row__label">Address</div>
              <div className="detail-row__value"><EditableText value={family.address} onChange={() => {}} /></div>
            </div>
          </Card>

          {/* Notes */}
          {family.notes ? (
            <Card title="Notes">
              <p className="text-sm" style={{ margin: 0 }}>{family.notes}</p>
            </Card>
          ) : null}
        </div>

        {/* Right column */}
        <div className="flex-col" style={{ gap: "var(--gap-lg)" }}>
          <Card title="Account">
            <div className="detail-row" style={{ borderTop: 0 }}>
              <div className="detail-row__label">Balance</div>
              <div className="detail-row__value">
                {family.balance === 0
                  ? <Pill kind="success">Paid in full · ${family.paid}</Pill>
                  : family.balance < 0
                    ? <Pill kind="warn">${Math.abs(family.balance)} credit</Pill>
                    : <Pill kind="danger">${family.balance} due</Pill>}
              </div>
            </div>
            <div className="detail-row">
              <div className="detail-row__label">Volunteer deposit</div>
              <div className="detail-row__value">
                <Pill kind={family.volunteerDeposit === "Held" ? "primary" : "neutral"}>{family.volunteerDeposit}</Pill>
              </div>
            </div>
            <div className="detail-row">
              <div className="detail-row__label">Reminders sent</div>
              <div className="detail-row__value text-sm mono">
                {family.balance > 0 ? "Apr 3, Apr 17 — both opened" : "—"}
              </div>
            </div>
          </Card>

          <Card title="Volunteer" padding={false}>
            <div className="card__list">
              <div className="alert">
                <div className="alert__icon alert__icon--success"><Icons.Check size={14} /></div>
                <div className="alert__body">
                  <div className="alert__title">Snack stand · Sat 4/12</div>
                  <div className="alert__sub">2pm–4pm · Big Rec</div>
                </div>
              </div>
              <div className="alert">
                <div className="alert__icon alert__icon--info"><Icons.Calendar size={14} /></div>
                <div className="alert__body">
                  <div className="alert__title">Field setup · Sun 4/13</div>
                  <div className="alert__sub">8am–9am · Big Rec</div>
                </div>
              </div>
            </div>
          </Card>

          <Card title="Communications" padding={false}>
            <div className="card__list">
              <div className="alert">
                <div className="alert__icon alert__icon--info"><Icons.Mail size={14} /></div>
                <div className="alert__body">
                  <div className="alert__title">Spring 2026 schedule</div>
                  <div className="alert__sub">Sent · Opened by primary, secondary</div>
                </div>
                <div className="alert__meta">5d</div>
              </div>
              <div className="alert">
                <div className="alert__icon alert__icon--success"><Icons.Check size={14} /></div>
                <div className="alert__body">
                  <div className="alert__title">SES RSVP</div>
                  <div className="alert__sub">Confirmed for Sat 3/1, Sun 3/2</div>
                </div>
                <div className="alert__meta">3w</div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

window.FamilyDetail = FamilyDetail;

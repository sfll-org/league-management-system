/* global window, React, Icons */
// Shared UI: Avatar, StatusPill, Button, Card, Toolbar, EditableField, etc.

const { useState, useRef, useEffect } = React;

function Avatar({ player, size = "md" }) {
  const cls = size === "sm" ? "avatar avatar--sm"
            : size === "lg" ? "avatar avatar--lg"
            : size === "xl" ? "avatar avatar--xl"
            : "avatar";
  const initials = `${player.first[0]}${player.last[0]}`;
  const team = (window.SFLL_DATA.TEAMS.find(t => t.id === player.team) || {});
  const teamCls = team.color ? ` avatar--${team.color}` : "";
  return (
    <span className={cls + teamCls} title={player.first + " " + player.last}>
      {initials}
    </span>
  );
}

function TeamSwatch({ teamId, size = "md" }) {
  const team = window.SFLL_DATA.TEAMS.find(t => t.id === teamId);
  if (!team) {
    const sz = size === "sm" ? 22 : 28;
    return <span className="avatar" style={{ width: sz, height: sz, fontSize: 10, color: "var(--ink-3)" }}>—</span>;
  }
  const initials = team.name === "Red Sox" ? "RS"
                 : team.name === "Athletics" ? "A's"
                 : team.name[0];
  return (
    <span className={"avatar" + (size === "sm" ? " avatar--sm" : "") + " avatar--" + team.color}>
      {initials}
    </span>
  );
}

function Pill({ kind = "neutral", children, dot, icon }) {
  return (
    <span className={"pill pill--" + kind}>
      {dot ? <span className="pill__dot" /> : null}
      {icon ? icon : null}
      {children}
    </span>
  );
}

function Button({ children, variant = "default", size, icon: Icon, leadingIcon: LeadingIcon, onClick, type, ...rest }) {
  const cls = ["btn"];
  if (variant !== "default") cls.push("btn--" + variant);
  if (size === "sm") cls.push("btn--sm");
  if (Icon && !children) cls.push("btn--icon");
  return (
    <button type={type || "button"} className={cls.join(" ")} onClick={onClick} {...rest}>
      {LeadingIcon ? <LeadingIcon size={14} /> : null}
      {children}
      {Icon ? <Icon size={14} /> : null}
    </button>
  );
}

function Card({ title, sub, action, children, padding = true, className }) {
  return (
    <div className={"card " + (className || "")}>
      {title || action ? (
        <div className="card__head">
          {title ? (
            <div className="card__title">
              {title}
              {sub ? <span className="card__title-sub">{sub}</span> : null}
            </div>
          ) : null}
          {action ? action : null}
        </div>
      ) : null}
      <div className={padding ? "card__body" : ""}>{children}</div>
    </div>
  );
}

function Stat({ label, value, delta, deltaKind = "flat", icon }) {
  return (
    <div className="stat">
      <div className="stat__label">{label}{icon ? icon : null}</div>
      <div className="stat__value tabular">{value}</div>
      {delta ? <div className={"stat__delta stat__delta--" + deltaKind}>{delta}</div> : null}
    </div>
  );
}

function Segmented({ options, value, onChange }) {
  return (
    <div className="seg">
      {options.map(opt => (
        <button key={opt.value}
          className={"seg__btn " + (value === opt.value ? "seg__btn--active" : "")}
          onClick={() => onChange(opt.value)}>
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function SearchInput({ value, onChange, placeholder = "Search…" }) {
  return (
    <div className="input">
      <Icons.Search size={14} style={{ color: "var(--ink-3)" }} />
      <input value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} />
    </div>
  );
}

function Chip({ children, active, onClick, onRemove }) {
  return (
    <button className={"chip " + (active ? "chip--active" : "")} onClick={onClick}>
      {children}
      {onRemove ? <span className="chip__x" onClick={(e) => { e.stopPropagation(); onRemove(); }}>×</span> : null}
    </button>
  );
}

// Inline editable field. Click → edit; blur or Enter → save.
function EditableText({ value, onChange, type = "text", placeholder, suffix, className }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef(null);

  useEffect(() => { setDraft(value); }, [value]);
  useEffect(() => { if (editing && inputRef.current) inputRef.current.select(); }, [editing]);

  function commit() {
    setEditing(false);
    if (draft !== value) onChange(draft);
  }
  function cancel() {
    setEditing(false);
    setDraft(value);
  }

  if (editing) {
    return (
      <span className={"editable " + (className || "")}>
        <input
          ref={inputRef}
          type={type}
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={e => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") cancel();
          }}
        />
      </span>
    );
  }
  return (
    <span
      className={"editable " + (className || "")}
      tabIndex={0}
      onClick={() => setEditing(true)}
      onKeyDown={e => { if (e.key === "Enter") setEditing(true); }}
      role="button"
    >
      {value || <span style={{ color: "var(--ink-4)" }}>{placeholder || "—"}</span>}
      {suffix ? <span style={{ color: "var(--ink-3)", marginLeft: 6 }}>{suffix}</span> : null}
    </span>
  );
}

function EditableSelect({ value, options, onChange }) {
  const [editing, setEditing] = useState(false);
  const ref = useRef(null);
  useEffect(() => { if (editing && ref.current) ref.current.focus(); }, [editing]);

  if (editing) {
    return (
      <span className="editable">
        <select
          ref={ref}
          value={value}
          onChange={e => { onChange(e.target.value); setEditing(false); }}
          onBlur={() => setEditing(false)}
        >
          {options.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </span>
    );
  }
  const label = (options.find(o => o.value === value) || {}).label || "—";
  return (
    <span className="editable" tabIndex={0} onClick={() => setEditing(true)} role="button">
      {label}
    </span>
  );
}

function ComplianceBadge({ status }) {
  if (status === "ok") return <Pill kind="success" dot>Cleared</Pill>;
  if (status === "warn") return <Pill kind="warn" dot>Expires soon</Pill>;
  if (status === "missing") return <Pill kind="danger" dot>Missing</Pill>;
  return <Pill kind="ghost" dot>—</Pill>;
}

window.UI = {
  Avatar, TeamSwatch, Pill, Button, Card, Stat, Segmented, SearchInput,
  Chip, EditableText, EditableSelect, ComplianceBadge,
};

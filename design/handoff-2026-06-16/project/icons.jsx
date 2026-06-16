/* global window, React */
// Small SVG icon set. Stroke-based, 1.5px, currentColor.
const { createElement: h } = React;

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

const I = (paths) => function Icon({ size = 16, className, style }) {
  return h(
    "svg",
    { width: size, height: size, viewBox: "0 0 20 20", className, style, ...stroke },
    ...paths.map((p, i) => typeof p === "string"
      ? h("path", { key: i, d: p })
      : h(p.tag, { key: i, ...p.attrs }))
  );
};

const Icons = {
  Dashboard:  I(["M3 10l7-6 7 6", "M5 9v7h4v-4h2v4h4V9"]),
  Players:    I(["M7 8a2.5 2.5 0 100-5 2.5 2.5 0 000 5z", "M3 17c0-2.5 2-4 4-4s4 1.5 4 4", "M14 9a2 2 0 100-4 2 2 0 000 4z", "M12 17c0-2 1.6-3.5 3.5-3.5S19 15 19 17"]),
  Family:     I(["M5 17v-2a3 3 0 013-3h4a3 3 0 013 3v2", "M10 9a3 3 0 100-6 3 3 0 000 6z", "M16 11c1.5 0 3 1 3 3v1"]),
  Teams:      I(["M3 10a7 7 0 1014 0 7 7 0 00-14 0z", "M3 10h14", "M10 3c2 2 2 12 0 14", "M10 3c-2 2-2 12 0 14"]),
  Calendar:   I(["M4 7h12v10H4z", "M4 7V5h12v2", "M8 3v4", "M12 3v4", "M4 11h12"]),
  Draft:      I(["M4 5h12", "M4 10h12", "M4 15h7", "M14 13l4 4", "M14 17l4-4"]),
  Eval:       I(["M5 4h10v12H5z", "M8 8h4", "M8 11h4", "M8 14h2"]),
  Comms:      I(["M3 5l7 5 7-5", "M3 5v10h14V5"]),
  Compliance: I(["M10 3l6 3v4c0 4-3 6-6 7-3-1-6-3-6-7V6l6-3z", "M7 10l2 2 4-4"]),
  Imports:    I(["M10 3v9", "M6 9l4 4 4-4", "M4 16h12"]),
  Audit:      I(["M4 4h10l3 3v9H4z", "M8 9h6", "M8 12h6", "M8 15h4"]),
  Settings:   I(["M10 4v2", "M10 14v2", "M4 10h2", "M14 10h2", "M5.5 5.5l1.5 1.5", "M13 13l1.5 1.5", "M5.5 14.5L7 13", "M13 7l1.5-1.5", "M10 13a3 3 0 100-6 3 3 0 000 6z"]),
  Search:     I(["M9 16a7 7 0 100-14 7 7 0 000 14z", "M17 17l-3.5-3.5"]),
  Plus:       I(["M10 4v12", "M4 10h12"]),
  Chevron:    I(["M7 5l5 5-5 5"]),
  ChevronDown:I(["M5 8l5 5 5-5"]),
  Filter:     I(["M3 5h14", "M6 10h8", "M9 15h2"]),
  Print:      I(["M6 4h8v4H6z", "M4 8h12v6H4z", "M6 14h8v3H6z", "M7 11h6"]),
  Check:      I(["M4 10l4 4 8-9"]),
  X:          I(["M5 5l10 10", "M15 5L5 15"]),
  Edit:       I(["M3 17h4l9-9-4-4-9 9z", "M12 4l4 4"]),
  Bell:       I(["M5 14V9a5 5 0 0110 0v5", "M3 14h14", "M8 16a2 2 0 004 0"]),
  Sparkle:    I(["M10 4l1.5 4.5L16 10l-4.5 1.5L10 16l-1.5-4.5L4 10l4.5-1.5z"]),
  Warn:       I(["M10 4l8 14H2L10 4z", "M10 9v4", "M10 16h.01"]),
  Info:       I(["M10 17a7 7 0 100-14 7 7 0 000 14z", "M10 9v4", "M10 7h.01"]),
  Field:      I(["M10 2l8 5v6l-8 5-8-5V7z", "M10 2v16", "M2 7l8 5 8-5"]),
  Trophy:     I(["M6 4h8v4a4 4 0 11-8 0V4z", "M6 6H4v1a2 2 0 002 2", "M14 6h2v1a2 2 0 01-2 2", "M8 14h4v3H8z"]),
  Phone:      I(["M5 4h3l2 4-2 1a8 8 0 004 4l1-2 4 2v3a2 2 0 01-2 2A12 12 0 013 6a2 2 0 012-2z"]),
  Mail:       I(["M3 5h14v10H3z", "M3 5l7 6 7-6"]),
  Home:       I(["M3 10l7-6 7 6", "M5 9v7h10V9"]),
  Pin:        I(["M10 17v-5", "M6 8a4 4 0 118 0c0 3-4 7-4 7s-4-4-4-7z"]),
  ArrowLeft:  I(["M9 5l-5 5 5 5", "M4 10h12"]),
  Top4:       I(["M10 2l2.5 5 5.5.8-4 4 1 5.5L10 14.5 5 17.3l1-5.5-4-4L7.5 7z"]),
  Coach:      I(["M3 8h14l-2 8H5z", "M5 8V6a5 5 0 0110 0v2"]),
  Diamond:    I(["M10 3l7 7-7 7-7-7z"]),
  CommandKey: I(["M7 5h6v6H7z", "M5 5a2 2 0 012-2h0a2 2 0 012 2", "M13 5a2 2 0 012-2h0a2 2 0 012 2", "M5 11a2 2 0 012-2h0", "M13 11a2 2 0 002 2h0a2 2 0 002-2"]),
  Caret:      I(["M5 7l5 5 5-5"]),
  Eye:        I(["M2 10s3-6 8-6 8 6 8 6-3 6-8 6-8-6-8-6z", "M10 13a3 3 0 100-6 3 3 0 000 6z"]),
  Trash:      I(["M4 6h12", "M8 6V4h4v2", "M5 6l1 11h8l1-11"]),
  Star:       I(["M10 3l2.5 5 5.5.8-4 4 1 5.5L10 15.5 5 18.3l1-5.5-4-4L7.5 8z"]),
  Sun:        I(["M10 4V2", "M10 18v-2", "M4 10H2", "M18 10h-2", "M5.5 5.5L4 4", "M16 16l-1.5-1.5", "M5.5 14.5L4 16", "M16 4l-1.5 1.5", "M10 14a4 4 0 100-8 4 4 0 000 8z"]),
};

window.Icons = Icons;

/* global window */
// Sample data for SFLL — San Francisco Little League.
// All names fabricated; demographics reflect SF.

const TEAMS = [
  { id: 't-giants',    name: "Giants",    color: "giants",   coach: "Ramos",     subLeague: "American" },
  { id: 't-athletics', name: "Athletics", color: "athletics", coach: "Tanaka",   subLeague: "American" },
  { id: 't-yankees',   name: "Yankees",   color: "yankees",  coach: "O'Brien",   subLeague: "American" },
  { id: 't-redsox',    name: "Red Sox",   color: "redsox",   coach: "Park",      subLeague: "American" },
  { id: 't-rangers',   name: "Rangers",   color: "rangers",  coach: "Singh",     subLeague: "American" },
  { id: 't-rays',      name: "Rays",      color: "rays",     coach: "Mendoza",   subLeague: "American" },
  { id: 't-dodgers',   name: "Dodgers",   color: "dodgers",  coach: "Chen",      subLeague: "National" },
  { id: 't-cubs',      name: "Cubs",      color: "cubs",     coach: "Hernández", subLeague: "National" },
  { id: 't-cardinals', name: "Cardinals", color: "cardinals",coach: "Patel",     subLeague: "National" },
  { id: 't-phillies',  name: "Phillies",  color: "phillies", coach: "Walker",    subLeague: "National" },
  { id: 't-brewers',   name: "Brewers",   color: "brewers",  coach: "Nakamura",  subLeague: "National" },
  { id: 't-astros',    name: "Astros",    color: "astros",   coach: "García",    subLeague: "National" },
];

const DIVISIONS = [
  // Baseball, oldest → youngest
  { id: "seniors",  name: "Seniors",     ages: "14–16", players: 28,  teams: 2,  track: "baseball" },
  { id: "juniors",  name: "Juniors",     ages: "12–14", players: 36,  teams: 3,  track: "baseball" },
  { id: "majors",   name: "Majors",      ages: "10–12", players: 132, teams: 12, track: "baseball" },
  { id: "aaa",      name: "AAA",         ages: "9–11",  players: 108, teams: 9,  track: "baseball" },
  { id: "aa",       name: "AA",          ages: "8–10",  players: 96,  teams: 8,  track: "baseball" },
  { id: "rookie",   name: "Rookie",      ages: "7–8",   players: 72,  teams: 6,  track: "baseball" },
  { id: "upper",    name: "Upper Farm",  ages: "6–7",   players: 60,  teams: 5,  track: "baseball" },
  { id: "lower",    name: "Lower Farm",  ages: "5–6",   players: 48,  teams: 4,  track: "baseball" },
  { id: "tball",    name: "T-Ball",      ages: "4–5",   players: 40,  teams: 4,  track: "baseball" },
  // Softball
  { id: "softball", name: "Softball",    ages: "8–14",  players: 64,  teams: 6,  track: "softball" },
  // Challenger
  { id: "chall",    name: "Challenger",  ages: "All",   players: 18,  teams: 2,  track: "challenger" },
];

const FIELDS = [
  "Big Rec (GG Park)",
  "West Sunset",
  "Funston Field",
  "Crocker-Amazon",
  "Glen Park",
  "Moscone Rec",
  "Jackson Playground",
  "Rossi Park",
];

// — Players (sample — Majors division) —
const PLAYERS = [
  { id: "p001", first: "Mateo",   last: "Hernández",  dob: "2014-04-12", age: 12, division: "majors", team: "t-giants",    sub: "American", topRank: 3, top4: true,  coachChild: false, status: "active",  jersey: 7,  bats: "R", throws: "R", positions: ["P","SS"], gpa: 87 },
  { id: "p002", first: "Sebastián", last: "Chen",     dob: "2014-08-03", age: 11, division: "majors", team: "t-giants",    sub: "American", topRank: 7, top4: false, coachChild: true,  status: "active",  jersey: 9,  bats: "R", throws: "R", positions: ["1B","P"], gpa: 81 },
  { id: "p003", first: "Aiden",   last: "Park",       dob: "2014-11-22", age: 11, division: "majors", team: "t-redsox",    sub: "American", topRank: 1, top4: true,  coachChild: false, status: "active",  jersey: 2,  bats: "L", throws: "L", positions: ["P","CF"], gpa: 94 },
  { id: "p004", first: "Liam",    last: "O'Brien",    dob: "2014-02-15", age: 12, division: "majors", team: "t-yankees",   sub: "American", topRank: 4, top4: true,  coachChild: true,  status: "active",  jersey: 12, bats: "R", throws: "R", positions: ["C","3B"], gpa: 78 },
  { id: "p005", first: "Diego",   last: "Ramos",      dob: "2013-12-05", age: 12, division: "majors", team: "t-giants",    sub: "American", topRank: 12, top4: false, coachChild: true, status: "active",  jersey: 21, bats: "R", throws: "R", positions: ["2B","OF"], gpa: 72 },
  { id: "p006", first: "Kai",     last: "Tanaka",     dob: "2014-06-30", age: 11, division: "majors", team: "t-athletics", sub: "American", topRank: 6, top4: false, coachChild: true,  status: "active",  jersey: 11, bats: "L", throws: "R", positions: ["CF","P"], gpa: 83 },
  { id: "p007", first: "Noah",    last: "Walker",     dob: "2014-09-18", age: 11, division: "majors", team: "t-phillies",  sub: "National", topRank: 9, top4: false, coachChild: true,  status: "active",  jersey: 4,  bats: "R", throws: "R", positions: ["SS","3B"], gpa: 80 },
  { id: "p008", first: "Ethan",   last: "Singh",      dob: "2013-10-08", age: 12, division: "majors", team: "t-rangers",   sub: "American", topRank: 5, top4: false, coachChild: true,  status: "active",  jersey: 16, bats: "R", throws: "R", positions: ["P","1B"], gpa: 76 },
  { id: "p009", first: "Lucas",   last: "Patel",      dob: "2014-01-19", age: 12, division: "majors", team: "t-cardinals", sub: "National", topRank: 8, top4: false, coachChild: true,  status: "active",  jersey: 23, bats: "R", throws: "R", positions: ["LF","P"], gpa: 79 },
  { id: "p010", first: "Asher",   last: "Nakamura",   dob: "2014-07-25", age: 11, division: "majors", team: "t-brewers",   sub: "National", topRank: 11, top4: false, coachChild: true, status: "active",  jersey: 8,  bats: "L", throws: "R", positions: ["RF","2B"], gpa: 85 },
  { id: "p011", first: "Theo",    last: "Mendoza",    dob: "2013-11-11", age: 12, division: "majors", team: "t-rays",      sub: "American", topRank: 2, top4: true,  coachChild: true,  status: "active",  jersey: 14, bats: "R", throws: "R", positions: ["P","CF"], gpa: 91 },
  { id: "p012", first: "Jasper",  last: "García",     dob: "2014-05-09", age: 12, division: "majors", team: "t-astros",    sub: "National", topRank: 10, top4: false, coachChild: true, status: "active",  jersey: 6,  bats: "R", throws: "R", positions: ["3B","P"], gpa: 74 },

  // Drafted players (round 2+, fewer details needed for list view)
  { id: "p013", first: "Owen",    last: "Kim",        dob: "2014-03-22", age: 12, division: "majors", team: "t-giants",    sub: "American", topRank: 18, top4: false, coachChild: false, status: "active", jersey: 5,  bats: "L", throws: "L", positions: ["1B","OF"], gpa: 88 },
  { id: "p014", first: "Caleb",   last: "Johansson",  dob: "2014-08-14", age: 11, division: "majors", team: "t-dodgers",   sub: "National", topRank: 14, top4: false, coachChild: false, status: "active", jersey: 17, bats: "R", throws: "R", positions: ["SS","2B"], gpa: 82 },
  { id: "p015", first: "Rowan",   last: "Mercer",     dob: "2013-12-30", age: 12, division: "majors", team: "t-cubs",      sub: "National", topRank: 16, top4: false, coachChild: false, status: "active", jersey: 22, bats: "R", throws: "R", positions: ["3B","C"], gpa: 77 },
  { id: "p016", first: "Eliana",  last: "Vázquez",    dob: "2014-04-04", age: 12, division: "majors", team: "t-athletics", sub: "American", topRank: 13, top4: false, coachChild: false, status: "active", jersey: 13, bats: "R", throws: "R", positions: ["P","CF"], gpa: 96 },
  { id: "p017", first: "Maya",    last: "Okonkwo",    dob: "2014-06-17", age: 11, division: "majors", team: "t-yankees",   sub: "American", topRank: 17, top4: false, coachChild: false, status: "active", jersey: 3,  bats: "R", throws: "R", positions: ["2B","SS"], gpa: 89 },
  { id: "p018", first: "Sofia",   last: "Russo",      dob: "2014-02-08", age: 12, division: "majors", team: "t-redsox",    sub: "American", topRank: 19, top4: false, coachChild: false, status: "active", jersey: 8,  bats: "L", throws: "R", positions: ["1B","OF"], gpa: 84 },
  { id: "p019", first: "Beckham", last: "Lopez",      dob: "2014-07-12", age: 11, division: "majors", team: "t-rangers",   sub: "American", topRank: 22, top4: false, coachChild: false, status: "active", jersey: 19, bats: "R", throws: "R", positions: ["OF","C"], gpa: 73 },
  { id: "p020", first: "Quinn",   last: "Doyle",      dob: "2013-11-29", age: 12, division: "majors", team: "t-rays",      sub: "American", topRank: 20, top4: false, coachChild: false, status: "active", jersey: 27, bats: "R", throws: "R", positions: ["P","3B"], gpa: 81 },
  { id: "p021", first: "Henry",   last: "Bryant",     dob: "2014-09-02", age: 11, division: "majors", team: "t-phillies",  sub: "National", topRank: 24, top4: false, coachChild: false, status: "active", jersey: 31, bats: "R", throws: "R", positions: ["OF","2B"], gpa: 76 },
  { id: "p022", first: "Wyatt",   last: "Sterling",   dob: "2014-01-25", age: 12, division: "majors", team: "t-cardinals", sub: "National", topRank: 21, top4: false, coachChild: false, status: "active", jersey: 10, bats: "R", throws: "R", positions: ["C","1B"], gpa: 79 },
  { id: "p023", first: "Milo",    last: "Yamamoto",   dob: "2014-05-30", age: 12, division: "majors", team: "t-brewers",   sub: "National", topRank: 26, top4: false, coachChild: false, status: "active", jersey: 26, bats: "L", throws: "L", positions: ["P","OF"], gpa: 86 },
  { id: "p024", first: "Felix",   last: "Andersson",  dob: "2014-10-08", age: 11, division: "majors", team: "t-astros",    sub: "National", topRank: 23, top4: false, coachChild: false, status: "active", jersey: 18, bats: "R", throws: "R", positions: ["SS","P"], gpa: 90 },
  { id: "p025", first: "Avery",   last: "Tran",       dob: "2014-08-19", age: 11, division: "majors", team: null,          sub: "American", topRank: 28, top4: false, coachChild: false, status: "unassigned", jersey: null, bats: "R", throws: "R", positions: ["2B","OF"], gpa: 75 },
  { id: "p026", first: "Riley",   last: "Mascarenhas",dob: "2014-03-11", age: 12, division: "majors", team: null,          sub: "National", topRank: 32, top4: false, coachChild: false, status: "unassigned", jersey: null, bats: "R", throws: "R", positions: ["OF","1B"], gpa: 69 },
];

const FAMILIES = {
  "fam-hernandez": {
    id: "fam-hernandez",
    surname: "Hernández",
    primary: "María Hernández",
    secondary: "Esteban Hernández",
    address: "1247 Capp St, San Francisco, CA 94110",
    neighborhood: "Mission",
    phone: "(415) 555-0142",
    email: "maria.hernandez@example.com",
    secondaryEmail: "esteban.h@example.com",
    players: ["p001"],
    balance: 0,
    paid: 425,
    volunteerDeposit: "Held",
    notes: "Esteban coaches AA Cubs (younger brother).",
  },
  "fam-chen": {
    id: "fam-chen",
    surname: "Chen",
    primary: "Wei Chen",
    secondary: "Linh Chen",
    address: "2841 Anza St, San Francisco, CA 94121",
    neighborhood: "Outer Richmond",
    phone: "(415) 555-0193",
    email: "wei.chen@example.com",
    players: ["p002"],
    balance: -50,
    paid: 425,
    volunteerDeposit: "Held",
    notes: "Wei is Head Coach, Giants (Majors).",
  },
  "fam-park": {
    id: "fam-park",
    surname: "Park",
    primary: "Jin Park",
    secondary: "Susan Park",
    address: "445 Cole St, San Francisco, CA 94117",
    neighborhood: "Cole Valley",
    phone: "(415) 555-0227",
    email: "jin.park@example.com",
    players: ["p003"],
    balance: 0,
    paid: 425,
    volunteerDeposit: "Held",
    notes: "",
  },
  "fam-obrien": {
    id: "fam-obrien",
    surname: "O'Brien",
    primary: "Kate O'Brien",
    secondary: "Patrick O'Brien",
    address: "1922 19th Ave, San Francisco, CA 94116",
    neighborhood: "Sunset",
    phone: "(415) 555-0381",
    email: "kate.obrien@example.com",
    players: ["p004"],
    balance: 0,
    paid: 425,
    volunteerDeposit: "Held",
    notes: "Patrick is Head Coach, Yankees (Majors).",
  },
};

// what needs attention
const ATTENTION = [
  { id: "a1", level: "danger",  title: "2 players still don't have a team",   sub: "Both are Top-4 protected. Draft was 6 days ago.", route: { name: "draft" }, meta: "6d" },
  { id: "a2", level: "warn",    title: "Concussion training expires Tue",     sub: "4 coaches: Walker, Chen, Singh, Mendoza.",       route: { name: "compliance" }, meta: "2d" },
  { id: "a3", level: "warn",    title: "SES makeup needs a date",             sub: "9 kids missed Session #4 — none rescheduled.",  route: { name: "ses" }, meta: "Thu" },
  { id: "a4", level: "info",    title: "Import flagged 3 division changes",   sub: "Liam Garcia bumped from AA → AAA in registration.", route: { name: "imports" }, meta: "1h" },
  { id: "a5", level: "warn",    title: "Mascarenhas family — balance unpaid", sub: "$425 outstanding. Auto-reminder sent twice.",    route: { name: "family", id: "fam-mascarenhas" }, meta: "5d" },
  { id: "a6", level: "info",    title: "Snack stand schedule has 3 gaps",     sub: "Sat 4/19 (4–6pm), Sun 4/20 (12–2pm and 2–4pm).", route: { name: "comms" }, meta: "1w" },
  { id: "a7", level: "success", title: "All Majors evals submitted",          sub: "First time this has happened on time. Don't ask.", route: { name: "ses" }, meta: "now" },
];

// SES sessions
const SESSIONS = [
  { id: "s1", name: "Majors SES — Saturday", date: "Mar 1, 2026", time: "9:00 AM", division: "majors", location: "Big Rec (GG Park)", checkedIn: 28, expected: 30, evals: 142, evalsExpected: 180 },
  { id: "s2", name: "Majors SES — Sunday",   date: "Mar 2, 2026", time: "10:30 AM", division: "majors", location: "Big Rec (GG Park)", checkedIn: 30, expected: 30, evals: 174, evalsExpected: 180 },
  { id: "s3", name: "Majors SES — Makeup",   date: "Mar 8, 2026", time: "1:00 PM", division: "majors", location: "Funston Field",     checkedIn: 9,  expected: 9,  evals: 48,  evalsExpected: 54 },
  { id: "s4", name: "AAA SES — Saturday",    date: "Mar 1, 2026", time: "1:00 PM", division: "aaa",    location: "West Sunset",       checkedIn: 22, expected: 24, evals: 86,  evalsExpected: 96 },
];

const STATIONS = [
  { id: "st-hit", name: "Hitting",   notes: "5 swings off coach pitch + 5 off machine.", fields: ["Power","Contact","Mechanics"] },
  { id: "st-pit", name: "Pitching",  notes: "3 fastballs, 3 changeups, 1 inning sim.",   fields: ["Velocity","Control","Composure"] },
  { id: "st-inf", name: "Infield",   notes: "4 grounders L/R, double-play pivot.",       fields: ["Range","Hands","Arm"] },
  { id: "st-out", name: "Outfield",  notes: "3 fly balls, 1 line drive, throw to 3B.",    fields: ["Tracking","Arm","Routes"] },
  { id: "st-spd", name: "Speed",     notes: "Home-to-1st on a swing.",                    fields: ["Time"] },
];

window.SFLL_DATA = { TEAMS, DIVISIONS, FIELDS, PLAYERS, FAMILIES, ATTENTION, SESSIONS, STATIONS };

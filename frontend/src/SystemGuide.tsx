import React from "react";
import { BookOpen, Printer, Search } from "lucide-react";
import { guideSections, guideStages, GuideAudience } from "./guide-data";
import { LibrarianSession, staffRoleName } from "./LoginPage";

const audienceFor = (role: LibrarianSession["role"]): GuideAudience =>
  role === "librarian" ? "librarian" : role === "librarian_associate" ? "associate" : "auditor";

export default function SystemGuide({ librarian }: { librarian: LibrarianSession }) {
  const [query, setQuery] = React.useState("");
  const audience = audienceFor(librarian.role);
  const normalized = query.trim().toLowerCase();
  const matches = (value: string) => !normalized || value.toLowerCase().includes(normalized);
  const sections = guideSections
    .map((section) => ({
      ...section,
      cards: section.cards.filter(
        (card) =>
          (card.audiences.includes("all") || card.audiences.includes(audience)) &&
          matches([card.title, card.path, ...card.steps].join(" ")),
      ),
    }))
    .filter((section) => section.cards.length > 0 || matches(`${section.title} ${section.intro} ${section.note}`));
  const stages = guideStages.filter((stage) => matches(stage.join(" ")));
  const resultCount = sections.reduce((total, section) => total + section.cards.length, 0) + stages.length;

  return (
    <section className="system-guide-page">
      <header className="guide-hero">
        <div>
          <span className="eyebrow">{staffRoleName(librarian.role)} guide</span>
          <h2>Library Attendance quick reference</h2>
          <p>Practical steps for check-ins, records, reporting, and responsible administration.</p>
        </div>
        <button className="guide-print-button" type="button" onClick={() => window.print()}>
          <Printer size={17} /> Print / Save PDF
        </button>
      </header>

      <nav className="guide-anchor-nav" aria-label="Guide sections">
        {guideSections.map((section) => (
          <a key={section.id} href={`#guide-${section.id}`} onClick={(event) => {
            event.preventDefault();
            setQuery("");
            requestAnimationFrame(() => document.getElementById(`guide-${section.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }));
          }}>
            <span>{section.number}</span>{section.title}
          </a>
        ))}
      </nav>

      <div className="guide-content">
        <search className="guide-search">
          <label htmlFor="guideSearch">Search the Library Attendance guide</label>
          <div><Search size={18} aria-hidden="true" /><input id="guideSearch" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search procedures, roles, records, or reports" autoComplete="off" /></div>
          <p role="status">{normalized ? `${resultCount} matching guide items` : "Search check-in, reporting, administration, and troubleshooting procedures."}</p>
        </search>

        {stages.length > 0 && (
          <section className="guide-workflow" aria-labelledby="guide-workflow-title">
            <div className="guide-section-heading compact"><div><span className="eyebrow">End to end</span><h3 id="guide-workflow-title">Attendance workflow at a glance</h3><p>Each visit moves from an active daily session to a searchable and reportable record.</p></div></div>
            <div className="guide-stage-list">{stages.map(([number, name, owner, detail]) => <article key={number}><span>{number}</span><div><h4>{name}</h4><small>{owner}</small><p>{detail}</p></div></article>)}</div>
          </section>
        )}

        {sections.map((section) => (
          <section className="guide-section" id={`guide-${section.id}`} key={section.id}>
            <header className="guide-section-heading"><div><span className="eyebrow">{section.number}</span><h3>{section.title}</h3><p>{section.intro}</p></div></header>
            <div className="guide-card-grid">{section.cards.map((card) => <article className="guide-card" key={card.title}><h4>{card.title}</h4><p className="guide-path">{card.path}</p><ol>{card.steps.map((step, index) => <li key={step}><span className="guide-step-number" aria-hidden="true">{index + 1}</span><span>{step}</span></li>)}</ol></article>)}</div>
            <p className="guide-note"><BookOpen size={16} /><span><strong>Remember:</strong> {section.note}</span></p>
          </section>
        ))}

        {resultCount === 0 && <div className="guide-empty"><strong>No matching procedures</strong><p>Try a broader term such as QR, attendance, user, report, settings, or account.</p></div>}
      </div>
    </section>
  );
}

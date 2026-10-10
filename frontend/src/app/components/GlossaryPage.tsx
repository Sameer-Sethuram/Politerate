import { useState, useEffect, useMemo } from "react";
import { Search, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";
import { Spinner, StateBox, PageContainer, SectionLabel } from "./shared";

interface ArticleLink {
  title?: string;
  url: string;
  source: string;
}

interface GlossaryTerm {
  term: string;
  definition: string;
  category: string;
  article_links?: ArticleLink[];
}

function TermCard({ term, index }: { term: GlossaryTerm; index: number }) {
  const [showSources, setShowSources] = useState(false);
  const links = term.article_links ?? [];

  return (
    <article className="bg-card border border-border rounded overflow-hidden">
      <div className="p-5">
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: "1.1rem",
              lineHeight: 1.2,
            }}
          >
            {term.term}
          </h3>
          <span className="shrink-0 inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-secondary text-muted-foreground">
            {term.category}
          </span>
        </div>
        <p className="text-sm text-foreground leading-relaxed">{term.definition}</p>
      </div>

      {/* Sources section */}
      <div className="border-t border-border px-5 py-3">
        {links.length === 0 ? (
          <span className="text-xs text-muted-foreground italic">No sources found for this term today.</span>
        ) : (
          <>
            <button
              onClick={() => setShowSources(s => !s)}
              className="flex items-center gap-1.5 text-xs font-medium hover:underline"
              style={{ color: "var(--accent)" }}
            >
              {showSources ? (
                <>Hide sources <ChevronUp size={12} /></>
              ) : (
                <>See sources ({links.length}) <ChevronDown size={12} /></>
              )}
            </button>
            {showSources && (
              <ul className="mt-3 space-y-0 divide-y divide-border">
                {links.map((link, i) => (
                  <li key={i} className="flex items-center justify-between gap-3 py-2.5">
                    <span className="text-sm text-foreground flex-1 min-w-0 truncate">
                      {link.title ?? link.source}
                    </span>
                    <a
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 text-xs font-semibold hover:underline"
                      style={{ color: "var(--accent)" }}
                    >
                      Read →
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </article>
  );
}

export function GlossaryPage() {
  const [terms, setTerms] = useState<GlossaryTerm[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [termsRes, catsRes] = await Promise.all([
          fetch("/api/glossary"),
          fetch("/api/glossary/categories"),
        ]);
        const [termsData, catsData] = await Promise.all([termsRes.json(), catsRes.json()]);
        setTerms(termsData.terms ?? []);
        setCategories(catsData.categories ?? []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load glossary");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return terms.filter(
      t =>
        (!q || t.term.toLowerCase().includes(q) || t.definition.toLowerCase().includes(q)) &&
        (!category || t.category.toLowerCase() === category.toLowerCase())
    );
  }, [terms, query, category]);

  return (
    <PageContainer narrow>
      {/* Header */}
      <div className="mb-8 pb-6 border-b border-border">
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 800,
            fontSize: "2rem",
            lineHeight: 1.15,
          }}
        >
          Political Glossary
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Learn the meaning of political terms used in today's news.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
          />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search terms…"
            className="w-full pl-9 pr-3 py-2.5 rounded border border-border bg-card text-foreground text-sm placeholder:text-muted-foreground focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 transition-colors"
          />
        </div>
        <select
          value={category}
          onChange={e => setCategory(e.target.value)}
          className="sm:w-48 px-3 py-2.5 rounded border border-border bg-card text-foreground text-sm focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 transition-colors"
        >
          <option value="">All categories</option>
          {categories.map(c => (
            <option key={c} value={c}>
              {c[0].toUpperCase() + c.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {/* Count */}
      {!loading && !error && (
        <p
          className="mb-4 text-xs text-muted-foreground"
          style={{ fontFamily: "var(--font-data)" }}
        >
          Showing {filtered.length} term{filtered.length !== 1 ? "s" : ""}
        </p>
      )}

      {loading && (
        <StateBox>
          <Spinner />
          <p>Loading glossary…</p>
        </StateBox>
      )}

      {!loading && error && (
        <StateBox>
          <AlertCircle className="text-destructive" size={28} />
          <p className="text-destructive font-medium">Failed to load glossary</p>
          <p className="text-sm text-muted-foreground">{error}</p>
        </StateBox>
      )}

      {!loading && !error && filtered.length === 0 && (
        <StateBox>
          <p className="font-medium">No terms found</p>
          <p className="text-sm">Try adjusting your search or filter.</p>
        </StateBox>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="space-y-3">
          {filtered.map((term, i) => (
            <TermCard key={term.term} term={term} index={i} />
          ))}
        </div>
      )}
    </PageContainer>
  );
}

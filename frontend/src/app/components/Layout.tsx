import { useState } from "react";
import { Outlet, NavLink, useLocation } from "react-router";
import { Menu, X } from "lucide-react";
import { BrandIcon, DEFAULT_WIDTH, WIDE_WIDTH } from "./shared";

// Pages laid out with PageContainer `wide`; the header and footer widen to
// match so their edges line up with the content.
const WIDE_PAGES = ["/all-articles"];

const NAV_LINKS = [
  { to: "/",             label: "Today",    end: true  },
  { to: "/all-articles", label: "Articles", end: false },
  { to: "/archive",      label: "Archive",  end: false },
  { to: "/learn",        label: "Learn",    end: false },
  { to: "/analyzer",     label: "Analyzer", end: false },
  { to: "/glossary",     label: "Glossary", end: false },
];

export function Layout() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const width = WIDE_PAGES.some(p => pathname.startsWith(p)) ? WIDE_WIDTH : DEFAULT_WIDTH;

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Top bar */}
      <header className="sticky top-0 z-50 bg-card border-b border-border shadow-sm">
        <div className={`${width} mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-6`}>
          {/* Logo */}
          <NavLink
            to="/"
            className="flex items-center gap-2.5 shrink-0 text-brand-dark hover:opacity-80 transition-opacity"
          >
            <BrandIcon size={36} />
            <span
              className="tracking-tight"
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 800,
                fontSize: "1.65rem",
                letterSpacing: "-0.01em",
              }}
            >
              Po<span className="text-brand-accent">literate</span>
            </span>
          </NavLink>

          {/* Desktop nav: links span the full bar height so the active
              underline sits on the header's bottom border, like a tab. */}
          <nav className="hidden md:flex self-stretch items-stretch gap-1" aria-label="Primary">
            {NAV_LINKS.map(link => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  [
                    "flex items-center px-3 lg:px-4 text-base transition-colors relative",
                    isActive
                      ? "text-foreground font-semibold"
                      : "text-muted-foreground hover:text-brand-accent hover:bg-secondary/60",
                  ].join(" ")
                }
              >
                {({ isActive }) => (
                  <>
                    {link.label}
                    {isActive && (
                      <span
                        className="absolute bottom-0 left-3 right-3 lg:left-4 lg:right-4 h-[3px] rounded-t-full"
                        style={{ background: "var(--accent)" }}
                      />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          {/* Mobile button */}
          <button
            className="md:hidden p-2 text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setOpen(o => !o)}
            aria-label="Toggle menu"
          >
            {open ? <X size={26} /> : <Menu size={26} />}
          </button>
        </div>

        {/* Mobile nav */}
        {open && (
          <nav
            className="md:hidden border-t border-border bg-card"
            aria-label="Mobile navigation"
          >
            <div className={`${width} mx-auto px-4 py-3 flex flex-col gap-1`}>
              {NAV_LINKS.map(link => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.end}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    [
                      "px-4 py-3 text-lg rounded transition-colors",
                      isActive
                        ? "bg-secondary text-foreground font-medium"
                        : "text-muted-foreground hover:text-brand-accent hover:bg-secondary",
                    ].join(" ")
                  }
                >
                  {link.label}
                </NavLink>
              ))}
            </div>
          </nav>
        )}
      </header>

      {/* Page content */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-8 mt-16 text-base text-muted-foreground">
        <div className={`${width} mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4`}>
          <div className="flex items-center gap-2">
            <BrandIcon size={20} />
            <span style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>Politerate</span>
            <span>— multi-source, unbiased political news.</span>
          </div>
          <nav className="flex flex-wrap justify-center gap-x-5 gap-y-1">
            {NAV_LINKS.map(link => (
              <NavLink
                key={link.to}
                to={link.to}
                className="link"
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </footer>
    </div>
  );
}

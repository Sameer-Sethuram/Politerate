import { useState } from "react";
import { Outlet, NavLink } from "react-router";
import { Menu, X } from "lucide-react";
import { BrandIcon } from "./shared";

const NAV_LINKS = [
  { to: "/",             label: "Today",    end: true  },
  { to: "/all-articles", label: "Articles", end: false },
  { to: "/learn",        label: "Learn",    end: false },
  { to: "/analyzer",     label: "Analyzer", end: false },
  { to: "/archive",      label: "Archive",  end: false },
  { to: "/glossary",     label: "Glossary", end: false },
];

export function Layout() {
  const [open, setOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Top bar */}
      <header className="sticky top-0 z-50 bg-card border-b border-border shadow-sm">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-6">
          {/* Logo */}
          <NavLink
            to="/"
            className="flex items-center gap-2 shrink-0 text-brand-dark hover:opacity-80 transition-opacity"
          >
            <BrandIcon size={28} />
            <span
              className="tracking-tight"
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 800,
                fontSize: "1.35rem",
                letterSpacing: "-0.01em",
              }}
            >
              Po<span className="text-brand-accent">literate</span>
            </span>
          </NavLink>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-0.5" aria-label="Primary">
            {NAV_LINKS.map(link => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  [
                    "px-3 py-1 text-sm rounded transition-colors relative",
                    isActive
                      ? "text-foreground font-medium"
                      : "text-muted-foreground hover:text-foreground",
                  ].join(" ")
                }
              >
                {({ isActive }) => (
                  <>
                    {link.label}
                    {isActive && (
                      <span
                        className="absolute bottom-0 left-3 right-3 h-0.5 rounded-full"
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
            className="md:hidden p-1.5 text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setOpen(o => !o)}
            aria-label="Toggle menu"
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {/* Mobile nav */}
        {open && (
          <nav
            className="md:hidden border-t border-border bg-card"
            aria-label="Mobile navigation"
          >
            <div className="max-w-6xl mx-auto px-4 py-3 flex flex-col gap-0.5">
              {NAV_LINKS.map(link => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.end}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    [
                      "px-3 py-2 text-sm rounded transition-colors",
                      isActive
                        ? "bg-secondary text-foreground font-medium"
                        : "text-muted-foreground hover:text-foreground hover:bg-secondary",
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
      <footer className="border-t border-border py-8 mt-16 text-sm text-muted-foreground">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <BrandIcon size={16} />
            <span style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>Politerate</span>
            <span>— multi-source, unbiased political news.</span>
          </div>
          <nav className="flex flex-wrap justify-center gap-x-5 gap-y-1">
            {NAV_LINKS.map(link => (
              <NavLink
                key={link.to}
                to={link.to}
                className="hover:text-foreground transition-colors"
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

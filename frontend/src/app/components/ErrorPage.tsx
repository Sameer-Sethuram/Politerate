import { useEffect } from "react";
import { Link, isRouteErrorResponse, useRouteError } from "react-router";
import { AlertCircle } from "lucide-react";
import { PageContainer, StateBox } from "./shared";
import { reportClientError } from "../api";

/**
 * Shown instead of a blank page when a page crashes while rendering, and
 * for addresses that match no page. Crashes are reported to the server log.
 */
export function ErrorPage() {
  const error = useRouteError();
  const notFound = isRouteErrorResponse(error) && error.status === 404;

  useEffect(() => {
    if (!notFound) reportClientError(error);
  }, [error, notFound]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <PageContainer narrow>
        <StateBox>
          <AlertCircle className="text-destructive" size={32} />
          <p className="text-xl font-semibold text-foreground">
            {notFound ? "Page not found" : "Something went wrong"}
          </p>
          <p className="text-base max-w-md">
            {notFound
              ? "There's no page at this address."
              : "This page ran into a problem. Reloading usually fixes it; if not, try again in a few minutes."}
          </p>
          <div className="flex gap-2.5 pt-2">
            {!notFound && (
              <button
                onClick={() => window.location.reload()}
                className="px-5 py-2 bg-primary text-primary-foreground rounded text-base font-semibold hover:opacity-90 transition-opacity"
              >
                Reload
              </button>
            )}
            <Link
              to="/"
              className="px-5 py-2 bg-secondary text-secondary-foreground rounded text-base font-medium hover:bg-muted transition-colors"
            >
              Today's Brief
            </Link>
          </div>
        </StateBox>
      </PageContainer>
    </div>
  );
}

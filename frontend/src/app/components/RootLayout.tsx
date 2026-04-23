import { Outlet, Link, useLocation } from "react-router";
import { Newspaper, ScanText } from "lucide-react";

export function RootLayout() {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link to="/" className="flex items-center gap-2">
              <Newspaper className="size-8 text-blue-600" />
              <div>
                <h1 className="font-bold text-xl">NewsBalance</h1>
                <p className="text-xs text-gray-500">Unbiased News Perspectives</p>
              </div>
            </Link>
            
            <nav className="flex gap-6">
              <Link
                to="/"
                className={`flex items-center gap-2 px-3 py-2 rounded-md transition-colors ${
                  location.pathname === "/"
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <Newspaper className="size-4" />
                News
              </Link>
              <Link
                to="/analyzer"
                className={`flex items-center gap-2 px-3 py-2 rounded-md transition-colors ${
                  location.pathname === "/analyzer"
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <ScanText className="size-4" />
                Text Analyzer
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main>
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-gray-600 text-sm">
            <p>NewsBalance - View news from all perspectives</p>
            <p className="mt-2 text-xs text-gray-500">
              Bias ratings and trust scores are for demonstration purposes
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

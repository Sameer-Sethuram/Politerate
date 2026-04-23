import { createBrowserRouter } from "react-router";
import { HomePage } from "./pages/HomePage";
import { ArticleDetailPage } from "./pages/ArticleDetailPage";
import { TextAnalyzerPage } from "./pages/TextAnalyzerPage";
import { RootLayout } from "./components/RootLayout";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: RootLayout,
    children: [
      { index: true, Component: HomePage },
      { path: "article/:id", Component: ArticleDetailPage },
      { path: "analyzer", Component: TextAnalyzerPage },
    ],
  },
]);

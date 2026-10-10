import { createBrowserRouter } from "react-router";
import { Layout } from "./components/Layout";
import { HomePage } from "./components/HomePage";
import { AllArticlesPage } from "./components/AllArticlesPage";
import { ArticleDetailPage } from "./components/ArticleDetailPage";
import { AnalyzerPage } from "./components/AnalyzerPage";
import { ArchivePage } from "./components/ArchivePage";
import { ClusterPage } from "./components/ClusterPage";
import { LearnPage } from "./components/LearnPage";
import { GlossaryPage } from "./components/GlossaryPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: HomePage },
      { path: "all-articles", Component: AllArticlesPage },
      { path: "article", Component: ArticleDetailPage },
      { path: "analyzer", Component: AnalyzerPage },
      { path: "archive", Component: ArchivePage },
      { path: "cluster/:clusterId", Component: ClusterPage },
      { path: "learn", Component: LearnPage },
      { path: "glossary", Component: GlossaryPage },
    ],
  },
]);

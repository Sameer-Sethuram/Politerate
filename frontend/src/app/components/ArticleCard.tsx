import { Link } from "react-router";
import { Article } from "../data/mockArticles";
import { BiasIndicator } from "./BiasIndicator";
import { TrustScore } from "./TrustScore";
import { Calendar, ExternalLink } from "lucide-react";

interface ArticleCardProps {
  article: Article;
}

export function ArticleCard({ article }: ArticleCardProps) {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", { 
      month: "short", 
      day: "numeric", 
      year: "numeric" 
    });
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-gray-900">{article.source}</span>
            <span className="text-xs text-gray-400">•</span>
            <span className="inline-flex items-center gap-1 text-xs text-gray-500">
              <Calendar className="size-3" />
              {formatDate(article.date)}
            </span>
          </div>
          <span className="inline-block px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded">
            {article.category}
          </span>
        </div>
      </div>

      {/* Title */}
      <Link to={`/article/${article.id}`}>
        <h3 className="text-lg font-semibold text-gray-900 mb-3 hover:text-blue-600 transition-colors">
          {article.title}
        </h3>
      </Link>

      {/* Summary Preview */}
      <p className="text-sm text-gray-600 mb-4 line-clamp-2">
        {article.summary}
      </p>

      {/* Metrics */}
      <div className="flex flex-col gap-3 mb-4 pt-4 border-t border-gray-100">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Political Bias:</span>
          <BiasIndicator bias={article.bias} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Trust Score:</span>
          <TrustScore score={article.trustScore} />
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <Link
          to={`/article/${article.id}`}
          className="flex-1 text-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm"
        >
          Read Summary
        </Link>
        <a
          href={article.originalUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition-colors text-sm flex items-center gap-1"
        >
          <ExternalLink className="size-4" />
          Original
        </a>
      </div>
    </div>
  );
}

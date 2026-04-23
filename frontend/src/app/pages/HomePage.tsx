import { useState } from "react";
import { mockArticles, BiasRating } from "../data/mockArticles";
import { ArticleCard } from "../components/ArticleCard";
import { Filter } from "lucide-react";

export function HomePage() {
  const [selectedBias, setSelectedBias] = useState<BiasRating | "all">("all");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  const filteredArticles = mockArticles.filter((article) => {
    const biasMatch = selectedBias === "all" || article.bias === selectedBias;
    const categoryMatch = selectedCategory === "all" || article.category === selectedCategory;
    return biasMatch && categoryMatch;
  });

  const categories = ["all", ...Array.from(new Set(mockArticles.map(a => a.category)))];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Hero Section */}
      <div className="text-center mb-12">
        <h2 className="text-4xl font-bold text-gray-900 mb-4">
          See Every Side of the Story
        </h2>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          Compare news coverage across the political spectrum. Read articles from different 
          perspectives with transparent bias ratings and trust scores.
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-8">
        <div className="flex items-center gap-2 mb-4">
          <Filter className="size-5 text-gray-600" />
          <h3 className="font-semibold text-gray-900">Filter Articles</h3>
        </div>
        
        <div className="grid md:grid-cols-2 gap-4">
          {/* Bias Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Political Bias
            </label>
            <div className="flex flex-wrap gap-2">
              {["all", "left", "lean-left", "center", "lean-right", "right"].map((bias) => (
                <button
                  key={bias}
                  onClick={() => setSelectedBias(bias as BiasRating | "all")}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    selectedBias === bias
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  {bias === "all" ? "All" : bias.split("-").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
                </button>
              ))}
            </div>
          </div>

          {/* Category Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Category
            </label>
            <div className="flex flex-wrap gap-2">
              {categories.map((category) => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    selectedCategory === category
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  {category === "all" ? "All Categories" : category}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Results Count */}
      <div className="mb-6">
        <p className="text-sm text-gray-600">
          Showing {filteredArticles.length} article{filteredArticles.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Articles Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredArticles.map((article) => (
          <ArticleCard key={article.id} article={article} />
        ))}
      </div>

      {filteredArticles.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">No articles found matching your filters.</p>
        </div>
      )}
    </div>
  );
}

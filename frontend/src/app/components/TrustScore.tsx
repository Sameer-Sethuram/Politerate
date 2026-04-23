interface TrustScoreProps {
  score: number; // 0-100
  showLabel?: boolean;
}

export function TrustScore({ score, showLabel = true }: TrustScoreProps) {
  const getScoreColor = (score: number) => {
    if (score >= 85) return { bg: "bg-green-500", text: "text-green-700" };
    if (score >= 70) return { bg: "bg-yellow-500", text: "text-yellow-700" };
    return { bg: "bg-orange-500", text: "text-orange-700" };
  };

  const colors = getScoreColor(score);

  return (
    <div className="flex items-center gap-2">
      {/* Progress Bar */}
      <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${colors.bg} transition-all duration-300`}
          style={{ width: `${score}%` }}
        />
      </div>
      
      {showLabel && (
        <span className={`text-sm font-medium ${colors.text}`}>
          {score}/100
        </span>
      )}
    </div>
  );
}

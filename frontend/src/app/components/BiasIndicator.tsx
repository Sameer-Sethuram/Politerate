import { BiasRating } from "../data/mockArticles";

interface BiasIndicatorProps {
  bias: BiasRating;
  showLabel?: boolean;
}

export function BiasIndicator({ bias, showLabel = true }: BiasIndicatorProps) {
  const biasConfig = {
    left: {
      label: "Left",
      color: "bg-blue-600",
      textColor: "text-blue-600",
      bgLight: "bg-blue-50",
    },
    "lean-left": {
      label: "Lean Left",
      color: "bg-blue-400",
      textColor: "text-blue-500",
      bgLight: "bg-blue-50",
    },
    center: {
      label: "Center",
      color: "bg-purple-600",
      textColor: "text-purple-600",
      bgLight: "bg-purple-50",
    },
    "lean-right": {
      label: "Lean Right",
      color: "bg-red-400",
      textColor: "text-red-500",
      bgLight: "bg-red-50",
    },
    right: {
      label: "Right",
      color: "bg-red-600",
      textColor: "text-red-600",
      bgLight: "bg-red-50",
    },
  };

  const config = biasConfig[bias];

  return (
    <div className="flex items-center gap-2">
      {/* Visual Indicator */}
      <div className="flex gap-1">
        {["left", "lean-left", "center", "lean-right", "right"].map((position) => (
          <div
            key={position}
            className={`w-2 h-6 rounded-sm ${
              position === bias ? config.color : "bg-gray-200"
            }`}
          />
        ))}
      </div>
      
      {showLabel && (
        <span className={`text-sm font-medium ${config.textColor}`}>
          {config.label}
        </span>
      )}
    </div>
  );
}

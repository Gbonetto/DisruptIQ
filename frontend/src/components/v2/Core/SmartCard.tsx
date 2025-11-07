import React from 'react';
import { LucideIcon } from 'lucide-react';

export interface SmartCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  onClick: () => void;
}

export const SmartCard: React.FC<SmartCardProps> = ({
  icon: Icon,
  title,
  description,
  onClick,
}) => {
  return (
    <button
      onClick={onClick}
      className="group relative p-4 rounded-xl border border-border bg-card hover:bg-accent/50 hover:border-primary/30 hover:shadow-md hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 text-left w-full"
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 group-hover:scale-110 transition-all duration-200">
          <Icon className="w-5 h-5 text-primary" />
        </div>

        {/* Content */}
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-foreground mb-1">
            {title}
          </h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {description}
          </p>
        </div>
      </div>
    </button>
  );
};

export interface SmartCardsGridProps {
  cards: SmartCardProps[];
}

export const SmartCardsGrid: React.FC<SmartCardsGridProps> = ({ cards }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {cards.map((card, index) => (
        <SmartCard key={index} {...card} />
      ))}
    </div>
  );
};

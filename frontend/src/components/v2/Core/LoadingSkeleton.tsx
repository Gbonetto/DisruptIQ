import React from 'react';
import { Skeleton } from '@/components/ui/skeleton';

export const MessageLoadingSkeleton: React.FC = () => {
  return (
    <div className="flex justify-start">
      <div className="w-full space-y-4 animate-in fade-in duration-300">
        {/* Chain of Thought Skeleton */}
        <div className="rounded-2xl p-4 bg-secondary/30 border border-border">
          <div className="flex items-center gap-2 mb-3">
            <Skeleton className="h-4 w-4 rounded-full" />
            <Skeleton className="h-4 w-32" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
          </div>
        </div>

        {/* Main Response Skeleton */}
        <div className="rounded-2xl px-4 py-3 bg-secondary">
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        </div>

        {/* Table Skeleton */}
        <div className="rounded-2xl border border-border bg-background overflow-hidden">
          <div className="p-3 border-b border-border">
            <Skeleton className="h-5 w-48" />
          </div>
          <div className="p-3 space-y-2">
            <div className="flex gap-2">
              <Skeleton className="h-8 flex-1" />
              <Skeleton className="h-8 flex-1" />
              <Skeleton className="h-8 flex-1" />
              <Skeleton className="h-8 flex-1" />
            </div>
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex gap-2">
                <Skeleton className="h-6 flex-1" />
                <Skeleton className="h-6 flex-1" />
                <Skeleton className="h-6 flex-1" />
                <Skeleton className="h-6 flex-1" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export const DocumentLoadingSkeleton: React.FC = () => {
  return (
    <div className="space-y-2 p-4">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-3 rounded-lg border border-border animate-pulse">
          <Skeleton className="w-5 h-5 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
};

export const TableLoadingSkeleton: React.FC = () => {
  return (
    <div className="space-y-3 p-4">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="p-4 rounded-xl border border-border animate-pulse">
          <div className="flex items-center justify-between mb-3">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-5 w-24" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
          </div>
        </div>
      ))}
    </div>
  );
};

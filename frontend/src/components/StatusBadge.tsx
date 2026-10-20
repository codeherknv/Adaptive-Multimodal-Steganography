import React from 'react';

export type StatusType = 
  | 'implemented' 
  | 'in_progress' 
  | 'pending' 
  | 'healthy' 
  | 'degraded' 
  | 'unhealthy'
  | 'completed'
  | 'current'
  | 'staged';

interface StatusBadgeProps {
  status: StatusType;
  label?: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, size = 'sm' }) => {
  const getBadgeStyle = () => {
    switch (status) {
      case 'implemented':
      case 'healthy':
      case 'completed':
        return 'bg-emerald-950/40 text-emerald-400 border-emerald-800/50';
      case 'in_progress':
      case 'current':
        return 'bg-sky-950/40 text-sky-300 border-sky-800/50';
      case 'degraded':
        return 'bg-amber-950/40 text-amber-300 border-amber-800/50';
      case 'unhealthy':
        return 'bg-rose-950/40 text-rose-300 border-rose-800/50';
      case 'pending':
      case 'staged':
      default:
        return 'bg-zinc-900/60 text-zinc-400 border-zinc-800';
    }
  };

  const getDotStyle = () => {
    switch (status) {
      case 'implemented':
      case 'healthy':
      case 'completed':
        return 'bg-emerald-400';
      case 'in_progress':
      case 'current':
        return 'bg-sky-400';
      case 'degraded':
        return 'bg-amber-400';
      case 'unhealthy':
        return 'bg-rose-400';
      case 'pending':
      case 'staged':
      default:
        return 'bg-zinc-500';
    }
  };

  const getDefaultLabel = () => {
    switch (status) {
      case 'implemented':
        return 'Implemented';
      case 'in_progress':
        return 'In Progress';
      case 'pending':
        return 'Planned';
      case 'healthy':
        return 'Online';
      case 'degraded':
        return 'Degraded';
      case 'unhealthy':
        return 'Offline';
      case 'completed':
        return 'Verified';
      case 'current':
        return 'Current Phase';
      case 'staged':
        return 'Staged';
      default:
        return status;
    }
  };

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center font-mono font-medium rounded border ${sizeClasses} ${getBadgeStyle()}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${getDotStyle()}`} />
      {label || getDefaultLabel()}
    </span>
  );
};

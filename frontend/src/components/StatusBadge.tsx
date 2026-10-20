import React from 'react';

interface StatusBadgeProps {
  status: 'implemented' | 'in_progress' | 'pending' | 'healthy' | 'degraded' | 'unhealthy';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const getBadgeStyle = () => {
    switch (status) {
      case 'implemented':
      case 'healthy':
        return 'bg-emerald-950/70 text-emerald-400 border-emerald-800/60';
      case 'in_progress':
      case 'degraded':
        return 'bg-amber-950/70 text-amber-400 border-amber-800/60';
      case 'pending':
      case 'unhealthy':
      default:
        return 'bg-slate-800/80 text-slate-400 border-slate-700/60';
    }
  };

  const getLabel = () => {
    switch (status) {
      case 'implemented':
        return 'Implemented';
      case 'in_progress':
        return 'In Progress';
      case 'pending':
        return 'Phase Pending';
      case 'healthy':
        return 'Online (Healthy)';
      case 'degraded':
        return 'Degraded';
      case 'unhealthy':
        return 'Offline';
      default:
        return status;
    }
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getBadgeStyle()}`}
    >
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-80" />
      {getLabel()}
    </span>
  );
};

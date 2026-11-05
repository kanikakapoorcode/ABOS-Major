import { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';
import { GoalStatus, StepStatus, GoalPriority } from '@/api/types';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'status' | 'priority';
  status?: GoalStatus | StepStatus;
  priority?: GoalPriority;
}

export default function Badge({ 
  variant = 'status', 
  status, 
  priority, 
  className,
  children,
  ...props 
}: BadgeProps) {
  const baseStyles = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium';

  const statusColors: Record<GoalStatus | StepStatus, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    planning: 'bg-blue-100 text-blue-800',
    executing: 'bg-blue-100 text-blue-800',
    running: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  };

  const priorityColors: Record<GoalPriority, string> = {
    low: 'bg-gray-100 text-gray-800',
    medium: 'bg-yellow-100 text-yellow-800',
    high: 'bg-orange-100 text-orange-800',
    critical: 'bg-red-100 text-red-800',
  };

  let colorClass = '';
  let displayText = children;

  if (variant === 'status' && status) {
    colorClass = statusColors[status];
    displayText = displayText || status;
  } else if (variant === 'priority' && priority) {
    colorClass = priorityColors[priority];
    displayText = displayText || priority;
  }

  return (
    <span
      className={cn(baseStyles, colorClass, className)}
      {...props}
    >
      {displayText}
    </span>
  );
}

export const COMMAND_STATUS_META = {
  pending: {
    label: 'Queued',
    description: 'Queued for the device',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
  },
  sent: {
    label: 'Acknowledged',
    description: 'Picked up by the device, executing',
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
  },
  completed: {
    label: 'Completed',
    description: 'Executed successfully on the device',
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
  },
  failed: {
    label: 'Failed',
    description: 'Execution failed on the device',
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
  },
  expired: {
    label: 'Expired',
    description: 'The device did not pick up the command in time',
    color: 'text-slate-400',
    bg: 'bg-slate-500/10',
    border: 'border-slate-500/30',
  },
};

export function getStatusMeta(status) {
  return COMMAND_STATUS_META[status] || COMMAND_STATUS_META.pending;
}

export function lifecycleStages(command) {
  const status = command?.status || 'pending';
  const meta = getStatusMeta(status);
  const stages = [
    { key: 'queued', label: 'Queued', time: command?.created_at, done: !!command?.created_at },
    {
      key: 'acknowledged',
      label: 'Acknowledged',
      time: command?.sent_at,
      done: !!command?.sent_at,
    },
    {
      key: 'executed',
      label: 'Executed',
      time: command?.executed_at,
      done: !!command?.executed_at,
    },
  ];
  const finalStage = {
    key: 'result',
    label: meta.label,
    time: command?.executed_at || command?.created_at,
    done: status === 'completed' || status === 'failed' || status === 'expired',
  };
  return { status, meta, stages, finalStage };
}

export function formatCommandType(commandType) {
  if (!commandType) return 'Custom Command';
  return commandType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function resultMessage(result) {
  if (!result) return null;
  if (typeof result === 'string') return result;
  return result.message || result.error || null;
}

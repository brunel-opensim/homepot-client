interface MetricsHistoryChartProps {
  label: string
  color: string
  values: Array<number | null>
}

const WIDTH = 90
const HEIGHT = 40
const PAD = 3

export default function MetricsHistoryChart({ label, color, values }: MetricsHistoryChartProps) {
  const nums = values.filter((v): v is number => v !== null && v !== undefined)
  if (nums.length === 0) {
    return (
      <div className="flex flex-col gap-1">
        <div className="h-10 w-[90px] rounded bg-slate-700/40 flex items-center justify-center">
          <span className="text-slate-500 text-[10px]">no data</span>
        </div>
        <span className="text-[10px] text-slate-500 text-center">{label}</span>
      </div>
    )
  }

  const max = Math.max(...nums, 1)
  const min = Math.min(...nums, 0)
  const range = max - min || 1
  const step = nums.length > 1 ? (WIDTH - PAD * 2) / (nums.length - 1) : WIDTH

  const points = nums
    .map((v, i) => {
      const x = i === 0 ? PAD : Math.min(PAD + i * step, WIDTH - PAD)
      const y = HEIGHT - PAD - ((v - min) / range) * (HEIGHT - PAD * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const current = nums[nums.length - 1]

  return (
    <div className="flex flex-col gap-1">
      <svg
        className="h-10 w-[90px]"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
      >
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="text-[10px] text-slate-500 text-center">
        {label} <span className="text-slate-300 font-mono">{current.toFixed(0)}%</span>
      </span>
    </div>
  )
}
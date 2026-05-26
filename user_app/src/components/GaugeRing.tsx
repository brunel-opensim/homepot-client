interface GaugeRingProps {
  label: string
  value: number
  color: string
}

export default function GaugeRing({ label, value, color }: GaugeRingProps) {
  const radius = 28
  const stroke = 5
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (value / 100) * circumference

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative w-16 h-16">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 70 70">
          <circle
            cx="35" cy="35" r={radius}
            fill="none"
            stroke="#1e293b"
            strokeWidth={stroke}
          />
          <circle
            cx="35" cy="35" r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-700"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-slate-200">
          {value}%
        </span>
      </div>
      <span className="text-xs text-slate-400 font-medium">{label}</span>
    </div>
  )
}

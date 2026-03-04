interface EmergentLogoProps {
  size?: number;
  className?: string;
}

export function EmergentLogo({ size = 40, className = '' }: EmergentLogoProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 512 512"
      width={size}
      height={size}
      role="img"
      aria-label="EmergentCTI logo"
      className={className}
    >
      {/* Regular flat-top hexagon */}
      <path
        d="M426 256 L341 403.22 L171 403.22 L86 256 L171 108.78 L341 108.78 Z"
        className="fill-none stroke-[18]"
        style={{ stroke: 'currentColor' }}
        strokeLinejoin="round"
      />

      {/* Network lines - red accent */}
      <g style={{ stroke: '#85191A' }} className="fill-none" strokeWidth="16" strokeLinecap="round" strokeLinejoin="round">
        <path d="M190 190 L256 256 L322 190" />
        <path d="M190 322 L256 256 L322 322" />
        <path d="M190 190 L190 322" />
        <path d="M322 190 L322 322" />
        <path d="M190 190 L322 322" />
        <path d="M322 190 L190 322" />
      </g>

      {/* Network nodes */}
      <circle cx="190" cy="190" r="16" style={{ fill: '#85191A', stroke: 'currentColor' }} strokeWidth="8" />
      <circle cx="322" cy="190" r="16" style={{ fill: '#85191A', stroke: 'currentColor' }} strokeWidth="8" />
      <circle cx="190" cy="322" r="16" style={{ fill: '#85191A', stroke: 'currentColor' }} strokeWidth="8" />
      <circle cx="322" cy="322" r="16" style={{ fill: '#85191A', stroke: 'currentColor' }} strokeWidth="8" />
    </svg>
  );
}

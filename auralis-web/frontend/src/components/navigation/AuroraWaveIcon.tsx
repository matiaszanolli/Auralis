import { WaveIcon } from './AuroraLogo.styles';

interface AuroraWaveIconProps {
  size: number;
}

export const AuroraWaveIcon = ({ size }: AuroraWaveIconProps) => {
  return (
    <WaveIcon size={size} viewBox="0 0 400 400" fill="none">
      <defs>
        <linearGradient id="auralis-grad-auralis-classic" x1="0%" y1="30%" x2="100%" y2="70%">
          <stop offset="0%" stopColor="#06b6d4" />
          <stop offset="35%" stopColor="#2563eb" />
          <stop offset="70%" stopColor="#7c3aed" />
          <stop offset="100%" stopColor="#db2777" />
        </linearGradient>
        <filter id="gentle-shadow" x="-10%" y="-10%" width="120%" height="120%">
          <feDropShadow dx="0" dy="8" stdDeviation="12" floodOpacity="0.25" floodColor="#000" />
        </filter>
        <linearGradient id="reflect-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="100%" stopColor="#1E293B" />
        </linearGradient>
      </defs>
      <g>
        <circle cx="200" cy="200" r="162" fill="none" stroke="url(#reflect-gradient)" strokeWidth="1.5" opacity="0.12" />
        <circle cx="200" cy="200" r="160" fill="#08080a" stroke="rgba(255,255,255,0.08)" strokeWidth="2" filter="url(#gentle-shadow)" />
        <circle cx="200" cy="200" r="120" fill="#06b6d4" opacity="0.0272" style={{ filter: 'blur(27.2px)' }} />
        <path
          d="M 80,210 C 115,145 138,165 160,205 C 182,245 220,110 248,115 C 275,120 292,245 320,195 C 324,190 322,205 310,225 C 285,263 270,215 248,155 C 220,95 185,260 160,240 C 135,220 108,245 80,210 Z"
          fill="url(#auralis-grad-auralis-classic)"
          style={{
            filter:
              'drop-shadow(rgba(0,0,0,0.15) 0px 4px 12px) drop-shadow(rgba(6,182,212,0.68) 0px 0px 10.2px) drop-shadow(rgba(219,39,119,0.455) 0px 0px 20.4px)',
          }}
        />
      </g>
    </WaveIcon>
  );
};

export default AuroraWaveIcon;

import { tokens, withOpacity } from '@/design-system';
import { WaveIcon } from './AuroraLogo.styles';

interface AuroraWaveIconProps {
  size: number;
}

// All colors come from design tokens (#4170): the aurora gradient/glow uses the
// brand accents, the disc fill uses bg.level0 (no near-pure-black), and rgba
// values are composed with withOpacity() instead of hardcoded literals.
const { accent, audioSemantic, semantic, bg, text } = tokens.colors;

export const AuroraWaveIcon = ({ size }: AuroraWaveIconProps) => {
  return (
    <WaveIcon size={size} viewBox="0 0 400 400" fill="none">
      <defs>
        <linearGradient id="auralis-grad-auralis-classic" x1="0%" y1="30%" x2="100%" y2="70%">
          <stop offset="0%" stopColor={accent.secondary} />
          <stop offset="35%" stopColor={semantic.info} />
          <stop offset="70%" stopColor={accent.primary} />
          <stop offset="100%" stopColor={audioSemantic.harmonic} />
        </linearGradient>
        <filter id="gentle-shadow" x="-10%" y="-10%" width="120%" height="120%">
          <feDropShadow dx="0" dy="8" stdDeviation="12" floodOpacity="0.25" floodColor={bg.level0} />
        </filter>
        <linearGradient id="reflect-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={text.primaryFull} />
          <stop offset="100%" stopColor={bg.level3} />
        </linearGradient>
      </defs>
      <g>
        <circle cx="200" cy="200" r="162" fill="none" stroke="url(#reflect-gradient)" strokeWidth="1.5" opacity="0.12" />
        <circle cx="200" cy="200" r="160" fill={bg.level0} stroke={withOpacity(text.primaryFull, 0.08)} strokeWidth="2" filter="url(#gentle-shadow)" />
        <circle cx="200" cy="200" r="120" fill={accent.secondary} opacity="0.0272" style={{ filter: 'blur(27.2px)' }} />
        <path
          d="M 80,210 C 115,145 138,165 160,205 C 182,245 220,110 248,115 C 275,120 292,245 320,195 C 324,190 322,205 310,225 C 285,263 270,215 248,155 C 220,95 185,260 160,240 C 135,220 108,245 80,210 Z"
          fill="url(#auralis-grad-auralis-classic)"
          style={{
            filter:
              `drop-shadow(${withOpacity(bg.level0, 0.15)} 0px 4px 12px) ` +
              `drop-shadow(${withOpacity(accent.secondary, 0.68)} 0px 0px 10.2px) ` +
              `drop-shadow(${withOpacity(audioSemantic.harmonic, 0.455)} 0px 0px 20.4px)`,
          }}
        />
      </g>
    </WaveIcon>
  );
};

export default AuroraWaveIcon;

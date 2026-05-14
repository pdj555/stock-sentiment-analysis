"use client";

import { animate, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { formatScore } from "@/lib/format";
import type { Tone } from "@/lib/types";

interface ScoreGaugeProps {
  score: number;
  tone: Tone;
}

const CX = 130;
const CY = 130;
const R = 108;

function pointForScore(score: number) {
  const clamped = Math.max(-1, Math.min(1, score));
  // score -1 -> 180deg (left), 0 -> 90deg (top), +1 -> 0deg (right)
  const angle = ((90 - clamped * 90) * Math.PI) / 180;
  return {
    x: CX + R * Math.cos(angle),
    y: CY - R * Math.sin(angle),
  };
}

export default function ScoreGauge({ score, tone }: ScoreGaugeProps) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    const controls = animate(0, score, {
      duration: 1.15,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (value) => setDisplay(value),
    });
    return () => controls.stop();
  }, [score]);

  const point = pointForScore(score);
  const sweep = score >= 0 ? 1 : 0;
  const trackPath = `M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`;
  const progressPath = `M ${CX} ${CY - R} A ${R} ${R} 0 0 ${sweep} ${point.x} ${point.y}`;

  return (
    <div className="gauge">
      <svg viewBox="0 0 260 150" role="img" aria-label={`Sentiment score ${formatScore(score)}`}>
        <defs>
          <linearGradient id="gaugeProgress" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="var(--tone)" stopOpacity="0.35" />
            <stop offset="1" stopColor="var(--tone)" />
          </linearGradient>
        </defs>

        <path
          d={trackPath}
          fill="none"
          stroke="rgba(255,255,255,0.09)"
          strokeWidth="10"
          strokeLinecap="round"
        />

        {/* center tick at score 0 */}
        <line
          x1={CX}
          y1={CY - R - 8}
          x2={CX}
          y2={CY - R + 8}
          stroke="rgba(255,255,255,0.22)"
          strokeWidth="2"
          strokeLinecap="round"
        />

        <motion.path
          d={progressPath}
          fill="none"
          stroke="url(#gaugeProgress)"
          strokeWidth="10"
          strokeLinecap="round"
          initial={{ pathLength: 0, opacity: 0.6 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 1.15, ease: [0.22, 1, 0.36, 1] }}
        />

        <motion.circle
          cx={point.x}
          cy={point.y}
          r="9"
          fill="var(--tone)"
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.95, type: "spring", stiffness: 320, damping: 18 }}
          style={{ transformOrigin: `${point.x}px ${point.y}px` }}
        />
        <motion.circle
          cx={point.x}
          cy={point.y}
          r="9"
          fill="none"
          stroke="var(--tone)"
          strokeWidth="2"
          initial={{ scale: 0.6, opacity: 0.8 }}
          animate={{ scale: 2.4, opacity: 0 }}
          transition={{ delay: 1.05, duration: 1.4, repeat: Infinity, repeatDelay: 0.6 }}
          style={{ transformOrigin: `${point.x}px ${point.y}px` }}
        />
      </svg>

      <div className="gauge-center">
        <div className="gauge-score">{formatScore(display)}</div>
        <div className="gauge-label">Score</div>
      </div>

      <div className="gauge-ends">
        <span>−1.0</span>
        <span>+1.0</span>
      </div>
    </div>
  );
}

import { useMemo, useRef, useState } from "react";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import * as THREE from "three";
import { COLORS, MODALITY_COLOR } from "../../design/tokens";
import { useStore } from "../../store/useStore";
import type { FusedSegment } from "../../types/contracts";

const WIDTH = 11;
const LANE_Y: Record<string, number> = {
  asr: -1.3,
  ocr: 0,
  merged: 0.65,
  audio: 1.3,
};

function SegmentBar({
  seg,
  x,
  dur,
  onHover,
}: {
  seg: FusedSegment;
  x: number;
  dur: number;
  onHover: (s: FusedSegment | null) => void;
}) {
  const color = MODALITY_COLOR[seg.source] ?? COLORS.textDim;
  const len = Math.max(0.18, ((seg.end_timestamp ?? seg.timestamp + 3) - seg.timestamp) / dur * WIDTH);
  const y = LANE_Y[seg.source] ?? 0;
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (ref.current) ref.current.rotation.y = Math.sin(clock.getElapsedTime() * 0.6 + x) * 0.15;
  });
  return (
    <mesh
      ref={ref}
      position={[x + len / 2 - WIDTH / 2, y, 0]}
      onClick={(e) => {
        e.stopPropagation();
        onHover(seg);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        onHover(seg);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        onHover(null);
        document.body.style.cursor = "default";
      }}
    >
      <boxGeometry args={[len, 0.42, 0.42]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.45} roughness={0.3} />
    </mesh>
  );
}

export function TimelineTheatre() {
  const artifact = useStore((s) => (s.activeJobId ? s.artifacts[s.activeJobId] : null));
  const playhead = useStore((s) => s.playhead);
  const setPlayhead = useStore((s) => s.setPlayhead);
  const [hover, setHover] = useState<FusedSegment | null>(null);
  const playRef = useRef<THREE.Mesh>(null);

  const segs = artifact?.evidence?.segments ?? [];
  const dur = useMemo(() => {
    const ev = artifact?.evidence;
    const maxT = ev?.segments.reduce((m, s) => Math.max(m, s.end_timestamp ?? s.timestamp), 0) ?? 0;
    return artifact?.bundle?.total_duration_seconds ?? artifact?.manifest?.duration_seconds ?? maxT ?? 60;
  }, [artifact]);

  const phX = (playhead / Math.max(1, dur)) * WIDTH - WIDTH / 2;

  useFrame(() => {
    if (playRef.current) {
      playRef.current.position.x = phX;
      const t = performance.now() * 0.004;
      (playRef.current.material as THREE.MeshBasicMaterial).opacity = 0.6 + Math.sin(t) * 0.25;
    }
  });

  const onGroundClick = (e: ThreeEvent<MouseEvent>) => {
    const x = e.point.x;
    const t = ((x + WIDTH / 2) / WIDTH) * dur;
    setPlayhead(Math.max(0, Math.min(dur, t)));
  };

  if (segs.length === 0) {
    return (
      <Html center>
        <div className="text-[var(--color-text-dim)] text-sm">No timeline segments for this job.</div>
      </Html>
    );
  }

  return (
    <group>
      {/* lane tracks */}
      {Object.entries(LANE_Y).map(([src, y]) => (
        <Line key={src} points={[[-WIDTH / 2, y, 0], [WIDTH / 2, y, 0]]} color={COLORS.border} lineWidth={1} transparent opacity={0.5} />
      ))}
      {/* lane labels */}
      {Object.entries(LANE_Y).map(([src, y]) => (
        <Html key={src} center position={[-WIDTH / 2 - 0.2, y, 0]} distanceFactor={12} pointerEvents="none">
          <div className="mono text-[10px] uppercase" style={{ color: MODALITY_COLOR[src] ?? COLORS.textDim, width: 56, textAlign: "right" }}>
            {src}
          </div>
        </Html>
      ))}

      {segs.map((s, i) => (
        <SegmentBar key={i} seg={s} x={(s.timestamp / Math.max(1, dur)) * WIDTH} dur={dur} onHover={setHover} />
      ))}

      {/* playhead */}
      <mesh ref={playRef} position={[phX, 0, 0]}>
        <boxGeometry args={[0.04, 3.4, 0.04]} />
        <meshBasicMaterial color={COLORS.accentSoft} transparent opacity={0.8} />
      </mesh>

      {/* clickable ground to scrub */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.8, 0]} onClick={onGroundClick}>
        <planeGeometry args={[WIDTH, 4]} />
        <meshBasicMaterial color={COLORS.void} transparent opacity={0.01} side={THREE.DoubleSide} />
      </mesh>

      {hover && (
        <Html center distanceFactor={11} position={[0, 2.4, 0]} pointerEvents="none">
          <div className="glass rounded-xl px-3 py-2 w-64">
            <div className="mono text-[10px] uppercase" style={{ color: MODALITY_COLOR[hover.source] }}>
              {hover.source} · {hover.timestamp.toFixed(1)}s
            </div>
            <div className="text-xs text-[var(--color-text)] mt-0.5 leading-snug">{hover.text}</div>
          </div>
        </Html>
      )}
    </group>
  );
}

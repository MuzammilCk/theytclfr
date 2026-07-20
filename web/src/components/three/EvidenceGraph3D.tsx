import { useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import * as THREE from "three";
import { COLORS } from "../../design/tokens";
import { useStore } from "../../store/useStore";
import type { ExtractedEntity } from "../../types/contracts";

const TYPE_COLOR: Record<string, string> = {
  product: COLORS.ocr,
  person: COLORS.asr,
  place: COLORS.audio,
  topic: COLORS.merged,
  unknown: COLORS.textDim,
};

function pos(i: number, n: number, r = 3): [number, number, number] {
  const a = (i / Math.max(1, n)) * Math.PI * 2;
  return [Math.cos(a) * r, Math.sin(i * 1.7) * 0.7, Math.sin(a) * r];
}

function EntityNode({
  p,
  e,
  onHover,
}: {
  p: [number, number, number];
  e: ExtractedEntity;
  onHover: (e: ExtractedEntity | null) => void;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const color = TYPE_COLOR[e.entity_type] ?? COLORS.textDim;
  const size = 0.22 + e.confidence * 0.4;
  useFrame(({ clock }) => {
    if (ref.current) {
      const t = clock.getElapsedTime();
      ref.current.scale.setScalar(1 + Math.sin(t * 1.8 + p[0]) * 0.07);
    }
  });
  return (
    <mesh
      ref={ref}
      position={p}
      onClick={(ev) => {
        ev.stopPropagation();
        onHover(e);
      }}
      onPointerOver={(ev) => {
        ev.stopPropagation();
        onHover(e);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        onHover(null);
        document.body.style.cursor = "default";
      }}
    >
      <dodecahedronGeometry args={[size, 0]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.5} roughness={0.3} metalness={0.3} />
    </mesh>
  );
}

export function EvidenceGraph3D() {
  const artifact = useStore((s) => (s.activeJobId ? s.artifacts[s.activeJobId] : null));
  const [hover, setHover] = useState<ExtractedEntity | null>(null);
  const groupRef = useRef<THREE.Group>(null);

  const entities = artifact?.evidence?.entities ?? [];
  const positions = useMemo(() => entities.map((_, i) => pos(i, entities.length)), [entities]);

  const edges = useMemo(() => {
    const out: Array<[THREE.Vector3, THREE.Vector3, number]> = [];
    for (let i = 0; i < entities.length; i++) {
      for (let j = i + 1; j < entities.length; j++) {
        const ti = entities[i].mentioned_at[0] ?? 0;
        const tj = entities[j].mentioned_at[0] ?? 0;
        const gap = Math.abs(ti - tj);
        if (gap < 200) {
          out.push([new THREE.Vector3(...positions[i]), new THREE.Vector3(...positions[j]), 1 - gap / 200]);
        }
      }
    }
    return out;
  }, [entities, positions]);

  useFrame(({ clock }) => {
    if (groupRef.current) groupRef.current.rotation.y = clock.getElapsedTime() * 0.1;
  });

  if (entities.length === 0) {
    return (
      <Html center>
        <div className="text-[var(--color-text-dim)] text-sm">No extracted entities for this job.</div>
      </Html>
    );
  }

  return (
    <group ref={groupRef}>
      {/* core */}
      <mesh>
        <sphereGeometry args={[0.4, 24, 24]} />
        <meshStandardMaterial color={COLORS.primaryDeep} emissive={COLORS.primary} emissiveIntensity={0.5} />
      </mesh>
      {entities.map((e, i) => (
        <Line key={`c${i}`} points={[new THREE.Vector3(0, 0, 0), new THREE.Vector3(...positions[i])]} color={TYPE_COLOR[e.entity_type] ?? COLORS.textDim} lineWidth={1.2} transparent opacity={0.4} />
      ))}
      {edges.map(([a, b, w], i) => (
        <Line key={`e${i}`} points={[a, b]} color={COLORS.secondary} lineWidth={1} transparent opacity={0.15 + w * 0.4} />
      ))}
      {entities.map((e, i) => (
        <EntityNode key={e.name} p={positions[i]} e={e} onHover={setHover} />
      ))}
      {hover && (
        <Html center distanceFactor={11} position={[0, 3.4, 0]} pointerEvents="none">
          <div className="glass rounded-xl px-3 py-2 w-52">
            <div className="text-xs font-semibold text-[var(--color-text)]">{hover.name}</div>
            <div className="mono text-[10px] uppercase mt-0.5" style={{ color: TYPE_COLOR[hover.entity_type] }}>
              {hover.entity_type} · {hover.confidence.toFixed(2)}
            </div>
            <div className="text-[10px] text-[var(--color-text-dim)] mt-1">
              @ {hover.mentioned_at.map((t) => `${t.toFixed(0)}s`).join(", ")}
            </div>
  </div>
        </Html>
      )}
    </group>
  );
}

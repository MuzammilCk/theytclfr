import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import * as THREE from "three";
import { COLORS, STAGES, isFailure, isTerminal, pipelineProgress, statusStage } from "../../design/tokens";
import { useStore } from "../../store/useStore";
import type { JobStatus } from "../../types/contracts";

type StageState = "done" | "active" | "pending" | "failed";

function computeStates(status: JobStatus): Record<string, StageState> {
  const keys = STAGES.map((s) => s.key);
  const out: Record<string, StageState> = {};
  if (status === "completed") {
    keys.forEach((k) => (out[k] = "done"));
    return out;
  }
  const cur = statusStage(status);
  const idx = Math.max(0, keys.indexOf(cur === "done" ? "stage_d" : cur));
  const failed = isFailure(status);
  keys.forEach((k, i) => {
    if (i < idx) out[k] = "done";
    else if (i === idx) out[k] = failed ? "failed" : "active";
    else out[k] = "pending";
  });
  return out;
}

const R = 4;
const NODE_ANGLE = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / STAGES.length;

function stateColor(s: StageState): string {
  if (s === "done") return COLORS.success;
  if (s === "active") return COLORS.primary;
  if (s === "failed") return COLORS.destructive;
  return COLORS.textFaint;
}

function Node({
  index,
  state,
  label,
  blurb,
  onClick,
}: {
  index: number;
  state: StageState;
  label: string;
  blurb: string;
  onClick: () => void;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const angle = NODE_ANGLE(index);
  const x = Math.cos(angle) * R;
  const z = Math.sin(angle) * R;
  const color = stateColor(state);
  const active = state === "active";

  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = clock.getElapsedTime();
    const pulse = active ? 1 + Math.sin(t * 3) * 0.08 : 1;
    ref.current.scale.setScalar(pulse);
    ref.current.rotation.y = t * 0.4;
    ref.current.rotation.x = t * 0.2;
  });

  return (
    <group position={[x, 0, z]}>
      <mesh
        ref={ref}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => (document.body.style.cursor = "default")}
      >
        <icosahedronGeometry args={[0.55, 1]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={active ? 1.1 : state === "pending" ? 0.1 : 0.6}
          roughness={0.3}
          metalness={0.4}
        />
      </mesh>
      {/* halo ring */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.95, 0.02, 8, 48]} />
        <meshBasicMaterial color={color} transparent opacity={active ? 0.8 : 0.3} />
      </mesh>
      <Html center distanceFactor={11} position={[0, 1.25, 0]} pointerEvents="none">
        <div className="pointer-events-none text-center w-32">
          <div className="mono text-[11px] font-bold" style={{ color }}>
            {label}
          </div>
          <div className="text-[9px] text-[var(--color-text-dim)] leading-tight mt-0.5">
            {blurb}
          </div>
        </div>
      </Html>
    </group>
  );
}

export function PipelineOrbit() {
  const artifact = useStore((s) => (s.activeJobId ? s.artifacts[s.activeJobId] : null));
  const setStage = useStore((s) => s.setStage);
  const setView = useStore((s) => s.setView);
  const selectJob = useStore((s) => s.selectJob);

  const status = (artifact?.job.status ?? "pending") as JobStatus;
  const states = useMemo(() => computeStates(status), [status]);
  const progress = pipelineProgress(status);
  const cometRef = useRef<THREE.Mesh>(null);

  const nodePositions = useMemo(
    () => STAGES.map((_, i) => [Math.cos(NODE_ANGLE(i)) * R, 0, Math.sin(NODE_ANGLE(i)) * R] as [number, number, number]),
    [],
  );

  // connector line through all nodes (closed loop)
  const loopPoints = useMemo(() => {
    const pts = nodePositions.map((p) => new THREE.Vector3(...p));
    pts.push(new THREE.Vector3(...nodePositions[0]));
    return pts;
  }, [nodePositions]);

  useFrame(({ clock }) => {
    if (cometRef.current) {
      const arc = progress * (STAGES.length - 1) * (2 * Math.PI) / STAGES.length;
      const a = -Math.PI / 2 + arc;
      cometRef.current.position.set(Math.cos(a) * R, 0, Math.sin(a) * R);
      const t = clock.getElapsedTime();
      cometRef.current.scale.setScalar(1 + Math.sin(t * 4) * 0.1);
    }
  });

  const drill: Record<string, () => void> = {
    ingest: () => setView("overview"),
    stage_a: () => setView("signals"),
    stage_b: () => setView("ocr"),
    stage_c: () => setView("evidence"),
    stage_d: () => setView("taxonomy"),
  };

  return (
    <group>
      {/* central core: progress orb */}
      <mesh>
        <sphereGeometry args={[0.6, 32, 32]} />
        <meshStandardMaterial
          color={COLORS.primaryDeep}
          emissive={COLORS.primary}
          emissiveIntensity={0.5}
          roughness={0.2}
          metalness={0.6}
        />
      </mesh>
      <Html center distanceFactor={12} position={[0, 1.5, 0]} pointerEvents="none">
        <div className="pointer-events-none text-center w-48">
          <div className="mono text-[10px] uppercase tracking-widest text-[var(--color-text-faint)]">
            Pipeline
          </div>
          <div className="mono text-sm font-semibold text-[var(--color-text)]">
            {Math.round(progress * 100)}%
          </div>
        </div>
      </Html>

      {/* connector loop */}
      <Line points={loopPoints} color={COLORS.border} lineWidth={1.5} transparent opacity={0.6} />
      <Line
        points={loopPoints.slice(0, Math.max(2, Math.round(progress * STAGES.length) + 1))}
        color={COLORS.primary}
        lineWidth={2.5}
      />

      {/* progress comet */}
      {!isTerminal(status) && (
        <mesh ref={cometRef}>
          <sphereGeometry args={[0.18, 16, 16]} />
          <meshBasicMaterial color={COLORS.secondary} />
        </mesh>
      )}

      {STAGES.map((s, i) => (
        <Node
          key={s.key}
          index={i}
          state={states[s.key]}
          label={s.label}
          blurb={s.blurb}
          onClick={() => {
            setStage(s.key);
            (drill[s.key] ?? (() => setView("overview")))();
          }}
        />
      ))}

      {/* ground reflection disc */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.8, 0]}>
        <ringGeometry args={[R - 0.1, R + 0.1, 64]} />
        <meshBasicMaterial color={COLORS.border} transparent opacity={0.25} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

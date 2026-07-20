import { useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import { COLORS } from "../../design/tokens";
import { useStore } from "../../store/useStore";
import type { SignalManifest } from "../../types/contracts";

interface Sig {
  key: string;
  label: string;
  value: number; // 0..1
  raw: string;
}

function buildSignals(m: SignalManifest): Sig[] {
  const clamp = (v: number) => Math.max(0, Math.min(1, v));
  return [
    { key: "speech", label: "Speech", value: m.has_speech ? 1 : 0, raw: m.has_speech ? "detected" : "absent" },
    { key: "music", label: "Music", value: m.has_music ? 1 : 0, raw: m.has_music ? "detected" : "absent" },
    { key: "burned", label: "Burned-in text", value: m.has_burned_in_text ? 1 : 0, raw: m.has_burned_in_text ? "yes" : "no" },
    { key: "faces", label: "Faces", value: m.has_faces ? 1 : 0, raw: m.has_faces ? "yes" : "no" },
    { key: "sub", label: "Subtitle track", value: m.has_subtitle_track ? 1 : 0, raw: m.has_subtitle_track ? "yes" : "no" },
    { key: "structural", label: "Structural score", value: clamp(m.structural_score), raw: m.structural_score.toFixed(2) },
    { key: "list", label: "List likelihood", value: clamp(m.list_likelihood), raw: m.list_likelihood.toFixed(2) },
    { key: "countdown", label: "Countdown likelihood", value: clamp(m.countdown_likelihood), raw: m.countdown_likelihood.toFixed(2) },
    { key: "overlay", label: "Overlay text density", value: clamp(m.overlay_text_density), raw: m.overlay_text_density.toFixed(2) },
    { key: "ordinal", label: "Ordinal pattern", value: clamp(m.ordinal_pattern_score), raw: m.ordinal_pattern_score.toFixed(2) },
    { key: "repeat", label: "Scene repeat", value: clamp(m.scene_repeat_score), raw: m.scene_repeat_score.toFixed(2) },
    { key: "motion", label: "Motion score", value: clamp(m.motion_score), raw: m.motion_score.toFixed(2) },
    { key: "probing", label: "Probing confidence", value: clamp(m.probing_confidence), raw: m.probing_confidence.toFixed(2) },
    { key: "ocrcov", label: "OCR expected coverage", value: clamp(m.ocr_expected_coverage), raw: m.ocr_expected_coverage.toFixed(2) },
    { key: "asrval", label: "ASR expected value", value: clamp(m.asr_expected_value), raw: m.asr_expected_value.toFixed(2) },
    { key: "motiond", label: "Motion density", value: clamp(m.motion_density / 10), raw: m.motion_density.toFixed(1) + "/min" },
    { key: "cuts", label: "Scene cuts", value: clamp(m.scene_cut_count / 60), raw: String(m.scene_cut_count) },
  ];
}

// Fibonacci sphere distribution
function spherePoint(i: number, n: number, radius: number): [number, number, number] {
  const phi = Math.acos(1 - (2 * (i + 0.5)) / n);
  const theta = Math.PI * (1 + Math.sqrt(5)) * i;
  return [
    radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  ];
}

function SigNode({
  pos,
  sig,
  onHover,
}: {
  pos: [number, number, number];
  sig: Sig;
  onHover: (s: Sig | null) => void;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const color = sig.value > 0.66 ? COLORS.primary : sig.value > 0.33 ? COLORS.secondary : COLORS.textFaint;
  const size = 0.1 + sig.value * 0.34;

  useFrame(({ clock }) => {
    if (ref.current) {
      const t = clock.getElapsedTime();
      const p = 1 + Math.sin(t * 1.6 + pos[0]) * 0.05 * sig.value;
      ref.current.scale.setScalar(p);
    }
  });

  return (
    <mesh
      ref={ref}
      position={pos}
      onClick={(e) => {
        e.stopPropagation();
        onHover(sig);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        onHover(sig);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        onHover(null);
        document.body.style.cursor = "default";
      }}
    >
      <sphereGeometry args={[size, 20, 20]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.25 + sig.value * 0.5} roughness={0.35} />
    </mesh>
  );
}

export function SignalConstellation() {
  const artifact = useStore((s) => (s.activeJobId ? s.artifacts[s.activeJobId] : null));
  const [hover, setHover] = useState<Sig | null>(null);
  const groupRef = useRef<THREE.Group>(null);

  const manifest = artifact?.manifest;
  const signals = useMemo(() => (manifest ? buildSignals(manifest) : []), [manifest]);
  const positions = useMemo(
    () => signals.map((_, i) => spherePoint(i, signals.length, 3.2)),
    [signals],
  );

  useFrame(({ clock }) => {
    if (groupRef.current) groupRef.current.rotation.y = clock.getElapsedTime() * 0.12;
  });

  if (!manifest) {
    return (
      <Html center>
        <div className="text-[var(--color-text-dim)] text-sm">No Stage A signal data for this job.</div>
      </Html>
    );
  }

  return (
    <group ref={groupRef}>
      {/* core */}
      <mesh>
        <icosahedronGeometry args={[0.5, 1]} />
        <meshStandardMaterial color={COLORS.primaryDeep} emissive={COLORS.primary} emissiveIntensity={0.3} wireframe />
      </mesh>
      {signals.map((s, i) => (
        <SigNode key={s.key} pos={positions[i]} sig={s} onHover={setHover} />
      ))}
      {hover && (
        <Html center distanceFactor={10} position={[0, 3.6, 0]} pointerEvents="none">
          <div className="glass rounded-xl px-3 py-2 text-center w-44">
            <div className="text-xs font-semibold text-[var(--color-text)]">{hover.label}</div>
            <div className="mono text-sm" style={{ color: COLORS.secondary }}>
              {hover.raw}
            </div>
          </div>
        </Html>
      )}
    </group>
  );
}

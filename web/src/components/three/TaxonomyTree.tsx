import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import * as THREE from "three";
import { COLORS } from "../../design/tokens";
import { useStore } from "../../store/useStore";

interface TreeNode {
  id: string;
  label: string;
  sub?: string;
  color: string;
  pos: [number, number, number];
}

export function TaxonomyTree() {
  const artifact = useStore((s) => (s.activeJobId ? s.artifacts[s.activeJobId] : null));
  const result = artifact?.result;
  const groupRef = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (groupRef.current) groupRef.current.rotation.y = Math.sin(clock.getElapsedTime() * 0.25) * 0.25;
  });

  if (!result) {
    return (
      <Html center>
        <div className="text-[var(--color-text-dim)] text-sm">No taxonomy result for this job.</div>
      </Html>
    );
  }

  const items = result.items;
  const t = result.taxonomy;
  const nodes: TreeNode[] = [
    { id: "root", label: artifact?.job.video_title ?? "Video", sub: "source", color: COLORS.primary, pos: [0, 4, 0] },
    { id: "parent", label: t.parent_category, color: COLORS.secondary, pos: [0, 2.3, 0] },
    { id: "child", label: t.child_category, color: COLORS.accentSoft, pos: [0, 0.7, 0] },
    { id: "intent", label: t.intent, sub: `conf ${(t.confidence * 100).toFixed(0)}%`, color: COLORS.merged, pos: [0, -0.9, 0] },
  ];
  items.forEach((it, i) => {
    const x = (i - (items.length - 1) / 2) * 1.5;
    nodes.push({
      id: `item-${i}`,
      label: it.name,
      sub: it.item_type,
      color: COLORS.ocr,
      pos: [x, -2.7, 0],
    });
  });

  const posOf = (id: string) => nodes.find((n) => n.id === id)!.pos;
  const links: Array<[string, string]> = [
    ["root", "parent"],
    ["parent", "child"],
    ["child", "intent"],
  ];
  items.forEach((_, i) => links.push(["intent", `item-${i}`]));

  return (
    <group ref={groupRef}>
      {links.map(([a, b], i) => (
        <Line key={i} points={[new THREE.Vector3(...posOf(a)), new THREE.Vector3(...posOf(b))]} color={COLORS.border} lineWidth={1.5} transparent opacity={0.5} />
      ))}
      {nodes.map((n) => (
        <group key={n.id} position={n.pos}>
          <mesh>
            <sphereGeometry args={[n.id.startsWith("item") ? 0.28 : 0.36, 20, 20]} />
            <meshStandardMaterial color={n.color} emissive={n.color} emissiveIntensity={0.5} roughness={0.3} />
          </mesh>
          <Html center distanceFactor={10} position={[0, n.id.startsWith("item") ? -0.7 : 0.7, 0]} pointerEvents="none">
            <div className="text-center w-40">
              <div className="text-xs font-semibold leading-tight" style={{ color: n.color }}>
                {n.label}
              </div>
              {n.sub && <div className="mono text-[9px] text-[var(--color-text-dim)] mt-0.5">{n.sub}</div>}
            </div>
          </Html>
        </group>
      ))}
    </group>
  );
}

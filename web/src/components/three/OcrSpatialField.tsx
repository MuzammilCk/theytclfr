import { useMemo } from "react";
import { Html, Line } from "@react-three/drei";
import * as THREE from "three";
import { COLORS } from "../../design/tokens";
import { useStore } from "../../store/useStore";
import type { OCRSegment } from "../../types/contracts";

const W = 6;
const H = (6 * 9) / 16;

function rectPoints(cx: number, cy: number, w: number, h: number, z: number): THREE.Vector3[] {
  const x0 = cx - w / 2;
  const x1 = cx + w / 2;
  const y0 = cy - h / 2;
  const y1 = cy + h / 2;
  return [
    new THREE.Vector3(x0, y0, z),
    new THREE.Vector3(x1, y0, z),
    new THREE.Vector3(x1, y1, z),
    new THREE.Vector3(x0, y1, z),
    new THREE.Vector3(x0, y0, z),
  ];
}

export function OcrSpatialField() {
  const artifact = useStore((s) => (s.activeJobId ? s.artifacts[s.activeJobId] : null));
  const playhead = useStore((s) => s.playhead);

  const segs: OCRSegment[] = artifact?.bundle?.ocr_segments ?? [];
  const activeIndex = useMemo(() => {
    if (segs.length === 0) return 0;
    let best = 0;
    let bestD = Infinity;
    segs.forEach((s, i) => {
      const d = Math.abs(s.frame_timestamp - playhead);
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    return best;
  }, [segs, playhead]);

  if (segs.length === 0) {
    return (
      <Html center>
        <div className="text-[var(--color-text-dim)] text-sm">No OCR segments for this job.</div>
      </Html>
    );
  }

  const frameBorder = rectPoints(0, 0, W, H, 0);

  return (
    <group>
      {/* back frames (ghost stack) */}
      {segs.map((s, i) => {
        const z = (activeIndex - i) * 0.55;
        const opacity = i === activeIndex ? 0.0 : 0.12;
        if (opacity === 0) return null;
        return (
          <Line key={`f${i}`} points={rectPoints(0, 0, W, H, z)} color={COLORS.border} lineWidth={1} transparent opacity={opacity} />
        );
      })}

      {/* active frame border */}
      <Line points={frameBorder} color={COLORS.ocr} lineWidth={2} transparent opacity={0.6} />

      {/* bounding boxes of the active frame */}
      {segs[activeIndex].bounding_boxes?.map((b, bi) => {
        const cx = (b.x + b.w / 2 - 0.5) * W;
        const cy = (0.5 - (b.y + b.h / 2)) * H;
        const w = b.w * W;
        const h = b.h * H;
        return (
          <group key={bi}>
            <Line points={rectPoints(cx, cy, w, h, 0.02)} color={COLORS.ocr} lineWidth={2} />
            <Html center position={[cx, cy + h / 2 + 0.2, 0.1]} distanceFactor={9} pointerEvents="none">
              <div className="mono text-[10px] px-1.5 py-0.5 rounded" style={{ background: COLORS.ocr, color: "#060912", whiteSpace: "nowrap" }}>
                {b.text ?? ""}
              </div>
            </Html>
          </group>
        );
      })}

      {/* frame meta */}
      <Html center position={[0, H / 2 + 0.5, 0]} pointerEvents="none">
        <div className="mono text-[11px] text-[var(--color-text-dim)]">
          frame @ {segs[activeIndex].frame_timestamp.toFixed(1)}s · {segs[activeIndex].bounding_boxes?.length ?? 0} regions
        </div>
      </Html>
    </group>
  );
}

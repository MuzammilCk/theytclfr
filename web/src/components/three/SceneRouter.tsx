import { useRef } from "react";
import * as THREE from "three";
import { StageCanvas } from "./StageCanvas";
import { PipelineOrbit } from "./PipelineOrbit";
import { SignalConstellation } from "./SignalConstellation";
import { TimelineTheatre } from "./TimelineTheatre";
import { EvidenceGraph3D } from "./EvidenceGraph3D";
import { TaxonomyTree } from "./TaxonomyTree";
import { OcrSpatialField } from "./OcrSpatialField";
import { useStore, type ViewKey } from "../../store/useStore";
import { gsap, useGSAP, prefersReducedMotion } from "../../lib/gsap";

const CONFIG: Record<ViewKey, { camera: [number, number, number]; autoRotate: boolean; enablePan: boolean }> = {
  overview: { camera: [0, 2.2, 10.5], autoRotate: true, enablePan: false },
  signals: { camera: [0, 0, 9], autoRotate: false, enablePan: false },
  timeline: { camera: [0, 1.2, 11], autoRotate: false, enablePan: false },
  evidence: { camera: [0, 1, 10], autoRotate: false, enablePan: false },
  taxonomy: { camera: [0, 0, 10.5], autoRotate: true, enablePan: false },
  ocr: { camera: [0, 0, 9], autoRotate: false, enablePan: false },
  search: { camera: [0, 1, 10], autoRotate: false, enablePan: false },
};

export function SceneRouter() {
  const view = useStore((s) => s.view);
  const cfg = CONFIG[view];
  const sceneRef = useRef<THREE.Group>(null);

  // A subtle "settle" when the scene swaps — spatial continuity alongside the
  // camera move, so view changes never feel like a hard cut.
  useGSAP(
    () => {
      const g = sceneRef.current;
      if (!g || prefersReducedMotion()) return;
      gsap.fromTo(
        g.scale,
        { x: 0.97, y: 0.97, z: 0.97 },
        { x: 1, y: 1, z: 1, duration: 0.5, ease: "power3.out" },
      );
    },
    { dependencies: [view], scope: sceneRef },
  );

  let scene = null;
  switch (view) {
    case "overview":
      scene = <PipelineOrbit />;
      break;
    case "signals":
      scene = <SignalConstellation />;
      break;
    case "timeline":
      scene = <TimelineTheatre />;
      break;
    case "evidence":
      scene = <EvidenceGraph3D />;
      break;
    case "taxonomy":
      scene = <TaxonomyTree />;
      break;
    case "ocr":
      scene = <OcrSpatialField />;
      break;
    case "search":
      scene = <EvidenceGraph3D />;
      break;
  }

  return (
    <StageCanvas camera={cfg.camera} autoRotate={cfg.autoRotate} enablePan={cfg.enablePan}>
      <group ref={sceneRef}>{scene}</group>
    </StageCanvas>
  );
}

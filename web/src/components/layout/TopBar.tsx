import { useRef, useState, type UIEvent } from "react";
import { KeyRound, Radio, Boxes, X } from "lucide-react";
import { useStore } from "../../store/useStore";
import { Button } from "../ui/primitives";
import { gsap, useGSAP, MOTION, prefersReducedMotion } from "../../lib/gsap";

function TokenModal({ onClose }: { onClose: () => void }) {
  const token = useStore((s) => s.token);
  const setToken = useStore((s) => s.setToken);
  const [val, setVal] = useState(token);
  const rootRef = useRef<HTMLDivElement>(null);

  const close = () => {
    const root = rootRef.current;
    if (!root || prefersReducedMotion()) {
      onClose();
      return;
    }
    const scrim = root.querySelector(".scrim");
    const card = root.querySelector(".card");
    gsap.to(card, { opacity: 0, scale: 0.97, y: 8, duration: MOTION.exit, ease: MOTION.easeExit });
    gsap.to(scrim, { opacity: 0, duration: MOTION.exit, ease: MOTION.easeExit, onComplete: onClose });
  };

  useGSAP(
    () => {
      const root = rootRef.current;
      if (!root || prefersReducedMotion()) return;
      gsap.fromTo(root.querySelector(".scrim"), { opacity: 0 }, { opacity: 1, duration: 0.2, ease: "power2.out" });
      gsap.fromTo(
        root.querySelector(".card"),
        { opacity: 0, scale: 0.96, y: 12 },
        { opacity: 1, scale: 1, y: 0, duration: 0.3, ease: MOTION.ease },
      );
    },
    { scope: rootRef },
  );

  return (
    <div
      ref={rootRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-4"
      onClick={close}
    >
      <div
        className="card glass rounded-2xl p-6 w-[440px] max-w-[92vw]"
        onClick={(e: UIEvent) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <KeyRound size={15} className="text-[var(--color-primary)]" /> Connect to API
          </h2>
          <button
            onClick={close}
            className="text-[var(--color-text-dim)] hover:text-[var(--color-text)] cursor-pointer transition-colors"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>
        <p className="text-xs text-[var(--color-text-dim)] mb-4 leading-relaxed">
          Paste a JWT bearer token issued by your auth provider. With a token set, the console
          talks to the FastAPI backend at <span className="mono text-[var(--color-text)]">/api/v3</span>.
          Without one, submission and search are disabled.
        </p>
        <textarea
          value={val}
          onChange={(e) => setVal(e.target.value)}
          placeholder="eyJhbGciOiJIUzI1Ni…"
          rows={4}
          className="w-full rounded-xl bg-[var(--color-void)] border border-[var(--color-border)] p-3 text-xs mono text-[var(--color-text)] resize-none focus:outline-none focus:border-[var(--color-primary)]/60 transition-colors"
        />
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              setToken(val.trim());
              close();
            }}
          >
            Save token
          </Button>
        </div>
      </div>
    </div>
  );
}

export function TopBar() {
  const connectivity = useStore((s) => s.connectivity);
  const token = useStore((s) => s.token);
  const [open, setOpen] = useState(false);

  const live = connectivity === "live";
  const offline = connectivity === "offline";

  const pill = live
    ? { text: "LIVE", color: "var(--color-success)", bg: "#34d39912", border: "var(--color-success)", pulse: true }
    : offline
      ? { text: "OFFLINE", color: "var(--color-text-faint)", bg: "transparent", border: "var(--color-border)", pulse: false }
      : { text: "CONNECTING", color: "var(--color-warning)", bg: "#fbbf2412", border: "var(--color-warning)", pulse: true };

  return (
    <header className="h-14 flex items-center justify-between px-4 border-b border-[var(--color-border)] bg-[var(--color-void)]/70 backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-xl bg-[var(--color-primary)] flex items-center justify-center">
          <Boxes size={17} className="text-white" />
        </div>
        <div className="leading-none">
          <div className="font-display text-[15px] font-semibold tracking-[0.18em] uppercase">
            ytclfr <span className="text-[var(--color-primary)]">Nexus</span>
          </div>
          <div className="text-[10px] text-[var(--color-text-faint)] tracking-wide mt-0.5">
            video intelligence console
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div
          className="flex items-center gap-2 rounded-full px-3 py-1 text-[10.5px] mono tracking-wider border"
          style={{ color: pill.color, borderColor: pill.border, background: pill.bg }}
        >
          <Radio size={12} className={pill.pulse ? "animate-pulse" : ""} />
          {pill.text}
        </div>
        <Button variant={token ? "subtle" : "primary"} icon={<KeyRound size={14} />} onClick={() => setOpen(true)}>
          {token ? "Token set" : "Connect"}
        </Button>
      </div>

      {open && <TokenModal onClose={() => setOpen(false)} />}
    </header>
  );
}

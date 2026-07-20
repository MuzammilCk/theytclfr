import { useState } from "react";
import { Link2, RotateCcw, Send, AlertTriangle, Inbox } from "lucide-react";
import { useStore } from "../../store/useStore";
import { isFailure, statusColor, statusLabel } from "../../design/tokens";
import { Button, EmptyState, cx } from "../ui/primitives";
import { Reveal } from "../motion/Reveal";

function StatusDot({ status }: { status: string }) {
  const color = statusColor(status as never);
  const pulse = !["completed", "failed", "dead_letter", "v3_stage_d_failed"].includes(status);
  return (
    <span className="relative flex h-2 w-2 shrink-0">
      {pulse && (
        <span className="absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping" style={{ background: color }} />
      )}
      <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: color }} />
    </span>
  );
}

function SubmitConsole() {
  const submit = useStore((s) => s.submit);
  const submitting = useStore((s) => s.submitting);
  const lastError = useStore((s) => s.lastError);
  const [url, setUrl] = useState("");
  const valid = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+/i.test(url);

  const run = async () => {
    if (!valid) return;
    await submit(url.trim());
    setUrl("");
  };

  return (
    <div className="p-3.5 border-b border-[var(--color-border)]">
      <label className="label" htmlFor="yt-url">
        Submit video URL
      </label>
      <div className="mt-2 flex flex-col gap-2">
        <div className="flex items-center gap-2 rounded-xl bg-[var(--color-void)] border border-[var(--color-border)] px-3 transition-colors focus-within:border-[var(--color-primary)]/60">
          <Link2 size={15} className="text-[var(--color-text-faint)]" />
          <input
            id="yt-url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            placeholder="https://youtu.be/…"
            className="bg-transparent w-full py-2.5 text-sm outline-none placeholder:text-[var(--color-text-faint)]"
          />
        </div>
        <Button onClick={run} disabled={!valid || submitting} icon={<Send size={14} />}>
          {submitting ? "Dispatching…" : "Extract intelligence"}
        </Button>
        {lastError && (
          <div className="rise flex items-start gap-1.5 text-[11px] text-[var(--color-destructive)] leading-snug">
            <AlertTriangle size={12} className="mt-0.5 shrink-0" />
            <span>{lastError}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function JobList() {
  const order = useStore((s) => s.order);
  const artifacts = useStore((s) => s.artifacts);
  const activeJobId = useStore((s) => s.activeJobId);
  const selectJob = useStore((s) => s.selectJob);
  const retry = useStore((s) => s.retry);

  if (order.length === 0) {
    return (
      <div className="flex-1 min-h-0 flex">
        <EmptyState
          icon={<Inbox size={26} />}
          title="No jobs yet"
          hint="Submit a YouTube URL above to start extracting structured intelligence."
        />
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-2.5">
      <div className="label px-1 pb-2">Jobs · {order.length}</div>
      <Reveal as="ul" staggerSelector="li" className="flex flex-col gap-1.5 list-none m-0 p-0">
        {order.map((id) => {
          const a = artifacts[id];
          if (!a) return null;
          const active = id === activeJobId;
          const failed = isFailure(a.job.status);
          return (
            <li key={id}>
              <button
                onClick={() => selectJob(id)}
                className={cx(
                  "w-full text-left rounded-xl p-3 border transition-[background,border-color] duration-200 cursor-pointer",
                  active
                    ? "border-[var(--color-primary)]/50 bg-[var(--color-primary)]/10"
                    : "border-transparent hover:bg-[var(--color-surface-2)]",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <StatusDot status={a.job.status} />
                    <span className="text-[13px] font-medium truncate">
                      {a.job.video_title ?? "Untitled"}
                    </span>
                  </div>
                  {failed && (
                    <span
                      title="Retry job"
                      role="button"
                      tabIndex={0}
                      onClick={(e) => {
                        e.stopPropagation();
                        retry(id);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.stopPropagation();
                          retry(id);
                        }
                      }}
                      className="text-[var(--color-destructive)] hover:text-[var(--color-text)] cursor-pointer transition-colors p-1 -m-1 rounded-md focus-visible:outline-2"
                    >
                      <RotateCcw size={13} />
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between mt-1.5">
                  <span className="mono text-[10px] text-[var(--color-text-faint)] truncate max-w-[160px]">
                    {a.job.youtube_url.replace(/^https?:\/\//, "")}
                  </span>
                  <span className="mono text-[10px]" style={{ color: statusColor(a.job.status as never) }}>
                    {statusLabel(a.job.status as never)}
                  </span>
                </div>
                {failed && a.job.error_message && (
                  <div className="flex items-start gap-1 mt-1.5 text-[10px] text-[var(--color-destructive)]">
                    <AlertTriangle size={11} className="mt-0.5 shrink-0" />
                    <span className="truncate">{a.job.error_message}</span>
                  </div>
                )}
              </button>
            </li>
          );
        })}
      </Reveal>
    </div>
  );
}

export function LeftRail() {
  return (
    <aside className="w-[280px] flex flex-col border-r border-[var(--color-border)] bg-[var(--color-void)]/40">
      <SubmitConsole />
      <JobList />
    </aside>
  );
}

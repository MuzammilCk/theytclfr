import type { ButtonHTMLAttributes, ReactNode } from "react";

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "danger" | "subtle";
  icon?: ReactNode;
}

export function Button({
  variant = "primary",
  icon,
  className,
  children,
  ...rest
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium tracking-wide transition-[background,color,border,box-shadow,transform] duration-200 cursor-pointer active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100 select-none";
  const variants: Record<string, string> = {
    // solid single-hue indigo — no gradient text
    primary:
      "text-white bg-[var(--color-primary)] hover:bg-[var(--color-secondary)] shadow-[0_6px_20px_-10px_var(--color-primary)]",
    ghost:
      "text-[var(--color-text-dim)] border border-[var(--color-border)] hover:text-[var(--color-text)] hover:border-[var(--color-primary)]/60 bg-[var(--color-surface)]/40",
    subtle: "bg-[var(--color-surface-2)] text-[var(--color-text)] hover:bg-[var(--color-elevated)]",
    danger:
      "text-[var(--color-destructive)] border border-[var(--color-destructive)]/40 hover:bg-[var(--color-destructive)]/10",
  };
  return (
    <button className={cx(base, variants[variant], className)} {...rest}>
      {icon}
      {children}
    </button>
  );
}

export function Panel({
  title,
  subtitle,
  right,
  children,
  className,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx("glass rounded-2xl p-4 flex flex-col min-h-0", className)}>
      {(title || right) && (
        <header className="flex items-start justify-between mb-3 gap-3">
          <div>
            {title && (
              <h2 className="text-[13px] font-semibold tracking-wide text-[var(--color-text)]">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="text-[11px] text-[var(--color-text-dim)] mt-0.5">{subtitle}</p>
            )}
          </div>
          {right}
        </header>
      )}
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}

export function Badge({
  children,
  color = "var(--color-text-dim)",
  filled,
}: {
  children: ReactNode;
  color?: string;
  filled?: boolean;
}) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-medium mono"
      style={
        filled
          ? { background: color, color: "#06080f" }
          : { color, border: `1px solid ${color}55`, background: `${color}12` }
      }
    >
      {children}
    </span>
  );
}

export function StatPill({
  label,
  value,
  color,
}: {
  label: string;
  value: ReactNode;
  color?: string;
}) {
  return (
    <div className="glass-soft rounded-xl px-3 py-2 flex flex-col gap-1">
      <span className="label">{label}</span>
      <span className="mono text-[15px] font-semibold" style={{ color: color ?? "var(--color-text)" }}>
        {value}
      </span>
    </div>
  );
}

export function ProgressBar({ value, color = "var(--color-primary)" }: { value: number; color?: string }) {
  return (
    <div className="h-[3px] w-full rounded-full bg-[var(--color-surface-2)] overflow-hidden">
      <div
        className="h-full rounded-full transition-[width] duration-700 ease-out"
        style={{ width: `${Math.max(2, Math.round(value * 100))}%`, background: color }}
      />
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  hint,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
}) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center px-6 py-10 gap-2">
      {icon && <div className="text-[var(--color-text-faint)] opacity-70">{icon}</div>}
      <p className="text-sm font-medium text-[var(--color-text-dim)]">{title}</p>
      {hint && <p className="text-[11px] text-[var(--color-text-faint)] max-w-[260px] leading-relaxed">{hint}</p>}
    </div>
  );
}

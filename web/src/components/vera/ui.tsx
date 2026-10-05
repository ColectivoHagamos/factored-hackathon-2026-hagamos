import type { LucideIcon } from "lucide-react";
import { CircleCheck, CircleQuestionMark, FileText, Lightbulb, MessageSquareText, Search, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export const STROKE = 1.75;

export const CLIENT_ICONS: Record<string, LucideIcon> = {
  A1: Search,
  A3: TriangleAlert,
  A6: MessageSquareText,
  A10: FileText,
  human: MessageSquareText,
  scam: TriangleAlert,
  inject: CircleQuestionMark,
};

export function IconBox({
  icon: Icon, state = "normal", className, children,
}: { icon?: LucideIcon; state?: "normal" | "active" | "disabled"; className?: string; children?: ReactNode }) {
  return (
    <span
      aria-hidden
      className={cn(
        "grid size-10 shrink-0 place-items-center rounded-[12px]",
        state === "active" ? "bg-primary-light text-primary" : "border border-primary-dark/8 bg-surface/70 text-primary-dark",
        className,
      )}
    >
      {Icon ? <Icon className={cn("size-5", state === "disabled" && "opacity-40")} strokeWidth={STROKE} /> : children}
    </span>
  );
}

export const STAGES = ["received", "analysis", "verification", "result", "resolved"] as const;
export type StageKey = (typeof STAGES)[number];

export const STAGE: Record<StageKey, { icon: LucideIcon; box: string; tag: string; tagKey: string }> = {
  received: { icon: MessageSquareText, box: "bg-stage-received", tag: "bg-stage-received-tag text-foreground", tagKey: "stage.tag.initial" },
  analysis: { icon: Search, box: "bg-stage-analysis", tag: "bg-stage-analysis-tag text-foreground", tagKey: "stage.tag.progress" },
  verification: { icon: FileText, box: "bg-stage-verification", tag: "bg-stage-verification-tag text-foreground", tagKey: "stage.tag.progress" },
  result: { icon: Lightbulb, box: "bg-stage-result", tag: "bg-stage-result-tag text-foreground", tagKey: "stage.tag.result" },
  resolved: { icon: CircleCheck, box: "bg-primary-dark text-primary-foreground", tag: "bg-stage-resolved-tag text-primary-foreground", tagKey: "stage.tag.complete" },
};

export function StageTag({ stage, label }: { stage: StageKey; label: string }) {
  return <span className={cn("inline-flex rounded-full px-2.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.12em]", STAGE[stage].tag)}>{label}</span>;
}

export function StageIcon({ stage, reached }: { stage: StageKey; reached: boolean }) {
  const s = STAGE[stage];
  const Icon = s.icon;
  return (
    <span aria-hidden className={cn("relative grid size-10 shrink-0 place-items-center rounded-[12px]", reached ? s.box : "border border-primary-dark/8 bg-surface/70")}>
      <Icon className={cn("size-5", !reached && "opacity-40", reached && stage !== "resolved" && "text-primary-dark")} strokeWidth={STROKE} />
      {reached && stage === "resolved" && <span className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-lime" />}
    </span>
  );
}

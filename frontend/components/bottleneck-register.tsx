"use client";

import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";

// ── Types ────────────────────────────────────────────────────────────────────

interface BottleneckPR {
  number: number;
  title: string;
  hours_open: number;
  severity: "critical" | "warning" | "stale";
}

interface BottleneckUser {
  username: string;
  summary: {
    total_stale_prs: number;
    critical_count: number;
    warning_count: number;
    stale_count: number;
    commit_velocity: { current_week: number; previous_week: number; trend: number };
    merge_lag: { average_hours: number; pr_count: number };
  };
  bottlenecks_by_repo: Record<string, BottleneckPR[]>;
}

export interface BottleneckData {
  status: string;
  total_bottlenecks: number;
  by_user: BottleneckUser[];
}

interface FallbackPR {
  repo: string;
  number: number;
  title: string;
  hours_open: number;
}

interface BottleneckRegisterProps {
  data: BottleneckData | null;
  fallbackPRs: FallbackPR[];
  username: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-red-950 text-red-400 border-red-800/50",
  warning: "bg-amber-950 text-amber-400 border-amber-800/50",
  stale: "bg-zinc-800 text-zinc-400 border-zinc-700/50",
};

function SeverityBadge({ severity }: { severity: string }) {
  return (
    <Badge
      className={`${SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.stale} hover:bg-transparent font-mono text-[10px] px-1.5 py-0 border`}
    >
      {severity}
    </Badge>
  );
}

function SeverityDot({ color }: { color: string }) {
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${color}`} />;
}

// ── Component ────────────────────────────────────────────────────────────────

export function BottleneckRegister({ data, fallbackPRs, username }: BottleneckRegisterProps) {
  // Resolve the user's bottleneck entry from the API data
  const userEntry = data?.by_user?.find((u) => u.username === username) ?? data?.by_user?.[0] ?? null;

  // If we have valid API data, use it; otherwise fall back to legacy stale_prs
  const hasApiData = userEntry && Object.keys(userEntry.bottlenecks_by_repo).length > 0;

  // Fallback: convert flat stale_prs into the repo-grouped shape
  const repoMap: Record<string, BottleneckPR[]> = {};

  if (hasApiData) {
    Object.assign(repoMap, userEntry.bottlenecks_by_repo);
  } else if (fallbackPRs.length > 0) {
    for (const pr of fallbackPRs) {
      const key = pr.repo;
      if (!repoMap[key]) repoMap[key] = [];
      repoMap[key].push({
        number: pr.number,
        title: pr.title,
        hours_open: pr.hours_open,
        severity: "warning",
      });
    }
  }

  const repoKeys = Object.keys(repoMap);
  const totalCount = hasApiData ? userEntry.summary.total_stale_prs : fallbackPRs.length;

  // ── Empty state ────────────────────────────────────────────────────────
  if (repoKeys.length === 0) {
    return (
      <div className="text-xs font-mono text-zinc-600 text-center py-6 border border-dashed border-zinc-800 rounded-md">
        No pipeline friction detected. Clean execution.
      </div>
    );
  }

  // ── Summary counts ─────────────────────────────────────────────────────
  const criticalCount = hasApiData ? userEntry.summary.critical_count : 0;
  const warningCount = hasApiData
    ? userEntry.summary.warning_count
    : fallbackPRs.length;
  const staleCount = hasApiData ? userEntry.summary.stale_count : 0;

  return (
    <div className="space-y-3">
      {/* Summary header */}
      <div className="flex items-center justify-between px-1">
        <span className="font-mono text-xs text-zinc-300">
          <span className="font-semibold text-zinc-100">{totalCount}</span> bottleneck{totalCount !== 1 ? "s" : ""}
        </span>
        <div className="flex items-center gap-2 font-mono text-[10px] text-zinc-500">
          {criticalCount > 0 && (
            <span className="flex items-center gap-1">
              <SeverityDot color="bg-red-400" />
              {criticalCount}
            </span>
          )}
          {warningCount > 0 && (
            <span className="flex items-center gap-1">
              <SeverityDot color="bg-amber-400" />
              {warningCount}
            </span>
          )}
          {staleCount > 0 && (
            <span className="flex items-center gap-1">
              <SeverityDot color="bg-zinc-400" />
              {staleCount}
            </span>
          )}
        </div>
      </div>

      {/* Accordion by repo */}
      <Accordion type="multiple" className="space-y-1">
        {repoKeys.map((repo) => {
          const prs = repoMap[repo];
          return (
            <AccordionItem
              key={repo}
              value={repo}
              className="border border-zinc-800/80 rounded-md bg-zinc-900/60 overflow-hidden not-last:border-b"
            >
              <AccordionTrigger className="px-3 py-2 hover:bg-zinc-800/40 hover:no-underline transition-colors text-xs font-mono text-zinc-300">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="truncate">{repo}</span>
                  <Badge
                    variant="outline"
                    className="border-zinc-700 bg-zinc-800/60 text-zinc-400 font-mono text-[10px] px-1.5 py-0"
                  >
                    {prs.length}
                  </Badge>
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-3 pb-2">
                <div className="space-y-2">
                  {prs.map((pr) => (
                    <div
                      key={pr.number}
                      className="flex items-start justify-between gap-2 py-1.5 border-t border-zinc-800/50 first:border-t-0"
                    >
                      <span className="font-mono text-xs text-zinc-200 line-clamp-1 min-w-0">
                        <span className="text-zinc-500">#{pr.number}</span>{" "}
                        {pr.title}
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="font-mono text-[10px] text-zinc-500">
                          {pr.hours_open}h
                        </span>
                        <SeverityBadge severity={pr.severity} />
                      </div>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          );
        })}
      </Accordion>
    </div>
  );
}

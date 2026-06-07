import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

interface MetricRow {
  repo: string;
  number: number;
  title: string;
  hours_open: number;
}

interface StandupData {
  status: string;
  username: string;
  metrics_snapshot: {
    developer: string;
    timestamp: string;
    stale_prs: MetricRow[];
    commit_velocity: {
      current_week: number;
      previous_week: number;
      trend: number;
    };
    merge_lag: {
      average_hours: number;
      pr_count: number;
    };
  };
  standup_summary: string;
}

type Params = Promise<{ username: string }>;

async function fetchStandupData(username: string): Promise<StandupData | null> {
  try {
    const res = await fetch(`http://127.0.0.1:8000/users/${username}/standup`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch (error) {
    console.error("Failed to establish backend handshake:", error);
    return null;
  }
}

export default function DashboardPage({ params }: { params: Params }) {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-50 p-6 font-sans">
      {/* Promise resolution wrapper inside async runtime */}
      <DashboardRenderer paramsPromise={params} />
    </main>
  );
}

async function DashboardRenderer({ paramsPromise }: { paramsPromise: Params }) {
  const { username } = await paramsPromise;
  const data = await fetchStandupData(username);

  if (!data) {
    return (
      <div className="flex min-h-[80vh] flex-col items-center justify-center space-y-4">
        <p className="font-mono text-sm text-zinc-400">Failed to pull target synchronization profile.</p>
        <Link href="/" className="text-xs font-mono text-zinc-500 hover:text-zinc-200 underline underline-offset-4">
          ← Return to Entry Node
        </Link>
      </div>
    );
  }

  const { metrics_snapshot, standup_summary } = data;
  const { commit_velocity, merge_lag, stale_prs } = metrics_snapshot;

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header Pipeline Status */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between border-b border-zinc-800 pb-5 gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold font-mono tracking-tight">{username}</h1>
            <Badge variant="outline" className="border-zinc-700 bg-zinc-900 font-mono text-zinc-400">
              Core Developer
            </Badge>
          </div>
          <p className="text-xs font-mono text-zinc-500 mt-1">
            Telemetry Synced At: {new Date(metrics_snapshot.timestamp).toISOString()}
          </p>
        </div>
        <Link href="/" className="text-xs font-mono text-zinc-400 hover:text-zinc-200 self-start md:self-auto border border-zinc-800 px-3 py-1.5 rounded-md bg-zinc-900/40">
          ← Swap Profile
        </Link>
      </div>

      {/* Metrics Performance Matrix Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Metric Node 1: Commit Velocity */}
        <Card className="border-zinc-800 bg-zinc-900/30 backdrop-blur text-zinc-50 shadow-sm">
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-xs font-mono uppercase tracking-wider text-zinc-400">
              Commit Velocity
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <div className="flex items-baseline space-x-2">
              <span className="text-4xl font-bold font-mono tracking-tight">
                {commit_velocity.current_week}
              </span>
              <span className="text-xs font-mono text-zinc-500">pushed (7d)</span>
            </div>
            <div className="mt-2 flex items-center space-x-1.5 text-xs font-mono">
              <span className={commit_velocity.trend >= 0 ? "text-emerald-400" : "text-rose-400"}>
                {commit_velocity.trend >= 0 ? `+${commit_velocity.trend}` : commit_velocity.trend}
              </span>
              <span className="text-zinc-500">vs historical baseline ({commit_velocity.previous_week})</span>
            </div>
          </CardContent>
        </Card>

        {/* Metric Node 2: Merge Lag Profile */}
        <Card className="border-zinc-800 bg-zinc-900/30 backdrop-blur text-zinc-50 shadow-sm">
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-xs font-mono uppercase tracking-wider text-zinc-400">
              Mean Merge Lag
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <div className="flex items-baseline space-x-2">
              <span className="text-4xl font-bold font-mono tracking-tight">
                {merge_lag.average_hours}h
              </span>
              <span className="text-xs font-mono text-zinc-500">cycle time</span>
            </div>
            <div className="mt-2 text-xs font-mono text-zinc-500">
              Aggregated across <span className="text-zinc-300 font-semibold">{merge_lag.pr_count} PRs</span> (last 30d)
            </div>
          </CardContent>
        </Card>

        {/* Metric Node 3: Open Blocker Counts */}
        <Card className="border-zinc-800 bg-zinc-900/30 backdrop-blur text-zinc-50 shadow-sm">
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-xs font-mono uppercase tracking-wider text-zinc-400">
              Active Pipeline Openings
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <div className="flex items-baseline space-x-2">
              <span className={`text-4xl font-bold font-mono tracking-tight ${stale_prs.length > 0 ? 'text-amber-500' : 'text-zinc-50'}`}>
                {stale_prs.length}
              </span>
              <span className="text-xs font-mono text-zinc-500">stale blockages</span>
            </div>
            <div className="mt-2 text-xs font-mono text-zinc-500">
              Pull requests unmerged for &gt; 48 hours
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Primary Split View: Standup Text Panel vs Detailed Stale PR list */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left/Main Column: SDE Engine Standup Synthesizer Block */}
        <Card className="lg:col-span-2 border-zinc-800 bg-zinc-900/20 text-zinc-50 shadow-inner">
          <CardHeader className="border-b border-zinc-800/80 p-4">
            <div className="flex items-center space-x-2">
              <div className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse" />
              <CardTitle className="text-sm font-mono tracking-wide">AI Synthesis Output</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-5 font-mono text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">
            {/* Render the main summary */}
            <p className="mb-4">{standup_summary?.synthesis_summary || "No summary available."}</p>

            {/* Render the Action Items list if it exists */}
            {standup_summary?.action_items && standup_summary.action_items.length > 0 && (
              <div className="mt-4 border-t border-zinc-800 pt-4 text-xs">
                <span className="text-emerald-400 font-bold tracking-wider uppercase mb-2 block">
                  Action Items
                </span>
                <ul className="list-disc pl-5 space-y-2">
                  {standup_summary.action_items.map((item: any, idx: number) => (
                    <li key={idx}>
                      <span className="text-zinc-100 font-semibold">PR #{item.pr_number}</span>: {item.action}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right Column: Direct Stale PR Node Tracking */}
        <Card className="border-zinc-800 bg-zinc-900/10 text-zinc-50">
          <CardHeader className="p-4 pb-3">
            <CardTitle className="text-sm font-mono tracking-wide">Blockage Register</CardTitle>
            <CardDescription className="text-zinc-500 text-xs font-mono">Isolated latency lines</CardDescription>
          </CardHeader>
          <CardContent className="p-4 pt-0 space-y-3">
            {stale_prs.length === 0 ? (
              <div className="text-xs font-mono text-zinc-600 text-center py-6 border border-dashed border-zinc-800 rounded-md">
                No pipeline friction detected. Clean execution.
              </div>
            ) : (
              stale_prs.map((pr, index) => (
                <div key={index} className="p-3 bg-zinc-900/60 border border-zinc-800/80 rounded-md space-y-1.5">
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-mono text-zinc-400 font-bold truncate block max-w-[70%]">
                      {pr.repo}
                    </span>
                    <Badge className="bg-amber-950 text-amber-400 hover:bg-amber-950 border border-amber-800/50 font-mono text-[10px] px-1.5 py-0">
                      {pr.hours_open}h open
                    </Badge>
                  </div>
                  <div className="text-xs font-mono text-zinc-200 font-medium line-clamp-1">
                    #{pr.number} - {pr.title}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
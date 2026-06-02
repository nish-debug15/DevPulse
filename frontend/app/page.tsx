"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  const [username, setUsername] = useState("");
  const router = useRouter();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (username.trim()) {
      router.push(`/dashboard/${username.trim()}`);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-zinc-950 px-4 text-zinc-50">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-zinc-900 via-zinc-950 to-zinc-950 -z-10 opacity-70" />
      
      <Card className="w-full max-w-md border-zinc-800 bg-zinc-900/50 backdrop-blur-md text-zinc-50 shadow-2xl">
        <CardHeader className="space-y-1.5 pb-6">
          <div className="flex items-center justify-center space-x-2 mb-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-mono tracking-widest text-zinc-400 uppercase">System Status: Active</span>
          </div>
          <CardTitle className="text-3xl font-bold tracking-tight text-center font-mono">DevPulse</CardTitle>
          <CardDescription className="text-zinc-400 text-center text-sm">
            AI-driven bottleneck isolation & automated standups.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <input
                type="text"
                placeholder="Enter GitHub Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="flex h-11 w-full rounded-md border border-zinc-800 bg-zinc-950 px-4 py-2 text-sm text-zinc-50 font-mono placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-400 focus:border-zinc-400 transition-colors"
                required
                autoComplete="off"
              />
            </div>
            <Button type="submit" className="w-full h-11 bg-zinc-50 text-zinc-950 font-mono hover:bg-zinc-200 font-semibold tracking-sm transition-all duration-150">
              Analyze Pipeline →
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
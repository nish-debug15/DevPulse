"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const BACKEND_URL = "http://127.0.0.1:8000";

export default function LandingPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-zinc-950 px-4 text-zinc-50">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-zinc-900 via-zinc-950 to-zinc-950 -z-10 opacity-70" />

      <Card className="w-full max-w-md border-zinc-800 bg-zinc-900/50 backdrop-blur-md text-zinc-50 shadow-2xl">
        <CardHeader className="space-y-6 pb-8 pt-6">
          <div className="flex items-center justify-center space-x-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-mono tracking-widest text-zinc-400 uppercase">System Status: Active</span>
          </div>

          <div className="space-y-3">
            <CardTitle className="text-4xl font-bold tracking-tight text-center font-mono">DevPulse</CardTitle>
            <CardDescription className="text-zinc-300 text-center text-sm font-medium leading-relaxed px-4">
              AI-driven bottleneck isolation & automated standups.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <a href={`${BACKEND_URL}/auth/login`} className="block">
            <Button className="w-full h-11 bg-zinc-50 text-zinc-950 font-mono hover:bg-zinc-200 font-semibold tracking-sm transition-all duration-150 cursor-pointer">
              <svg className="mr-2 h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              Sign in with GitHub
            </Button>
          </a>
          <p className="text-center text-[11px] font-mono text-zinc-600">
            Authenticate via GitHub to access your pipeline analytics.
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
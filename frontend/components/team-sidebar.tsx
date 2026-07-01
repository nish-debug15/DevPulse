"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

interface TrackedDeveloper {
  username: string;
  name: string | null;
  github_id: number;
  last_synced_at: string | null;
  added_at: string | null;
}

interface TeamSidebarProps {
  currentViewedUser: string;
}

export function TeamSidebar({ currentViewedUser }: TeamSidebarProps) {
  const router = useRouter();
  const [team, setTeam] = useState<TrackedDeveloper[]>([]);
  const [loggedInUser, setLoggedInUser] = useState<{ username: string } | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [loading, setLoading] = useState(true);
  const [addingError, setAddingError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [authRes, teamRes] = await Promise.all([
        fetch(`${BACKEND_URL}/auth/me`, { credentials: "include" }),
        fetch(`${BACKEND_URL}/team`, { credentials: "include" })
      ]);

      if (authRes.ok) {
        const authData = await authRes.json();
        setLoggedInUser(authData);
      }

      if (teamRes.ok) {
        const teamData = await teamRes.json();
        setTeam(teamData.team);
      }
    } catch (err) {
      console.error("Failed to load sidebar data", err);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUsername.trim()) return;

    setIsSubmitting(true);
    setAddingError("");

    try {
      const res = await fetch(`${BACKEND_URL}/team/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ github_username: newUsername.trim() }),
      });

      const data = await res.json();

      if (res.ok) {
        setNewUsername("");
        setIsAdding(false);
        await fetchData(); // Refresh the list
      } else {
        setAddingError(data.detail || "Failed to add developer");
      }
    } catch (err) {
      setAddingError("Network error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemove = async (username: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!confirm(`Stop tracking ${username}?`)) return;

    try {
      const res = await fetch(`${BACKEND_URL}/team/${username}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (res.ok) {
        if (currentViewedUser === username && loggedInUser) {
          router.push(`/dashboard/${loggedInUser.username}`);
        } else {
          await fetchData();
        }
      }
    } catch (err) {
      console.error("Failed to remove developer", err);
    }
  };

  if (loading) {
    return (
      <div className="w-60 shrink-0 border-r border-zinc-800 bg-zinc-900/30 p-4 flex items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-zinc-500" />
      </div>
    );
  }

  return (
    <div className="w-60 shrink-0 border-r border-zinc-800 bg-zinc-900/30 flex flex-col h-[calc(100vh-3rem)] sticky top-6 rounded-l-xl">
      <div className="p-4 border-b border-zinc-800/80">
        <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-zinc-400 mb-4">Me</h2>
        {loggedInUser && (
          <Link
            href={`/dashboard/${loggedInUser.username}`}
            className={`flex items-center px-3 py-2 rounded-md text-sm font-mono transition-colors ${
              currentViewedUser === loggedInUser.username
                ? "bg-zinc-800/80 text-zinc-50 border-l-2 border-emerald-400"
                : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
            }`}
          >
            {loggedInUser.username}
          </Link>
        )}
      </div>

      <div className="p-4 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-zinc-400">Team</h2>
          <button
            onClick={() => setIsAdding(!isAdding)}
            className="text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        {isAdding && (
          <form onSubmit={handleAdd} className="mb-4 space-y-2 bg-zinc-900/50 p-3 rounded-md border border-zinc-800">
            <Input
              type="text"
              placeholder="GitHub handle..."
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              className="h-8 text-xs font-mono bg-zinc-950 border-zinc-700 placeholder:text-zinc-600"
              autoFocus
            />
            {addingError && <p className="text-[10px] text-rose-400 font-mono">{addingError}</p>}
            <div className="flex space-x-2">
              <Button
                type="submit"
                disabled={isSubmitting}
                className="h-7 px-3 text-xs flex-1 bg-zinc-100 hover:bg-zinc-300 text-zinc-900"
              >
                {isSubmitting ? <Loader2 className="h-3 w-3 animate-spin" /> : "Track"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setIsAdding(false);
                  setAddingError("");
                  setNewUsername("");
                }}
                className="h-7 px-3 text-xs"
              >
                Cancel
              </Button>
            </div>
          </form>
        )}

        <div className="space-y-1">
          {team.length === 0 && !isAdding && (
            <p className="text-xs font-mono text-zinc-600 italic px-2">No developers tracked.</p>
          )}
          {team.map((dev) => (
            <Link
              key={dev.username}
              href={`/dashboard/${dev.username}`}
              className={`group flex items-center justify-between px-3 py-2 rounded-md text-sm font-mono transition-colors ${
                currentViewedUser === dev.username
                  ? "bg-zinc-800/80 text-zinc-50 border-l-2 border-indigo-400"
                  : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200"
              }`}
            >
              <span className="truncate pr-2">{dev.username}</span>
              <button
                onClick={(e) => handleRemove(dev.username, e)}
                className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-rose-400 transition-opacity p-1 -mr-1 rounded-sm"
              >
                <X className="h-3 w-3" />
              </button>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

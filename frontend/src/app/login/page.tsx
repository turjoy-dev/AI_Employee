"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, Lock, Mail, Sparkles } from "lucide-react";

import { BackgroundScene } from "@/components/canvas/BackgroundScene";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuthStore } from "@/store/useAuthStore";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, isLoading, error, hydrate } = useAuthStore();

  const [email, setEmail] = useState("admin@aiemployee.com");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    if (!email.trim() || !password) {
      setLocalError("Please enter both email and password.");
      return;
    }

    await login(email.trim(), password);
    if (useAuthStore.getState().isAuthenticated) {
      router.replace("/dashboard");
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#F7F7F5] px-4 py-12 text-[#1A1A1A]">
      <BackgroundScene />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl border border-[#EAE9E4] bg-white shadow-sm">
            <Sparkles className="h-5 w-5 text-[#5C8A67]" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#1A1A1A]">
            AI Employee Workspace
          </h1>
          <p className="mt-1.5 text-sm text-[#737370]">
            Sign in to review qualified leads, conversations, and insights.
          </p>
        </div>

        <Card className="border-[#EAE9E4] bg-white/90 shadow-[0_12px_40px_-16px_rgba(26,26,26,0.12)] backdrop-blur-md">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">Welcome back</CardTitle>
            <CardDescription>
              Enter your operator credentials to access the dashboard.
            </CardDescription>
          </CardHeader>

          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="email"
                  className="text-xs font-medium text-[#52524E]"
                >
                  Work Email
                </label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9C9C96]" />
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="admin@aiemployee.com"
                    className="pl-9"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="password"
                  className="text-xs font-medium text-[#52524E]"
                >
                  Password
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9C9C96]" />
                  <Input
                    id="password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    className="pl-9"
                  />
                </div>
              </div>

              {(localError || error) && (
                <div className="rounded-lg border border-[#F5C6C2] bg-[#FCECEA] px-3 py-2 text-xs font-medium text-[#B9382C]">
                  {localError || error}
                </div>
              )}

              <Button
                type="submit"
                disabled={isLoading}
                className="mt-2 h-10 w-full rounded-xl bg-[#5C8A67] text-white shadow-sm hover:bg-[#4D7757]"
              >
                {isLoading ? (
                  "Signing in..."
                ) : (
                  <>
                    Sign in to Dashboard
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-xs text-[#9C9C96]">
          Protected by JWT authentication · AI Receptionist &amp; Analyst v1
        </p>
      </motion.div>
    </div>
  );
}

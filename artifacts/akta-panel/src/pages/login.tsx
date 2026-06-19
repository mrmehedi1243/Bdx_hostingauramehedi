import { useState } from "react";
import { useLocation } from "wouter";
import { Terminal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { toast } from "sonner";

export default function Login() {
  const [, setLocation] = useLocation();
  const [accessKey, setAccessKey] = useState("");

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (accessKey === "mehedixaura") {
      localStorage.setItem("adminToken", "mehedixaura");
      toast.success("ACCESS GRANTED");
      setLocation("/dashboard");
    } else {
      toast.error("ACCESS DENIED");
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-background bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(0,255,100,0.1),rgba(255,255,255,0))] font-mono">
      <Card className="w-full max-w-md bg-card border-border rounded-none shadow-[0_0_20px_rgba(0,255,100,0.05)] border border-primary/20">
        <CardHeader className="text-center space-y-4 pb-8">
          <div className="mx-auto bg-primary/10 p-4 w-fit border border-primary/20">
            <Terminal className="h-10 w-10 text-primary" />
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-widest text-foreground">AKTA_PANEL</h1>
            <p className="text-xs text-primary/70 tracking-widest uppercase">System Authentication</p>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-6">
            <div className="space-y-2">
              <label htmlFor="key" className="text-xs tracking-wider text-muted-foreground">ROOT_ACCESS_KEY</label>
              <Input
                id="key"
                type="password"
                placeholder="••••••••••••"
                value={accessKey}
                onChange={(e) => setAccessKey(e.target.value)}
                className="bg-background border-border focus-visible:ring-primary focus-visible:border-primary font-mono rounded-none tracking-widest"
              />
            </div>
            <Button 
              type="submit" 
              className="w-full rounded-none font-bold tracking-widest bg-primary hover:bg-primary/90 text-primary-foreground border border-primary transition-all duration-200"
            >
              INITIALIZE_SESSION
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

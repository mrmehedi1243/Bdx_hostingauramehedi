import { AppLayout } from "@/components/layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BookOpen, Copy, CheckCircle } from "lucide-react";
import { toast } from "sonner";
import { useState } from "react";

function CodeBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    toast.success("COPIED");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="relative group">
      {label && (
        <div className="text-xs text-muted-foreground tracking-widest mb-1.5">{label}</div>
      )}
      <div className="bg-background border border-border p-4 font-mono text-xs leading-relaxed overflow-x-auto">
        <pre className="text-foreground whitespace-pre-wrap break-all">{code}</pre>
      </div>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 text-muted-foreground hover:text-primary transition-colors p-1.5 border border-border bg-card opacity-0 group-hover:opacity-100"
      >
        {copied ? <CheckCircle className="h-3.5 w-3.5 text-primary" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

function MethodBadge({ method }: { method: string }) {
  const colors: Record<string, string> = {
    POST: "border-primary text-primary",
    GET: "border-blue-400 text-blue-400",
    DELETE: "border-destructive text-destructive",
    PATCH: "border-yellow-500 text-yellow-500",
  };
  return (
    <Badge variant="outline" className={`rounded-none font-mono text-xs ${colors[method] ?? "border-border text-muted-foreground"}`}>
      {method}
    </Badge>
  );
}

const baseUrl = window.location.origin;

export default function ApiDocs() {
  return (
    <AppLayout>
      <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-primary">API_DOCS</h1>
          <p className="text-muted-foreground text-sm uppercase tracking-widest">Public API reference for user creation</p>
        </div>

        <Card className="rounded-none border-border bg-card">
          <CardHeader className="border-b border-border/50 pb-4">
            <CardTitle className="text-sm font-normal flex items-center gap-2 tracking-widest text-muted-foreground">
              <BookOpen className="h-4 w-4 text-primary" /> BASE_URL
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            <CodeBlock code={`${baseUrl}/api`} />
          </CardContent>
        </Card>

        <Card className="rounded-none border-border bg-card">
          <CardHeader className="border-b border-border/50 pb-4">
            <div className="flex items-center gap-3">
              <MethodBadge method="POST" />
              <span className="font-mono text-sm text-foreground">/users</span>
            </div>
            <p className="text-xs text-muted-foreground tracking-widest mt-2">Create a new user using a valid API key. User gets 15-day validity.</p>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            <CodeBlock
              label="REQUEST_BODY (application/json)"
              code={`{
  "username": "john_doe",
  "password": "s3cr3t_pass",
  "apiKey": "YOUR_API_KEY_HERE"
}`}
            />
            <CodeBlock
              label="SUCCESS_RESPONSE (201)"
              code={`{
  "id": 1,
  "username": "john_doe",
  "password": "s3cr3t_pass",
  "apiKeyId": 3,
  "apiKey": "YOUR_API_KEY_HERE",
  "status": "active",
  "expiresAt": "2026-07-04T00:00:00.000Z",
  "createdAt": "2026-06-19T00:00:00.000Z"
}`}
            />
            <CodeBlock
              label="ERROR_RESPONSE (400)"
              code={`{ "error": "Invalid or expired API key" }`}
            />
            <CodeBlock
              label="CURL_EXAMPLE"
              code={`curl -X POST ${baseUrl}/api/users \\
  -H "Content-Type: application/json" \\
  -d '{"username":"john","password":"pass123","apiKey":"YOUR_KEY"}'`}
            />
            <CodeBlock
              label="PYTHON_EXAMPLE"
              code={`import requests

res = requests.post("${baseUrl}/api/users", json={
    "username": "john_doe",
    "password": "s3cr3t",
    "apiKey": "YOUR_KEY"
})
print(res.json())`}
            />
          </CardContent>
        </Card>

        <Card className="rounded-none border-border bg-card">
          <CardHeader className="border-b border-border/50 pb-4">
            <div className="flex items-center gap-3">
              <MethodBadge method="GET" />
              <span className="font-mono text-sm text-foreground">/healthz</span>
            </div>
            <p className="text-xs text-muted-foreground tracking-widest mt-2">Check API server health.</p>
          </CardHeader>
          <CardContent className="pt-4">
            <CodeBlock
              label="RESPONSE (200)"
              code={`{ "status": "ok" }`}
            />
          </CardContent>
        </Card>

        <div className="border border-primary/20 bg-primary/5 p-4 font-mono text-xs space-y-2">
          <div className="text-primary tracking-widest">IMPORTANT_NOTES</div>
          <ul className="text-muted-foreground space-y-1 list-none">
            <li>— API keys must be active and within max_users limit to create users</li>
            <li>— Each created user has 15-day validity from creation date</li>
            <li>— Username must be unique across the system</li>
            <li>— Generate API keys from the API_KEYS panel section</li>
          </ul>
        </div>
      </div>
    </AppLayout>
  );
}

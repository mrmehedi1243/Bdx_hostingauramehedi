import { useState } from "react";
import { useListApiKeys, useCreateApiKey, useDeleteApiKey, useRevokeApiKey, getListApiKeysQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { AppLayout } from "@/components/layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Key, Plus, Copy, Trash2, Ban, CheckCircle } from "lucide-react";
import { toast } from "sonner";

function StatusBadge({ status }: { status: string }) {
  const styles = {
    active: "border-primary text-primary shadow-[0_0_8px_rgba(0,255,100,0.25)]",
    expired: "border-destructive text-destructive",
    revoked: "border-yellow-500 text-yellow-500",
  }[status] ?? "border-border text-muted-foreground";
  return (
    <Badge variant="outline" className={`rounded-none font-mono text-xs ${styles}`}>
      {status.toUpperCase()}
    </Badge>
  );
}

export default function ApiKeys() {
  const queryClient = useQueryClient();
  const { data: keys, isLoading } = useListApiKeys();
  const createMutation = useCreateApiKey();
  const deleteMutation = useDeleteApiKey();
  const revokeMutation = useRevokeApiKey();

  const [showCreate, setShowCreate] = useState(false);
  const [label, setLabel] = useState("");
  const [maxUsers, setMaxUsers] = useState("");

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: getListApiKeysQueryKey() });

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(
      { data: { label, maxUsers: maxUsers ? Number(maxUsers) : null } },
      {
        onSuccess: () => {
          toast.success("API_KEY_CREATED");
          setShowCreate(false);
          setLabel("");
          setMaxUsers("");
          invalidate();
        },
        onError: () => toast.error("CREATE_FAILED"),
      }
    );
  };

  const handleDelete = (id: number) => {
    deleteMutation.mutate(
      { id },
      {
        onSuccess: () => { toast.success("KEY_DELETED"); invalidate(); },
        onError: () => toast.error("DELETE_FAILED"),
      }
    );
  };

  const handleRevoke = (id: number) => {
    revokeMutation.mutate(
      { id },
      {
        onSuccess: () => { toast.success("KEY_REVOKED"); invalidate(); },
        onError: () => toast.error("REVOKE_FAILED"),
      }
    );
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    toast.success("COPIED_TO_CLIPBOARD");
  };

  return (
    <AppLayout>
      <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight text-primary">API_KEYS</h1>
            <p className="text-muted-foreground text-sm uppercase tracking-widest">Manage reseller access keys</p>
          </div>
          <Button
            onClick={() => setShowCreate(true)}
            className="rounded-none font-mono tracking-wider border border-primary/40 bg-primary/10 hover:bg-primary/20 text-primary"
          >
            <Plus className="h-4 w-4 mr-2" /> GENERATE_KEY
          </Button>
        </div>

        <Card className="rounded-none border-border bg-card">
          <CardHeader className="border-b border-border/50 pb-4">
            <CardTitle className="text-sm font-normal flex items-center gap-2 tracking-widest text-muted-foreground">
              <Key className="h-4 w-4 text-primary" /> KEY_REGISTRY
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="p-4 space-y-3">
                {[1, 2, 3].map(i => <Skeleton key={i} className="h-12 bg-muted/50 rounded-none" />)}
              </div>
            ) : !keys?.length ? (
              <div className="p-12 text-center text-muted-foreground text-sm font-mono uppercase tracking-widest">
                NO_KEYS_FOUND — GENERATE_FIRST_KEY
              </div>
            ) : (
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow className="hover:bg-transparent border-border/50">
                    <TableHead className="font-mono text-xs text-muted-foreground">ID</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">LABEL</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">KEY</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">STATUS</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">USAGE</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">EXPIRES</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground text-right">ACTIONS</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {keys.map((k) => (
                    <TableRow key={k.id} className="border-border/50 hover:bg-muted/30 transition-colors">
                      <TableCell className="font-mono text-xs text-muted-foreground">#{k.id}</TableCell>
                      <TableCell className="font-mono text-sm">{k.label}</TableCell>
                      <TableCell className="font-mono text-xs">
                        <div className="flex items-center gap-2">
                          <span className="text-primary/80 truncate max-w-[160px]">{k.key}</span>
                          <button onClick={() => copyKey(k.key)} className="text-muted-foreground hover:text-primary transition-colors">
                            <Copy className="h-3 w-3" />
                          </button>
                        </div>
                      </TableCell>
                      <TableCell><StatusBadge status={k.status} /></TableCell>
                      <TableCell className="font-mono text-xs">
                        <span className="text-primary">{k.usageCount}</span>
                        {k.maxUsers != null && <span className="text-muted-foreground">/{k.maxUsers}</span>}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {k.expiresAt ? new Date(k.expiresAt).toLocaleDateString() : "NEVER"}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {k.status === "active" && (
                            <button
                              onClick={() => handleRevoke(k.id)}
                              className="text-yellow-500/70 hover:text-yellow-400 transition-colors p-1"
                              title="Revoke"
                            >
                              <Ban className="h-3.5 w-3.5" />
                            </button>
                          )}
                          <button
                            onClick={() => handleDelete(k.id)}
                            className="text-destructive/70 hover:text-destructive transition-colors p-1"
                            title="Delete"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="rounded-none border-border bg-card font-mono max-w-md">
          <DialogHeader>
            <DialogTitle className="tracking-widest text-primary flex items-center gap-2">
              <CheckCircle className="h-4 w-4" /> GENERATE_NEW_KEY
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <label className="text-xs tracking-wider text-muted-foreground">KEY_LABEL *</label>
              <Input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="e.g. reseller_batch_01"
                required
                className="rounded-none bg-background border-border font-mono text-sm focus-visible:ring-primary"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs tracking-wider text-muted-foreground">MAX_USERS (optional)</label>
              <Input
                type="number"
                value={maxUsers}
                onChange={(e) => setMaxUsers(e.target.value)}
                placeholder="Leave empty for unlimited"
                className="rounded-none bg-background border-border font-mono text-sm focus-visible:ring-primary"
              />
            </div>
            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowCreate(false)}
                className="rounded-none font-mono tracking-wider border-border"
              >
                CANCEL
              </Button>
              <Button
                type="submit"
                disabled={createMutation.isPending}
                className="rounded-none font-mono tracking-wider bg-primary text-primary-foreground hover:bg-primary/90"
              >
                {createMutation.isPending ? "GENERATING..." : "GENERATE"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}

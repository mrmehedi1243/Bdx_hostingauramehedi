import { useListUsers, useDeleteUser, getListUsersQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { AppLayout } from "@/components/layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Users as UsersIcon, Trash2, Copy, Terminal } from "lucide-react";
import { toast } from "sonner";

function StatusBadge({ status }: { status: string }) {
  const styles =
    status === "active"
      ? "border-primary text-primary shadow-[0_0_8px_rgba(0,255,100,0.25)]"
      : "border-destructive text-destructive";
  return (
    <Badge variant="outline" className={`rounded-none font-mono text-xs ${styles}`}>
      {status.toUpperCase()}
    </Badge>
  );
}

export default function Users() {
  const queryClient = useQueryClient();
  const { data: users, isLoading } = useListUsers();
  const deleteMutation = useDeleteUser();

  const handleDelete = (id: number) => {
    deleteMutation.mutate(
      { id },
      {
        onSuccess: () => {
          toast.success("USER_DELETED");
          queryClient.invalidateQueries({ queryKey: getListUsersQueryKey() });
        },
        onError: () => toast.error("DELETE_FAILED"),
      }
    );
  };

  const copy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label}_COPIED`);
  };

  return (
    <AppLayout>
      <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-primary">USERS</h1>
          <p className="text-muted-foreground text-sm uppercase tracking-widest">All registered panel users</p>
        </div>

        <Card className="rounded-none border-primary/20 bg-muted/10">
          <CardContent className="p-4 font-mono text-xs text-muted-foreground space-y-1">
            <div className="flex items-center gap-2 text-primary mb-2">
              <Terminal className="h-3.5 w-3.5" />
              <span className="tracking-widest">USER_CREATION_ENDPOINT</span>
            </div>
            <div className="bg-background/60 border border-border p-3 space-y-1">
              <span className="text-yellow-400">POST</span>
              <span className="text-foreground ml-2">/api/users</span>
            </div>
            <div className="bg-background/60 border border-border p-3 mt-2 text-xs leading-relaxed">
              <div className="text-muted-foreground">{`{ "username": "john", "password": "secret", "apiKey": "YOUR_KEY" }`}</div>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-none border-border bg-card">
          <CardHeader className="border-b border-border/50 pb-4">
            <CardTitle className="text-sm font-normal flex items-center gap-2 tracking-widest text-muted-foreground">
              <UsersIcon className="h-4 w-4 text-primary" /> USER_REGISTRY — {users?.length ?? 0} RECORDS
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="p-4 space-y-3">
                {[1, 2, 3].map(i => <Skeleton key={i} className="h-12 bg-muted/50 rounded-none" />)}
              </div>
            ) : !users?.length ? (
              <div className="p-12 text-center text-muted-foreground text-sm font-mono uppercase tracking-widest">
                NO_USERS_FOUND
              </div>
            ) : (
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow className="hover:bg-transparent border-border/50">
                    <TableHead className="font-mono text-xs text-muted-foreground">ID</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">USERNAME</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">PASSWORD</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">API_KEY</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">STATUS</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">EXPIRES</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">CREATED</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground text-right">DEL</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.id} className="border-border/50 hover:bg-muted/30 transition-colors">
                      <TableCell className="font-mono text-xs text-muted-foreground">#{u.id}</TableCell>
                      <TableCell className="font-mono text-sm">
                        <div className="flex items-center gap-1.5">
                          {u.username}
                          <button onClick={() => copy(u.username, "USERNAME")} className="text-muted-foreground hover:text-primary transition-colors">
                            <Copy className="h-3 w-3" />
                          </button>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <span>••••••••</span>
                          <button onClick={() => copy(u.password, "PASSWORD")} className="hover:text-primary transition-colors">
                            <Copy className="h-3 w-3" />
                          </button>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        <div className="flex items-center gap-1.5">
                          <span className="text-primary/70 truncate max-w-[120px]">{u.apiKey}</span>
                          <button onClick={() => copy(u.apiKey, "API_KEY")} className="text-muted-foreground hover:text-primary transition-colors">
                            <Copy className="h-3 w-3" />
                          </button>
                        </div>
                      </TableCell>
                      <TableCell><StatusBadge status={u.status} /></TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {new Date(u.expiresAt).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {new Date(u.createdAt).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <button
                          onClick={() => handleDelete(u.id)}
                          className="text-destructive/70 hover:text-destructive transition-colors p-1"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}

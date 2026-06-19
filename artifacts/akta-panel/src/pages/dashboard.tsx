import { useGetDashboardStats } from "@workspace/api-client-react";
import { AppLayout } from "@/components/layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, Key, Users, ServerCrash, Clock } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function Dashboard() {
  const { data: stats, isLoading } = useGetDashboardStats({
    query: {
      queryKey: ["getDashboardStats"],
    }
  });

  return (
    <AppLayout>
      <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight text-primary">SYS_OVERVIEW</h1>
          <p className="text-muted-foreground text-sm uppercase tracking-widest">Real-time system telemetry</p>
        </div>

        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32 bg-card border-border rounded-none" />)}
          </div>
        ) : stats ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatCard title="TOTAL_KEYS" value={stats.totalApiKeys} icon={Key} />
            <StatCard title="ACTIVE_KEYS" value={stats.activeApiKeys} icon={Activity} color="text-primary" />
            <StatCard title="TOTAL_USERS" value={stats.totalUsers} icon={Users} />
            <StatCard title="EXPIRED_USERS" value={stats.expiredUsers} icon={ServerCrash} color="text-destructive" />
          </div>
        ) : null}

        <Card className="rounded-none border-border bg-card">
          <CardHeader className="border-b border-border/50 pb-4">
            <CardTitle className="text-lg font-normal flex items-center gap-2 tracking-widest">
              <Clock className="h-4 w-4 text-primary" /> RECENT_USERS
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="p-4 space-y-4">
                {[1, 2, 3].map(i => <Skeleton key={i} className="h-10 bg-muted/50 rounded-none" />)}
              </div>
            ) : stats?.recentUsers?.length ? (
              <Table>
                <TableHeader className="bg-muted/50">
                  <TableRow className="hover:bg-transparent border-border/50">
                    <TableHead className="font-mono text-xs text-muted-foreground">ID</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">USERNAME</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground">API_KEY</TableHead>
                    <TableHead className="font-mono text-xs text-muted-foreground text-right">STATUS</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {stats.recentUsers.map((user) => (
                    <TableRow key={user.id} className="border-border/50 hover:bg-muted/50 transition-colors">
                      <TableCell className="font-mono text-xs text-muted-foreground">#{user.id}</TableCell>
                      <TableCell className="font-mono">{user.username}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground truncate max-w-[150px]">
                        {user.apiKey}
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge 
                          variant="outline" 
                          className={`rounded-none font-mono text-xs ${
                            user.status === "active" 
                              ? "border-primary text-primary shadow-[0_0_10px_rgba(0,255,100,0.2)]" 
                              : "border-destructive text-destructive"
                          }`}
                        >
                          {user.status.toUpperCase()}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="p-8 text-center text-muted-foreground text-sm font-mono uppercase tracking-widest">
                NO_DATA_FOUND
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}

function StatCard({ title, value, icon: Icon, color = "text-foreground" }: { title: string, value: number, icon: any, color?: string }) {
  return (
    <Card className="rounded-none border-border bg-card overflow-hidden group">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 bg-muted/20">
        <CardTitle className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className={`h-4 w-4 ${color}`} />
      </CardHeader>
      <CardContent className="pt-4">
        <div className={`text-4xl font-bold font-mono tracking-tighter ${color}`}>{value}</div>
      </CardContent>
      <div className="h-1 w-full bg-border group-hover:bg-primary/20 transition-colors">
        <div className="h-full bg-primary w-1/3 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </Card>
  );
}

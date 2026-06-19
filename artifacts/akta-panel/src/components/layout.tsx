import { useEffect } from "react";
import { Link, useLocation } from "wouter";
import { Terminal, Key, Users, BookOpen, LogOut } from "lucide-react";
import { Sidebar, SidebarContent, SidebarHeader, SidebarMenu, SidebarMenuItem, SidebarMenuButton, SidebarFooter, SidebarProvider } from "@/components/ui/sidebar";

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [location, setLocation] = useLocation();

  useEffect(() => {
    const token = localStorage.getItem("adminToken");
    if (token !== "mehedixaura") {
      setLocation("/");
    }
  }, [location, setLocation]);

  const handleLogout = () => {
    localStorage.removeItem("adminToken");
    setLocation("/");
  };

  return (
    <SidebarProvider>
      <div className="flex h-screen w-full bg-background overflow-hidden">
        <Sidebar className="border-r border-border bg-sidebar text-sidebar-foreground">
          <SidebarHeader className="p-4 border-b border-border flex items-center gap-2">
            <Terminal className="h-6 w-6 text-primary" />
            <span className="font-mono font-bold tracking-widest text-lg">AKTA<span className="text-primary">_</span></span>
          </SidebarHeader>
          <SidebarContent>
            <SidebarMenu className="mt-4 gap-2">
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={location === "/dashboard"} className="hover:bg-sidebar-accent hover:text-sidebar-accent-foreground rounded-none">
                  <Link href="/dashboard" className="flex items-center gap-3 px-4 py-2 font-mono text-sm">
                    <Terminal className="h-4 w-4" />
                    <span>DASHBOARD</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={location === "/apikeys"} className="hover:bg-sidebar-accent hover:text-sidebar-accent-foreground rounded-none">
                  <Link href="/apikeys" className="flex items-center gap-3 px-4 py-2 font-mono text-sm">
                    <Key className="h-4 w-4" />
                    <span>API_KEYS</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={location === "/users"} className="hover:bg-sidebar-accent hover:text-sidebar-accent-foreground rounded-none">
                  <Link href="/users" className="flex items-center gap-3 px-4 py-2 font-mono text-sm">
                    <Users className="h-4 w-4" />
                    <span>USERS</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={location === "/api-docs"} className="hover:bg-sidebar-accent hover:text-sidebar-accent-foreground rounded-none">
                  <Link href="/api-docs" className="flex items-center gap-3 px-4 py-2 font-mono text-sm">
                    <BookOpen className="h-4 w-4" />
                    <span>API_DOCS</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
          <SidebarFooter className="border-t border-border p-4">
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton onClick={handleLogout} className="hover:bg-sidebar-accent hover:text-sidebar-accent-foreground rounded-none text-muted-foreground w-full">
                  <div className="flex items-center gap-3 px-2 py-2 font-mono text-sm w-full">
                    <LogOut className="h-4 w-4" />
                    <span>LOGOUT</span>
                  </div>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarFooter>
        </Sidebar>
        <main className="flex-1 overflow-y-auto p-6 md:p-10 font-mono">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}

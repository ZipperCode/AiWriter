"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, Map, BarChart3, Home } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Projects", icon: Home },
];

const projectNavItems = (projectId: string) => [
  { href: `/projects/${projectId}`, label: "Overview", icon: BookOpen },
  { href: `/projects/${projectId}/atlas`, label: "Atlas", icon: Map },
  { href: `/projects/${projectId}/dashboard`, label: "Dashboard", icon: BarChart3 },
];

export function Sidebar({ projectId }: { projectId?: string }) {
  const pathname = usePathname();

  const items = projectId
    ? [...navItems, ...projectNavItems(projectId)]
    : navItems;

  return (
    <aside className="w-60 border-r bg-gray-50 p-4 space-y-2">
      <h2 className="text-lg font-bold mb-4">AiWriter</h2>
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-md text-sm",
            pathname === item.href
              ? "bg-blue-600 text-white"
              : "hover:bg-gray-200"
          )}
        >
          <item.icon className="h-4 w-4" />
          {item.label}
        </Link>
      ))}
    </aside>
  );
}

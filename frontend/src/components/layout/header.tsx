"use client";

import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAppStore } from "@/lib/store";

export function Header() {
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);

  return (
    <header className="h-14 border-b flex items-center px-4 gap-4">
      <Button variant="ghost" size="icon" onClick={toggleSidebar}>
        <Menu className="h-5 w-5" />
      </Button>
      <h1 className="text-sm font-semibold">AiWriter Studio</h1>
    </header>
  );
}

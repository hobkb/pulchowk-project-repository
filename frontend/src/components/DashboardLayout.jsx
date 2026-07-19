import { useState } from "react";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";

export default function DashboardLayout({ children }) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const toggleSidebar = () => {
    setIsCollapsed((prev) => !prev);
  };

  return (
    <div className="min-h-screen flex flex-col bg-surface-canvas text-text-primary">
      {/* Sticky top Navbar */}
      <Navbar onToggleSidebar={toggleSidebar} />

      {/* Main container with Sidebar and Main content area */}
      <div className="flex-1 flex overflow-hidden min-h-[calc(100vh-64px)]">
        <Sidebar isCollapsed={isCollapsed} />

        {/* Main scrollable view */}
        <main className="flex-1 min-h-0 overflow-y-auto bg-surface-canvas">
          <div className="max-w-[1440px] mx-auto w-full px-6 py-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
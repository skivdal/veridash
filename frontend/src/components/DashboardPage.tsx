"use client";

import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";
import CasesSection from "@/components/CasesSection";

const caseIds = ["ID261", "ID113", "ID64", "ID241"]; // Replace with dynamic list LATER, just a dummy for now

export default function DashboardPage() {
  return (
    <div className="flex flex-col min-h-screen">
      <Topbar />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar />

        <main className="flex-1 p-6 overflow-auto bg-[#f6f6f7]">
          <h1 className="text-2xl font-bold mb-6">Welcome to VeriDash!</h1>

          <CasesSection title="Recent Cases" caseIds={caseIds} />
          <CasesSection title="All Cases" caseIds={caseIds} />
        </main>
      </div>
    </div>
  );
}

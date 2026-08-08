// components/Topbar.tsx
"use client";

import { FaBell, FaShareAlt } from "react-icons/fa";
import { IoIosAdd } from "react-icons/io";

export default function Topbar({ currentCaseId }: { currentCaseId?: string }) {
  return (
    <header className="w-full h-16 shadow-md bg-white border-b flex items-center justify-between px-6 sticky top-0 z-20">
      {/* Left: Logo + divider + Case ID */}
      <div className="flex items-center gap-3">
        <div className="text-xl font-bold flex items-center gap-2">
          <img src="/temp_veri_logo.png" alt="Logo" className="w-7 h-7" />
          <span className="text-lg font-semibold tracking-tight">VeriDash</span>
        </div>

        {currentCaseId && (
          <>
            {/* Divider */}
            <div className="h-6 w-px bg-gray-300 shadow-sm" />

            {/* Case ID pill */}
            <span
              className="inline-flex items-center rounded-md px-2.5 py-1 text-sm
                         bg-blue-100 text-blue-700 whitespace-nowrap"
              title={`Case ${currentCaseId}`}
            >
              {currentCaseId}
            </span>
          </>
        )}
      </div>

      {/* Right-side buttons */}
      <div className="flex items-center gap-4">
        <button className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center gap-2 text-sm">
          <IoIosAdd className="text-lg" /> New Case
        </button>
        <button className="border border-gray-300 px-4 py-2 rounded-md text-sm flex items-center gap-2 hover:bg-gray-50">
          <FaShareAlt className="text-sm" /> Share
        </button>
        <FaBell className="text-gray-600 text-lg cursor-pointer ml-2" />
      </div>
    </header>
  );
}

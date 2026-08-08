// components/PrimaryTopbar.tsx
"use client";
import { FaPlus } from "react-icons/fa";

export default function PrimaryTopbar({ activeCaseId }: { activeCaseId: string }) {
  return (
    <div className="flex items-center justify-between w-full h-12 md:h-14 px-4 md:px-6 bg-white border-b text-sm shadow-md">
      {/* Left: Logo and name */}
      <div className="flex items-center gap-2 font-semibold text-gray-800">
        <img src="/temp_veri_logo.png" alt="VeriDash Logo" className="w-5 h-5" />
        <span className="text-base">VeriDash</span>
      </div>

      {/* Right: Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto">
        {/* Hardcoded tabs for now */}
        <div className="bg-blue-100 text-blue-700 px-2 py-1 rounded-md whitespace-nowrap">
          {activeCaseId}
        </div>
        <button className="text-gray-500 hover:text-black shrink-0">
          <FaPlus />
        </button>
      </div>
    </div>
  );
}

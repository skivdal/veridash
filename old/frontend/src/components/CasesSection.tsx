"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FiChevronRight } from "react-icons/fi";

export default function CasesSection({
  title,
  caseIds,
}: {
  title: string;
  caseIds: string[];
}) {
  const [isOpen, setIsOpen] = useState(true);
  const router = useRouter();

  return (
    <div className="mb-8">
      {/* Section Header */}
      <div
        className="flex items-center justify-between cursor-pointer mb-4"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-2">
          <FiChevronRight
            className={`text-xl transition-transform duration-300 ${
              isOpen ? "rotate-90" : "rotate-0"
            }`}
          />
          <h2 className="text-lg font-semibold">{title}</h2>
        </div>
      </div>

      {/* Cards Grid */}
      {isOpen && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {caseIds.map((id) => (
            <div
              key={id}
              onClick={() => router.push(`/dashboard/case/${id}`)}
              className="cursor-pointer bg-white border border-gray-200 shadow-sm rounded-xl p-4 hover:shadow-md transition"
            >
              <p className="text-sm text-gray-500 mb-1">Case ID:</p>
              <p className="font-medium text-gray-800">{id}</p>
              <p className="text-xs text-gray-400 mt-2">Click to view details</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

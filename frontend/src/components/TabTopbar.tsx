// components/TabTopbar.tsx
"use client";

type Props = {
  currentCaseId: string;
  activeModule: string;
  onChangeModule: (id: string) => void;
};

const tabs = [
  { id: "video",      label: "Overview" },      // your Source card
  { id: "map",        label: "Geolocation" },   // Map module
  { id: "notepad",    label: "Notes" },         // placeholder/real notes
  { id: "stitching",  label: "Stitching" },     // placeholder/real
];

export default function TabTopbar({ activeModule, onChangeModule }: Props) {
  return (
    <div className="w-full border-b bg-white">
      <div className="flex items-center h-12 px-4 gap-4 overflow-x-auto">

        {/* Tabs */}
        <div className="flex items-center gap-1 ml-2">
            {tabs.map((t, idx) => {
                const active = t.id === activeModule;
                return (
                <div key={t.id} className="flex items-center">
                    {/* Tab button */}
                    <button
                    onClick={() => onChangeModule(t.id)}
                    className={`relative inline-flex items-center rounded-md px-3 py-1.5 text-sm font-medium
                                ${active ? "text-blue-700" : "text-gray-700 hover:bg-gray-100"}`}
                    >
                    {t.label}
                    {active && (
                        <span className="absolute -bottom-[11px] left-0 right-0 h-[2px] bg-blue-600" />
                    )}
                    </button>

                    {/* Divider - only show if NOT last tab */}
                    {idx < tabs.length - 1 && (
                    <div className="h-6 w-px bg-gray-300 shadow-sm mx-2" />
                    )}
                </div>
                );
            })}
            </div>


        <div className="ml-auto" />
      </div>
    </div>
  );
}

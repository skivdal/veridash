"use client";

import { FaHome, FaTrash, FaCog, FaUser, FaShareAlt } from "react-icons/fa";
import { BsFileEarmarkTextFill } from "react-icons/bs";

export default function Sidebar() {
  return (
    <aside className="min-w-[14rem] sm:min-w-[16rem] lg:min-w-[18rem] flex-shrink-0 bg-white border-r min-h-screen px-4 py-6 flex flex-col justify-between">
      <div className="flex flex-col">
        {/* Profile Placeholder */}
        <div className="flex items-center gap-3 mb-6 px-2">
          <div className="flex-shrink-0 w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center text-lg">
            👤
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-gray-800 truncate">
              First Lastname
            </p>
            <p className="text-xs text-gray-500 truncate">
              fakey.fake@email.com
            </p>
          </div>
        </div>

        <hr className="border-gray-200 mb-4" />

        {/* Navigation */}
        <nav className="flex flex-col gap-2 text-sm">
          <NavItem icon={<FaHome />} label="Home" active />
          <NavItem icon={<FaUser />} label="Created By Me" />
          <NavItem icon={<FaShareAlt />} label="Shared With Me" />
          <NavItem icon={<FaTrash />} label="Trash" />
          <NavItem icon={<FaCog />} label="Settings" />
        </nav>

        <hr className="border-gray-200 mt-6 mb-4" />

        {/* Starred Section */}
        <div>
          <p className="text-xs font-semibold text-gray-500 mb-2 px-2">
            Starred:
          </p>
          <div className="flex flex-col gap-1">
            <StarredItem id="ID261" />
            <StarredItem id="ID113" />
            <StarredItem id="ID241" />
          </div>
        </div>
      </div>
    </aside>
  );
}

function NavItem({
  icon,
  label,
  active,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
}) {
  return (
    <div
      className={`flex items-center w-full gap-3 px-3 py-2 rounded-md cursor-pointer transition ${
        active ? "bg-gray-100 font-semibold text-gray-900" : "hover:bg-gray-50 text-gray-700"
      }`}
    >
      <span className="text-lg">{icon}</span>
      <span className="truncate">{label}</span>
    </div>
  );
}

function StarredItem({ id }: { id: string }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1 text-sm text-gray-700 hover:bg-gray-100 rounded cursor-pointer">
      <BsFileEarmarkTextFill className="text-gray-400" />
      <span className="truncate">{id}</span>
    </div>
  );
}

"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect } from "react";


export default function Home() {
  const router = useRouter();

  useEffect(() => {
  router.prefetch("/dashboard");
}, []);


  return (
    <main className="relative flex items-center justify-center min-h-screen bg-white px-4">
      <div className="w-full max-w-2xl text-center flex flex-col items-center">
        {/* Heading */}
        <h2 className="welcome-text">Welcome to</h2>


        {/* Logo and tagline */}

        <div className="relative flex flex-col items-center mb-1">
          <h1 className="text-5xl sm:text-6xl font-bold flex items-center gap-1">
              <img src="/temp_veri_logo.png" alt="Logo" width={90} height={90} />
              <span className="text-black">eriDash</span>
          </h1>
  
          <p className="desc">
            Your Verification Command Center
          </p>
        </div>


        {/* Subtitle */}
        <p className="text-gray-500 italic mb-10 subtitle-shift">
            The Prototype
            </p>


        {/* key control instructions 
        <div className="flex flex-col gap-4 text-left mb-10 w-full max-w-md">
          <Instruction keyLabel="Z" text="To resize the prototype window" />
          <Instruction keyLabel="R" text="To restart the flow" />
          <Instruction keyLabel="← / →" text="To skip frames" />
        </div>
        */}
        
        {/* begin Button */}
        <button
          onClick={() => router.push("/dashboard")}
          className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 rounded-md text-lg transition w-full max-w-xs"
        >
          Begin
        </button>
        
        <div className="mt-10">
          <p className="text-gray-400 text-left mb-5">
            The development of VeriDash back-end, specifically the job scheduler, database design, file transfer, and modules for keyframes, stitching, transcription, metadata, and map, is funded by European Union under Action 101158604 — NORDIS, funded through the Digital Europe Programme (DIGITAL) under the DIGITAL-2023-DEPLOY-04-EDMO-HUBS call (Digital SME Support Actions), managed by the European Health and Digital Executive Agency (HaDEA).
          </p>
          
          <Image src="/nordis-logo.png" alt="NORDIS logo" width={363} height={72} className="inline mr-5"></Image>
          <Image src="/funded-by-eu.jpeg" alt="NORDIS logo" width={88} height={88} className="inline"></Image>
        </div>
        
      </div>
    </main>
  );
}

function Instruction({ keyLabel, text }: { keyLabel: string; text: string }) {
  return (
    <div className="flex items-center gap-4">
      <span className="px-3 py-1 border border-gray-400 rounded bg-gray-100 font-mono text-sm sm:text-base">
        {keyLabel}
      </span>
      <span className="text-sm sm:text-base">{text}</span>
    </div>
  );
}

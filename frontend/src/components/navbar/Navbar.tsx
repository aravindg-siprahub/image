"use client";

import { useState } from "react";

interface NavbarProps {
  onGetStarted: () => void;
}

export default function Navbar({ onGetStarted }: NavbarProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="w-full bg-white/90 backdrop-blur-xl sticky top-0 z-50 border-b border-slate-100/80">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between gap-8">

        {/* Logo */}
        <a href="#" className="flex items-center gap-2 shrink-0">
          <div className="w-8 h-8 rounded-xl bg-[#FF6B2C] flex items-center justify-center shadow-sm">
            <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M5 8 Q5 5 8 5 L16 5 Q19 5 19 8 L19 16 Q19 19 16 19 L8 19 Q5 19 5 16 Z" />
            </svg>
          </div>
          <span className="font-bold text-[17px] tracking-tight text-slate-900">LensAI</span>
        </a>

        {/* Center Links – desktop only */}
        <div className="hidden md:flex items-center gap-7 text-[14px] font-medium text-slate-500">
          {["How it works", "Features", "Pricing", "Blog"].map((link) => (
            <a key={link} href="#" className="hover:text-slate-900 transition-colors duration-150">{link}</a>
          ))}
        </div>

        {/* Right */}
        <div className="flex items-center gap-3 shrink-0">
          <a href="#" className="hidden md:block text-[14px] font-medium text-slate-600 hover:text-slate-900 transition-colors">
            Sign in
          </a>
        </div>

      </div>
    </nav>
  );
}

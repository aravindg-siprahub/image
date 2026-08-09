export default function HowItWorks() {
  const steps = [
    {
      num: "1",
      title: "Upload Photos",
      desc: "Drop 10–100+ photos from your device.",
      accent: "text-[#FF6B2C] bg-orange-50 border-orange-100",
    },
    {
      num: "2",
      title: "AI Analyzes",
      desc: "We score quality, sharpness, lighting & composition.",
      accent: "text-violet-600 bg-violet-50 border-violet-100",
    },
    {
      num: "3",
      title: "Get Best Photos",
      desc: "Review your AI-curated top picks instantly.",
      accent: "text-emerald-600 bg-emerald-50 border-emerald-100",
    },
  ];

  return (
    <section className="w-full max-w-6xl mx-auto px-6 py-10">

      {/* Section label */}
      <div className="flex items-center justify-center gap-3 mb-8">
        <div className="h-px flex-1 bg-slate-200/80" />
        <span className="text-sm font-semibold tracking-widest text-slate-400 uppercase">How LensAI works</span>
        <div className="h-px flex-1 bg-slate-200/80" />
      </div>

      {/* Steps card */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-slate-100">
          {steps.map((step, i) => (
            <div key={i} className="flex items-start gap-4 px-5 sm:px-8 py-6 sm:py-8 group">
              {/* Number circle */}
              <div className={`w-10 h-10 rounded-xl border flex items-center justify-center text-base font-black shrink-0 transition-transform group-hover:scale-105 ${step.accent}`}>
                {step.num}
              </div>
              <div>
                <h3 className="font-bold text-[15px] text-slate-900 mb-1">{step.title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

    </section>
  );
}

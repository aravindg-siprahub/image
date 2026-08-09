"use client";

const DEMO_CARDS = [
  {
    img: "/demo/demo-1.jpg",
    rank: 1,
    score: 96,
    label: "Excellent",
    tags: ["Sharp", "Well Exposed", "Great Composition"],
  },
  {
    img: "/demo/demo-2.jpg",
    rank: 2,
    score: 93,
    label: "Excellent",
    tags: ["Great Lighting", "Nice Expression"],
  },
  {
    img: "/demo/demo-3.jpg",
    rank: 3,
    score: 91,
    label: "Excellent",
    tags: ["Sharp", "Great Composition"],
  },
  {
    img: "/demo/demo-4.jpg",
    rank: 4,
    score: 89,
    label: "Very Good",
    tags: ["Nice Lighting", "Good Composition"],
  },
  {
    img: "/demo/demo-5.jpg",
    rank: 5,
    score: 87,
    label: "Very Good",
    tags: ["Sharp", "Well Exposed"],
  },
];

function scoreColor(score: number) {
  if (score >= 92) return "bg-emerald-500";
  if (score >= 85) return "bg-green-500";
  return "bg-yellow-500";
}

export default function DemoGallery() {
  return (
    <section className="w-full max-w-6xl mx-auto px-6 pb-20">

      {/* Section header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">AI-Selected Photos</h2>
          <p className="text-sm text-slate-500 mt-0.5">Ranked by quality score — highest first</p>
        </div>
      </div>

      {/* Cards grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {DEMO_CARDS.map((card) => (
          <div
            key={card.rank}
            className="group relative rounded-2xl overflow-hidden bg-slate-100 shadow-sm hover:shadow-lg transition-all duration-300 cursor-default"
          >
            {/* Image */}
            <div className="aspect-[3/4] relative overflow-hidden">
              <img
                src={card.img}
                alt={`Top pick #${card.rank}`}
                loading="lazy"
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
              />
              {/* Dark gradient overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />

              {/* Rank top-left */}
              <div className="absolute top-2.5 left-2.5 bg-[#FF6B2C] text-white text-[11px] font-bold px-2 py-0.5 rounded-md shadow">
                #{card.rank}
              </div>

              {/* Score top-right */}
              <div className={`absolute top-2.5 right-2.5 ${scoreColor(card.score)} text-white rounded-lg overflow-hidden shadow text-center min-w-[44px]`}>
                <div className="text-[16px] font-black leading-none px-2 pt-1.5 pb-0.5">{card.score}</div>
                <div className="text-[9px] font-semibold uppercase tracking-wider bg-black/20 px-1 py-0.5">{card.label}</div>
              </div>

              {/* Tags overlaid at bottom */}
              <div className="absolute bottom-0 left-0 right-0 p-3 flex flex-wrap gap-1">
                {card.tags.map((tag) => (
                  <span
                    key={tag}
                    className="bg-white/15 backdrop-blur-sm text-white text-[10px] font-medium px-2 py-0.5 rounded-md border border-white/20"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

    </section>
  );
}


import React from 'react';
import Process from './Process';
import ServiceAreas from './ServiceAreas';
import FinalCTA from './FinalCTA';



const BlogPost2: React.FC = () => {
  const bgImage = "/media/6976c78bc1fa0c9f59a78f69.webp";

  return (
    <div className="flex flex-col">
      {/* 1. Hero Section */}
      <section className="relative min-h-[600px] flex items-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={bgImage} alt="Water Damage background" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/40"></div>
        </div>
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 relative z-10 w-full text-center text-white py-20">
          <div className="inline-block bg-black px-4 py-2 mb-6 shadow-xl">
            <span className="text-xs font-black uppercase tracking-[0.2em]">BLOG</span>
          </div>
          <h1 className="text-4xl md:text-7xl font-black uppercase mb-8 leading-[1.1] tracking-tighter drop-shadow-2xl max-w-5xl mx-auto">
            Common Causes of Water Damage and How to Prevent Them
          </h1>
          <div className="flex flex-col items-center gap-2 mt-12 animate-bounce">
            <div className="w-1 h-12 bg-white opacity-40"></div>
            <div className="w-4 h-4 border-r-4 border-b-4 border-white rotate-45 opacity-60"></div>
            <div className="w-4 h-4 border-r-4 border-b-4 border-white rotate-45 opacity-40"></div>
          </div>
        </div>
      </section>

      {/* 2. Blog Body Content */}
      <section className="bg-white py-24">
        <div className="max-w-[1000px] mx-auto px-6 sm:px-12">
          <div className="space-y-12 text-gray-800">
            
            <div className="space-y-4">
              <h2 className="text-2xl font-black text-navy uppercase tracking-tight">
                Introduction
              </h2>
              <p className="text-lg leading-relaxed opacity-90">
                Water damage often starts with small problems that seem harmless at first. A tiny leak, a worn hose, or a clogged gutter can slowly soak materials and cause big repairs later. When you know the common causes, you can spot warning signs early and take action. Simple maintenance can prevent many water damage events in homes and businesses. This article breaks down the most common causes and easy ways to lower your risk. If water damage does happen, ProBrite Gen can help remove water and dry the space properly.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Cause 1: Leaking or Broken Pipes
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Pipes can leak for many reasons, including age, rust, and pressure changes. In cold weather, pipes can freeze and crack, which can lead to a sudden burst when they thaw. Some leaks are slow and hide behind walls, under sinks, or in crawl spaces for a long time. Look for water stains, peeling paint, damp smells, or a higher water bill than normal. Fixing a small leak early can prevent damage to drywall, flooring, and cabinets. Regular checks and quick repairs are one of the best ways to prevent water damage.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Cause 2: Appliance Leaks and Hose Failures
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Appliances like washers, dishwashers, and refrigerators use hoses and fittings that can wear out. A hose can crack, loosen, or pop off, and water can spread fast across floors. Water heaters can also leak from valves or tanks, especially as they get older. Check hoses for bulges, cracks, or rust, and replace them if they look worn. Do not push appliances tight against the wall if it bends hoses or pinches lines. A few minutes of inspection can prevent a major leak later.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Cause 3: Roof Leaks and Clogged Gutters
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                A roof leak can start small and grow over time as water enters during storms. Missing shingles, damaged flashing, or old seals around vents can let water inside. Clogged gutters can overflow and push water toward the roofline and walls. Over time, this moisture can damage insulation, ceilings, and framing. Clean gutters regularly and look for loose shingles or wet spots in the attic. Early roof maintenance is cheaper than repairing water damage inside the home.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Cause 4: Poor Drainage and Foundation Seepage
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Water needs a path away from your home, and poor drainage can push water toward the foundation. If the ground slopes toward the house, rain can pool near walls and seep into basements or crawl spaces. Cracks in the foundation or gaps around doors can allow water inside during heavy storms. Downspouts should point away from the house to move water to a safer area. Adding soil, drains, or simple grading can help direct water away from the structure. Good drainage lowers the chance of flooding and moisture problems.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Cause 5: Prevention Tips That Actually Help
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Prevention is about small habits done consistently. Check under sinks, behind toilets, and around appliances for dampness at least once a month. Replace old supply lines and hoses before they fail, especially on washers and water heaters. Keep gutters clear and make sure downspouts move water away from the home. If you notice stains, odors, or soft spots, address them early instead of waiting. These steps lower risk, and if damage happens anyway, ProBrite Gen can help restore the space.
              </p>
            </div>

            <div className="space-y-4">
              <h2 className="text-2xl font-black text-navy uppercase tracking-tight">
                Conclusion
              </h2>
              <p className="text-lg leading-relaxed opacity-90">
                Most water damage starts small, but it can become expensive if it is ignored. Knowing the causes helps you catch problems early and protect your home. Regular checks of pipes, appliances, roofs, and drainage can prevent many issues. When water damage happens, fast action is still the key to better results. ProBrite Gen can remove water, dry hidden moisture, and help prepare your property for repairs. A little prevention and a quick response can save a lot of trouble.
              </p>
            </div>

          </div>
        </div>
      </section>
      <Process />
      <div className="bg-navy border-t border-white border-opacity-10 py-1"></div>
      <ServiceAreas />
      <FinalCTA />
    </div>
  );
};

export default BlogPost2;

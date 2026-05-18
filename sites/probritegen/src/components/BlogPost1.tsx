
import React from 'react';
import Process from './Process';
import ServiceAreas from './ServiceAreas';
import FinalCTA from './FinalCTA';



const BlogPost1: React.FC = () => {
  const bgImage = "/media/6976c78bc1fa0c9f59a78f69.png";

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
            What to Do Immediately After Water Damage in Your Home
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
                Water damage can happen fast, and it can get worse if you wait. Water can soak into floors, walls, and cabinets, and it can spread into other rooms. The sooner you act, the more you can protect your home and your belongings. Even if the water looks small, hidden moisture can stay behind and cause problems later. This guide walks you through simple steps you can take right away to lower damage and stress. If you are not sure what to do, these steps will help you stay safe and make smart choices.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Step 1: Make Sure the Area Is Safe
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Before you touch anything, take a moment to check for danger. Water on tile, wood, or stairs can make you slip, so move slowly and watch your footing. If water is near outlets, lights, or appliances, do not step into it until power is off. Only turn off electricity if you can reach the panel safely and your hands are dry. Also look for sagging ceilings, soft floors, or loose drywall that could fall. If the area looks unsafe, stay out and call a professional for help.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Step 2: Stop the Source of the Water
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Stopping the water is one of the best ways to limit damage. If a pipe is leaking, shut off the main water valve or the valve for that fixture. If an appliance is leaking, turn it off and stop the water supply line if possible. For rain or flooding, use towels or barriers to keep water from moving into other rooms. Do not ignore a slow drip, because it can soak materials over time and cause swelling or rot. Once the source is stopped, you can focus on cleanup and drying.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Step 3: Remove Standing Water
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Standing water should be removed as soon as you can. Water sitting on floors can soak in and damage wood, carpet, and padding. It can also reach baseboards and drywall and cause stains and warping. Small puddles can be picked up with towels, a wet vacuum, or a mop, but deep water needs stronger tools. Professional teams like ProBrite Gen use pumps and extractors to remove water faster and more completely. Fast removal helps lower the chance of mold and helps the drying step work better.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Step 4: Start Drying the Space
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Drying is not just about air; it is about removing moisture trapped in materials. Open windows if the weather is dry, and use fans to move air across wet surfaces. Place dehumidifiers in the area to pull moisture out of the air and speed up drying. Lift rugs and move furniture when you can, because moisture can stay under heavy items. Hidden water can sit behind walls or under floors, so the space may feel dry even when it is not. ProBrite Gen uses commercial drying equipment and moisture checks to confirm areas are truly dry.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Step 5: Protect Items and Document Damage
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                After the area is safe, protect your important items. Move dry belongings away from the wet zone and place foil or blocks under furniture legs to prevent staining. Take clear photos and short videos of affected rooms, floors, walls, and items before you throw things away. Write down what happened and when you found the water, because details help later. Keep damaged items that may need to be inspected, unless they are a health risk. Good records make the next steps smoother, especially if repairs or claims are involved.
              </p>
            </div>

            <div className="space-y-4">
              <h2 className="text-2xl font-black text-navy uppercase tracking-tight">
                Conclusion
              </h2>
              <p className="text-lg leading-relaxed opacity-90">
                Water damage does not fix itself, and waiting can make the problem bigger. Quick action helps protect your home, lowers repair costs, and reduces the risk of mold. Start with safety, stop the source, remove water, and begin drying right away. If the damage is more than a small spill, professional equipment can make a huge difference. ProBrite Gen can help remove water, dry hidden moisture, and prepare the space for repairs or normal use. The sooner you respond, the better your home can recover.
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

export default BlogPost1;

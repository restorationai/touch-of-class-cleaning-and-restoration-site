
import React from 'react';
import Process from './Process';
import ServiceAreas from './ServiceAreas';
import FinalCTA from './FinalCTA';



const BlogPost6: React.FC = () => {
  const bgImage = "/media/6976c78bc1fa0c9f59a78f69.webp";

  return (
    <div className="flex flex-col">
      {/* 1. Hero Section */}
      <section className="relative min-h-[600px] flex items-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={bgImage} alt="Mold Remediation background" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/40"></div>
        </div>
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 relative z-10 w-full text-center text-white py-20">
          <div className="inline-block bg-black px-4 py-2 mb-6 shadow-xl">
            <span className="text-xs font-black uppercase tracking-[0.2em]">BLOG</span>
          </div>
          <h1 className="text-4xl md:text-7xl font-black uppercase mb-8 leading-[1.1] tracking-tighter drop-shadow-2xl max-w-5xl mx-auto">
            Signs You May Need Professional Mold Remediation
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
                Mold is not always easy to detect, but there are signs that may point to a problem. Recognizing these signs early can help prevent further damage to a property. Mold problems can get worse if they are ignored, especially when moisture keeps feeding the growth. Knowing the warning signs helps you decide when it is time to get professional help. This post covers common signs of mold and explains why remediation may be needed. If you see these signs, acting early can protect your home and reduce future repairs.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Visible Mold Growth
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Visible mold can look like dark spots, fuzzy patches, or stains on walls, ceilings, or floors. It may appear black, green, brown, or even white, depending on the surface and moisture level. Many people wipe the surface and think the problem is gone, but the growth can extend deeper inside materials. If mold is visible, it may also be growing behind drywall or under flooring where you cannot see it. Mold can spread to nearby areas when disturbed, especially if the moisture source is still active. Professional remediation helps remove mold safely and reduces the chance of it spreading further.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Musty or Persistent Odors
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                A strong or musty smell is a common sign of mold, even when you cannot see any spots. Odors often get stronger in damp areas like basements, bathrooms, laundry rooms, or under sinks. Some smells come and go, but they can return when humidity rises or after rain. Air fresheners may cover the odor for a short time, but they do not remove the source. If the smell keeps coming back, it may mean mold is growing behind walls, under floors, or inside cabinets. A professional inspection can help locate the source and confirm what needs to be cleaned.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Past Water Damage or Leaks
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Past water damage is one of the biggest clues that mold may be growing somewhere in the home. Even if the water looked like it dried, moisture can stay trapped behind baseboards, under floors, or inside walls. A slow drip under a sink or a leak around a toilet can feed mold for weeks before anyone notices. Some repairs cover the surface but do not fully dry the materials underneath, which allows mold to keep growing. If you have had a flood, a burst pipe, or repeated leaks, it is smart to watch the area closely for changes. An inspection can help find hidden damp spots and reduce the chance that mold keeps spreading.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Changes in Indoor Comfort
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Mold and moisture problems can change how a home feels and smells day to day. Rooms may feel damp, clammy, or stuffy, especially when doors stay closed or airflow is limited. You might notice more condensation on windows or a damp feeling on walls and floors. Some people also notice irritation or discomfort when spending time in a moldy area, even if the mold is hidden. These comfort changes are often signs that moisture is still present and needs to be addressed. Professional remediation helps restore a cleaner, drier space and can improve overall comfort.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                When to Contact ProBrite Gen
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                If you see mold, smell musty odors, or had water damage that was not fully dried, it is smart to call for help. ProBrite Gen can inspect affected areas, look for moisture sources, and explain the next steps clearly. Remediation often includes containment to prevent spread, removal of impacted materials, and cleanup of affected surfaces. Moisture control is also important so the problem does not return after cleanup. Professional work helps protect your property and reduces the chance of repeated mold issues. Getting help early often makes the process easier and limits damage.
              </p>
            </div>

            <div className="space-y-4">
              <h2 className="text-2xl font-black text-navy uppercase tracking-tight">
                Conclusion
              </h2>
              <p className="text-lg leading-relaxed opacity-90">
                Mold problems can start small, but they can spread when moisture remains in a home. Visible growth, musty odors, and a history of leaks are strong warning signs. Changes in indoor comfort can also point to hidden moisture and mold. Professional inspection helps confirm the problem and prevents guesswork. ProBrite Gen can help remove mold safely, control moisture, and restore the area with clear steps. Early action protects your property and helps you feel confident in your indoor space again.
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

export default BlogPost6;

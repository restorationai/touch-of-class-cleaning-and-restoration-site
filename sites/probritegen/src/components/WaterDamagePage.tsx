import { openChatWidget } from '../store';

import React from 'react';
import { ArrowRight, Star, Users, FileCheck, Settings, Search, HandCoins, MapPin } from 'lucide-react';



const WaterDamagePage: React.FC = () => {
  const bgImage = "/media/6976c78bc1fa0c9f59a78f69.png";
  
  const steps = [
    { icon: <Users size={45} />, label: "Free Consultation" },
    { icon: <FileCheck size={45} />, label: "Inspection & Assessment" },
    { icon: <Settings size={45} />, label: "Water Removal & Drying" },
    { icon: <Search size={45} />, label: "Final Inspection" },
    { icon: <HandCoins size={45} />, label: "Completion" },
  ];

  const areas = [
    "Keasbey, NJ"
  ];

  return (
    <div className="flex flex-col">
      {/* 1. Hero Section */}
      <section className="relative min-h-[600px] flex items-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={bgImage} alt="Water Damage background" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/40"></div>
        </div>
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 relative z-10 w-full text-center text-white py-20">
          <h1 className="text-6xl md:text-8xl font-black uppercase mb-8 leading-[0.9] tracking-tighter drop-shadow-2xl">
            Water Damage<br/>Restoration Services
          </h1>
          <p className="max-w-3xl mx-auto text-xl md:text-2xl font-bold mb-12 drop-shadow-lg">
            ProBrite Gen offers efficient water damage restoration services, leaving your property dry and ready for use in Houston, TX after flooding or leaks.
          </p>
          <button 
            onClick={() => openChatWidget()}
            className="bg-primary hover:bg-opacity-90 text-white font-black uppercase px-12 py-5 text-xl tracking-widest shadow-2xl transition-transform hover:scale-105"
          >
            Get Free Quote
          </button>
        </div>
      </section>

      {/* 2. Main Content Intro Section */}
      <section className="bg-white py-24">
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12">
          <div className="max-w-4xl mx-auto text-center mb-20 space-y-8">
            <p className="text-lg md:text-xl font-medium text-gray-700 leading-relaxed">
              When water damage or flooding happens, quick action is important to prevent bigger problems. ProBrite Gen provides water damage restoration services in Houston, TX to help remove water, dry affected areas, and protect your property from further damage. Acting fast can help reduce damage to building materials and limit long-term issues.
            </p>
            <p className="text-lg md:text-xl font-medium text-gray-700 leading-relaxed">
              We handle more than just visible water. Our team removes standing water, uses drying equipment to reach hidden moisture, and checks affected areas to make sure they are properly dried. This process helps protect floors, walls, and other materials while lowering the risk of mold growth and unpleasant odors.
            </p>
            <p className="text-lg md:text-xl font-medium text-gray-700 leading-relaxed">
              Water damage can come from many sources, including broken pipes, leaking appliances, roof leaks, or flooding. No matter the cause, ProBrite Gen works carefully and efficiently to restore your space. Our goal is to leave your property clean, dry, and safe so it is ready for repairs or normal use again.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <img 
              src="/media/6976c32bc1fa0cbbdba6d70d.png" 
              alt="Water damage restoration process 1" 
              className="w-full aspect-video object-cover rounded-sm shadow-xl" 
            />
            <img 
              src="/media/6976c388a87bebeb9de7d09f.png" 
              alt="Water damage restoration process 2" 
              className="w-full aspect-video object-cover rounded-sm shadow-xl" 
            />
            <img 
              src="/media/6977d7fff62bb7666098bdaa.png" 
              alt="Water damage restoration process 3" 
              className="w-full aspect-video object-cover rounded-sm shadow-xl" 
            />
          </div>
        </div>
      </section>

      {/* 4. Our Process Section */}
      <section className="bg-navy py-24 text-white border-t border-white border-opacity-10">
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 text-center">
          <div className="flex items-center justify-center gap-6 mb-4">
            <h2 className="text-5xl md:text-6xl font-black uppercase tracking-tighter">Our Process</h2>
            <div className="w-1/3 h-px bg-white/20 hidden md:block"></div>
          </div>
          <p className="text-xl opacity-80 mb-24 font-medium italic">Our process is simple and only contains a few simple steps.</p>
          <div className="flex flex-col md:flex-row justify-between items-start gap-12">
            {steps.map((step, idx) => (
              <div key={idx} className="flex-1 w-full flex flex-col items-center">
                <div className="w-32 h-32 rounded-full border-4 border-navy bg-white flex items-center justify-center text-navy mb-12 shadow-2xl relative">
                  {step.icon}
                  {idx < steps.length - 1 && (
                    <div className="hidden md:block absolute left-full top-1/2 w-full h-1 bg-white opacity-20 -translate-y-1/2"></div>
                  )}
                </div>
                <div className="w-full relative">
                   <div className="bg-white text-navy py-5 px-3 font-black uppercase text-sm rounded-sm shadow-2xl">
                      <span className="block tracking-tight">{step.label}</span>
                   </div>
                   {/* Step Arrow */}
                   <div className="absolute top-1/2 -right-4 w-8 h-8 bg-white transform rotate-45 -translate-y-1/2 hidden md:block z-0"></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 5. Service Areas Section */}
      <section className="bg-navy py-32 text-white border-t border-white border-opacity-10">
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 flex flex-col items-center">
          <h2 className="text-6xl md:text-7xl font-black uppercase tracking-tighter mb-20 text-center">
            PROUDLY SERVING
          </h2>
          <div className="w-full grid grid-cols-1 md:grid-cols-1 lg:grid-cols-1 gap-y-10 gap-x-32 max-w-4xl text-center">
            <div className="flex items-center justify-center gap-6 text-2xl font-black uppercase tracking-[0.1em] group border-b border-white border-opacity-5 pb-4">
              <MapPin size={32} className="text-primary group-hover:scale-125 transition-transform duration-300" />
              <span className="group-hover:text-primary transition-colors">Houston, TX & Surrounding Cities</span>
            </div>
          </div>
        </div>
      </section>

      {/* 6. Final CTA Section */}
      <section className="relative py-40 bg-navy overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={bgImage} alt="Final CTA background" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/40"></div>
        </div>
        <div className="max-w-[1400px] mx-auto px-6 relative z-10 text-center text-white">
          <h2 className="text-5xl md:text-8xl font-black uppercase mb-6 tracking-tighter drop-shadow-2xl">
            READY TO TAKE THE NEXT STEP?
          </h2>
          <h3 className="text-5xl md:text-8xl font-black uppercase mb-16 tracking-tighter italic opacity-90 drop-shadow-2xl">
            GET A FREE QUOTE TODAY!
          </h3>
          <button 
            onClick={() => openChatWidget()}
            className="bg-primary hover:bg-opacity-90 text-white font-black uppercase px-16 py-6 rounded-md transition-all text-2xl tracking-[0.3em] shadow-2xl transform hover:scale-105"
          >
            GET A FREE QUOTE
          </button>
        </div>
      </section>
    </div>
  );
};

export default WaterDamagePage;

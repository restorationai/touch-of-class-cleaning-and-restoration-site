import { openChatWidget } from '../store';

import React from 'react';
import { ArrowRight, Star, Users, FileCheck, Settings, Search, HandCoins, MapPin } from 'lucide-react';



const HotWaterPage: React.FC = () => {
  const bgImage = "/media/6976c78bc1fa0c9f59a78f69.png";
  
  const steps = [
    { icon: <Users size={45} />, label: "Free Consultation" },
    { icon: <FileCheck size={45} />, label: "Inspection & Assessment" },
    { icon: <Settings size={45} />, label: "Heater Installation" },
    { icon: <Search size={45} />, label: "Final Inspection" },
    { icon: <HandCoins size={45} />, label: "Completion" },
  ];

  return (
    <div className="flex flex-col">
      {/* 1. Hero Section */}
      <section className="relative min-h-[600px] flex items-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={bgImage} alt="Hot Water background" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/40"></div>
        </div>
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 relative z-10 w-full text-center text-white py-20">
          <h1 className="text-6xl md:text-8xl font-black uppercase mb-8 leading-[0.9] tracking-tighter drop-shadow-2xl">
            Hot Water<br/>Installation
          </h1>
          <p className="max-w-3xl mx-auto text-xl md:text-2xl font-bold mb-12 drop-shadow-lg">
            ProBrite Gen provides professional water heater installation, replacement, and repair services in Houston, TX, keeping your home comfortable and running efficiently.
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
              A reliable water heater is essential for your home's everyday comfort. Whether you are dealing with an aging unit, frequent leaks, or inconsistent water temperature, these are all signs that it may be time for a professional replacement or repair. Most traditional water heaters last 8 to 12 years, and acting before a full failure can save you from unexpected water damage and higher emergency repair costs.
            </p>
            <p className="text-lg md:text-xl font-medium text-gray-700 leading-relaxed">
              ProBrite Gen provides expert water heater installation and replacement services in Houston, TX and surrounding cities. We install and service both electric and gas water heaters, with storage tank and tankless options available to fit your home's size and your budget. Our certified technicians handle the entire process — from helping you select the right unit to completing the installation with minimal disruption to your daily routine.
            </p>
            <p className="text-lg md:text-xl font-medium text-gray-700 leading-relaxed">
              We work with trusted suppliers to ensure every unit we install is built for long-lasting, energy-efficient performance. After your new system is in place, we provide ongoing maintenance and support so your hot water stays reliable for years to come. Our goal is to provide a seamless installation experience that keeps your home running smoothly and efficiently.
            </p>
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

export default HotWaterPage;

import React from 'react';
import { openChatWidget } from '../store';

const Hero: React.FC = () => {
  return (
    <section className="relative min-h-[750px] flex items-center overflow-hidden">
      {/* Background with Overlay */}
      <div className="absolute inset-0 z-0">
        <img 
          src="/media/69d454413d829c73b28678e0.png" 
          alt="ProBrite Gen Restoration" 
          className="w-full h-full object-cover object-center scale-100 lg:scale-[1.05] transition-transform duration-700 brightness-90 contrast-110"
          style={{ imageRendering: 'auto' }}
        />
        {/* Adjusted overlay to be more transparent (40%) so the image is clearly visible behind the content */}
        <div className="absolute inset-0 bg-black/40"></div>
      </div>

      <div className="max-w-[1400px] mx-auto px-4 sm:px-10 lg:px-12 relative z-10 w-full py-20">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-24 items-center">
          
          {/* Left Column Content - Strictly Centered on mobile */}
          <div className="text-white flex flex-col items-center lg:items-start text-center lg:text-left w-full">
            <h1 className="text-4xl xs:text-5xl md:text-6xl lg:text-7xl font-black uppercase mb-6 lg:mb-8 leading-[1.1] tracking-tighter drop-shadow-[0_4px_4px_rgba(0,0,0,0.8)]">
              Houston's Trusted Water Damage, Mold & Water Treatment Experts
            </h1>
            <div className="max-w-xl lg:max-w-2xl">
              <p className="text-base sm:text-lg md:text-2xl opacity-100 leading-relaxed font-bold drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)] mb-6">
                ProBrite Gen is Houston's all-in-one water specialist. We restore properties after water damage and mold, and we improve your home's water quality with softeners, filtration systems, and hot water heater installation. Whether you're dealing with an emergency or upgrading your water system, we bring fast, professional service — and we work directly with your insurance company to make the process easy.
              </p>
              <div className="inline-block border-b-2 border-white pb-1">
                <span className="text-base sm:text-xl font-black uppercase tracking-widest text-white">Houston, TX</span>
              </div>
            </div>
          </div>

          {/* Right Column Content - Buttons */}
          <div className="w-full flex justify-center lg:justify-end">
            <div className="flex flex-col space-y-4 w-full max-w-sm">
              
              {/* Email - Not a button, just outlined text */}
              <div className="w-full border-2 border-white text-white py-5 px-6 font-black uppercase text-center tracking-widest rounded-sm">
                <span className="text-xs opacity-80 block mb-1">Email Us</span>
                <span className="select-all">SERVICE@PROBRITEGEN.COM</span>
              </div>
              
              {/* Phone Button - Orange */}
              <a 
                href="tel:+18326886779"
                className="w-full bg-accent text-white py-5 px-6 font-black uppercase text-center tracking-widest rounded-sm shadow-xl hover:bg-opacity-90 transition-all text-xl"
              >
                (832) 688-6779
              </a>

              {/* Get A Free Quote Button - Blue */}
              <button 
                onClick={openChatWidget}
                className="w-full bg-primary text-white py-6 px-6 font-black uppercase text-center tracking-widest rounded-sm shadow-xl hover:bg-opacity-90 transition-all text-2xl"
              >
                Get A Free Quote
              </button>

            </div>
          </div>

        </div>
      </div>
    </section>
  );
};

export default Hero;

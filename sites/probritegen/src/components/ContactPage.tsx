import React from 'react';
import { openChatWidget } from '../store';
import Process from './Process';
import ServiceAreas from './ServiceAreas';
import FinalCTA from './FinalCTA';

const ContactPage: React.FC = () => {
  const bgImage = "/media/6976c78bc1fa0c9f59a78f69.png";
  const logoUrl = "/media/69cd6fb6ddfdcb063981acc7.png";

  return (
    <div className="flex flex-col">
      {/* 1. Hero Section */}
      <section className="relative min-h-[600px] flex items-center justify-center text-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={bgImage} alt="Contact background" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/60"></div>
        </div>
        <div className="relative z-10 text-white px-6 w-full max-w-2xl mx-auto">
          <h1 className="text-6xl md:text-8xl font-black uppercase tracking-tighter mb-4 drop-shadow-2xl">
            CONTACT US
          </h1>
          <p className="text-xl md:text-2xl font-bold opacity-90 mb-10 max-w-2xl mx-auto italic">
            Get in touch with any questions or comments and we'll be happy to help.
          </p>
          
          {/* MOBILE ONLY: Email and Phone Buttons + Bouncing Arrow */}
          <div className="lg:hidden flex flex-col items-center space-y-6 mt-8">
            <div className="w-full space-y-4">
              <a 
                href="mailto:service@probritegen.com"
                className="block w-full bg-primary py-4 px-6 text-white font-black uppercase text-center tracking-widest rounded-sm shadow-xl"
              >
                EMAIL: SERVICE@PROBRITEGEN.COM
              </a>
              <a 
                href="tel:+18326886779"
                className="block w-full bg-primary py-4 px-6 text-white font-black uppercase text-center tracking-widest rounded-sm shadow-xl"
              >
                PHONE: (832) 688-6779
              </a>
            </div>

            {/* Bouncing Arrow specifically for mobile under buttons */}
            <div className="flex flex-col items-center gap-2 animate-bounce mt-4">
              <div className="w-0.5 h-8 bg-white opacity-40"></div>
              <div className="w-3 h-3 border-r-2 border-b-2 border-white rotate-45 opacity-60"></div>
              <div className="w-3 h-3 border-r-2 border-b-2 border-white rotate-45 opacity-40"></div>
            </div>
          </div>

          {/* Desktop Only Scroll Indicator */}
          <div className="hidden lg:flex flex-col items-center gap-2 mt-10 animate-bounce">
            <div className="w-1 h-8 bg-white opacity-40"></div>
            <div className="w-4 h-4 border-r-2 border-b-2 border-white rotate-45 opacity-60"></div>
            <div className="w-4 h-4 border-r-2 border-b-2 border-white rotate-45 opacity-40"></div>
          </div>
        </div>
      </section>

      {/* 2. Contact Form & Info Section */}
      <section className="bg-white py-24 relative">
        <div className="max-w-[1400px] mx-auto px-6 sm:px-10 lg:px-12">
          {/* Use flex-col and order classes for mobile reordering */}
          <div className="flex flex-col lg:grid lg:grid-cols-2 gap-20 items-center">
            
            {/* TEXT CONTENT: Mobile Order 1, Desktop Order 1 */}
            <div className="space-y-10 order-1 lg:order-none">
              <h2 className="text-5xl md:text-6xl font-black uppercase tracking-tighter text-navy leading-none">
                CONTACT US FOR A FREE QUOTE
              </h2>
              <p className="text-xl text-gray-600 font-medium leading-relaxed">
                We are available 24/7 for all your restoration and water solution needs. Contact us by filling in the form or by using any of the methods below and we'll respond immediately.
              </p>
            </div>

            {/* FORM CARD: Mobile Order 2 (Above buttons), Desktop Order 2 */}
            <div className="bg-navy rounded-sm p-8 md:p-12 shadow-[0_50px_100px_-20px_rgba(0,0,0,0.5)] relative z-20 order-2 lg:order-none flex flex-col justify-center items-center h-full space-y-6">
               {/* Logo hidden on mobile/tablet, visible on large screens */}
               <div className="hidden lg:flex justify-center mb-6">
                  <img src={logoUrl} alt="ProBrite Gen Logo" className="h-24 w-auto object-contain" />
               </div>
               
              {/* Email - Not a button, just outlined text */}
              <div className="w-full max-w-sm border-2 border-white text-white py-5 px-6 font-black uppercase text-center tracking-widest rounded-sm">
                <span className="text-xs opacity-80 block mb-1">Email Us</span>
                <span className="select-all">SERVICE@PROBRITEGEN.COM</span>
              </div>
              
              {/* Phone Button - Orange */}
              <a 
                href="tel:+18326886779"
                className="w-full max-w-sm bg-accent text-white py-5 px-6 font-black uppercase text-center tracking-widest rounded-sm shadow-xl hover:bg-opacity-90 transition-all text-xl"
              >
                (832) 688-6779
              </a>

              {/* Get A Free Quote Button - Blue */}
              <button 
                onClick={openChatWidget}
                className="w-full max-w-sm bg-primary text-white py-6 px-6 font-black uppercase text-center tracking-widest rounded-sm shadow-xl hover:bg-opacity-90 transition-all text-2xl"
              >
                Get A Free Quote
              </button>
            </div>

          </div>
        </div>
      </section>

      {/* 3. Re-used Sections */}
      <Process />
      <ServiceAreas />
      <FinalCTA />
    </div>
  );
};

export default ContactPage;

import { openChatWidget } from '../store';

import React from 'react';
import { ArrowRight, Star, Users, FileCheck, Settings, Search, HandCoins, MapPin, ChevronDown, ChevronUp } from 'lucide-react';



const WaterSoftenerPage: React.FC = () => {
  const bgImage = "/media/6976c78bc1fa0c9f59a78f69.png";
  
  const steps = [
    { icon: <Users size={45} />, label: "Free Consultation" },
    { icon: <FileCheck size={45} />, label: "Water Assessment" },
    { icon: <Settings size={45} />, label: "System Installation" },
    { icon: <Search size={45} />, label: "Final Inspection" },
    { icon: <HandCoins size={45} />, label: "Completion" },
  ];

  const faqs = [
    {
      question: "Do I really need a water softener in Houston?",
      answer: "Yes — Houston water is often hard due to high mineral content. A water softener reduces scale and protects your plumbing from costly damage."
    },
    {
      question: "What is the difference between softening and filtration?",
      answer: "A softener removes minerals that cause hardness, while a filtration system targets contaminants, chlorine, taste, odors, and sediment."
    },
    {
      question: "Are water softeners safe to drink from?",
      answer: "Yes. Softened water is safe; if you are sodium-sensitive, ask about alternative systems or blended solutions."
    },
    {
      question: "How long does installation take?",
      answer: "Most system installs are completed in a few hours with minimal disruption."
    }
  ];

  const [openFaq, setOpenFaq] = React.useState<number | null>(null);

  return (
    <div className="flex flex-col">
      {/* 1. Hero Section */}
      <section className="relative min-h-[600px] flex items-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={bgImage} alt="Water Softener background" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/40"></div>
        </div>
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 relative z-10 w-full text-center text-white py-20">
          <h1 className="text-6xl md:text-8xl font-black uppercase mb-8 leading-[0.9] tracking-tighter drop-shadow-2xl">
            Water Softener<br/>Solutions
          </h1>
          <p className="max-w-3xl mx-auto text-xl md:text-2xl font-bold mb-12 drop-shadow-lg">
            ProBrite Gen provides professional water softener installation and whole-home filtration systems in Houston, TX, designed to protect your home, your health, and your daily comfort.
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
              Houston's water supply frequently contains high levels of calcium and magnesium minerals that cause hard water issues throughout your home. Hard water leads to scale buildup in pipes, faucets, and appliances, shortened lifespan of water heaters and dishwashers, poor soap and detergent performance, dry skin and brittle hair, and cloudy drinking water. Without a proper water treatment system in place, these minerals will continue to wear down your plumbing and affect your daily comfort over time.
            </p>
            <p className="text-lg md:text-xl font-medium text-gray-700 leading-relaxed">
              ProBrite Gen offers professional whole-home water softener installation and filtration solutions designed specifically for Houston homeowners. Our services include whole-home water softener systems for hard water protection, advanced filtration solutions to remove chlorine, sediment, and contaminants, salt-based and salt-free options to fit your needs, reverse osmosis drinking water systems for purified water at the tap, and professional sizing and certified installation with no guesswork. Every installation begins with a comprehensive in-home water assessment so you get the right system for your specific water quality and household needs.
            </p>
            <p className="text-lg md:text-xl font-medium text-gray-700 leading-relaxed">
              Once your system is installed, you will notice the difference right away — softer skin, better-feeling showers, cleaner dishes, brighter laundry, extended life for your water heaters and appliances, and better tasting, healthier water straight from the tap. ProBrite Gen works with trusted water system suppliers to ensure every unit we install is built for long-lasting, reliable performance. We also offer flexible financing options on qualifying systems and ongoing maintenance and support after installation.
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

      {/* FAQ Section */}
      <section className="bg-white py-24">
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12">
          <h2 className="text-5xl md:text-6xl font-black uppercase tracking-tighter mb-16 text-center">Frequently Asked Questions</h2>
          <div className="max-w-4xl mx-auto space-y-4">
            {faqs.map((faq, idx) => (
              <div key={idx} className="border-2 border-gray-100 rounded-lg overflow-hidden">
                <button 
                  onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
                  className="w-full flex items-center justify-between p-6 text-left bg-white hover:bg-gray-50 transition-colors"
                >
                  <span className="text-xl font-bold uppercase tracking-tight">{faq.question}</span>
                  {openFaq === idx ? <ChevronUp size={24} className="text-primary" /> : <ChevronDown size={24} className="text-primary" />}
                </button>
                {openFaq === idx && (
                  <div className="p-6 bg-gray-50 border-t-2 border-gray-100">
                    <p className="text-lg font-medium text-gray-700">{faq.answer}</p>
                  </div>
                )}
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

export default WaterSoftenerPage;

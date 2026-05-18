import { openChatWidget } from '../store';

import React from 'react';
import { ArrowRight, Star, Users, FileCheck, Settings, Search, HandCoins, MapPin, ChevronDown, ChevronUp } from 'lucide-react';



const SewageBackupPage: React.FC = () => {
  const bgImage = "/media/6976c78bc1fa0c9f59a78f69.png";
  
  const steps = [
    { icon: <Users size={45} />, label: "Free Consultation" },
    { icon: <FileCheck size={45} />, label: "Inspection & Assessment" },
    { icon: <Settings size={45} />, label: "Sewage Cleanup" },
    { icon: <Search size={45} />, label: "Final Inspection" },
    { icon: <HandCoins size={45} />, label: "Completion" },
  ];

  const faqs = [
    {
      question: "What should I do immediately after a sewage backup?",
      answer: "Avoid contact with the affected area and call ProBrite Gen right away. Sewage contains harmful bacteria and should only be handled by trained professionals."
    },
    {
      question: "Is sewage backup covered by insurance?",
      answer: "It depends on your policy. We can help you document the damage to support your insurance claim."
    },
    {
      question: "How long does sewage cleanup take?",
      answer: "Most cleanups are completed within 1-3 days depending on the extent of the backup and the affected area."
    }
  ];

  const [openFaq, setOpenFaq] = React.useState<number | null>(null);

  return (
    <div className="flex flex-col">
      {/* 1. Hero Section */}
      <section className="relative min-h-[600px] flex items-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={bgImage} alt="Sewage Backup background" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/40"></div>
        </div>
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 relative z-10 w-full text-center text-white py-20">
          <h1 className="text-6xl md:text-8xl font-black uppercase mb-8 leading-[0.9] tracking-tighter drop-shadow-2xl">
            Sewage Backup<br/>and Cleanup
          </h1>
          <p className="max-w-3xl mx-auto text-xl md:text-2xl font-bold mb-12 drop-shadow-lg">
            ProBrite Gen provides specialized sewage backup cleanup services in Houston, TX, ensuring your home is thoroughly cleaned, disinfected, and restored to a safe state.
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
              Sewage backups are not just unpleasant — they pose serious health risks to you and your family. When sewage water enters your home, it carries harmful bacteria, viruses, and pathogens that can contaminate surfaces, furniture, and the air. If not handled quickly and properly, the damage can spread far beyond the visible affected area, creating long-term structural and health hazards.
            </p>
            <p className="text-lg md:text-xl font-medium text-gray-700 leading-relaxed">
              ProBrite Gen provides specialized sewage backup and cleanup services in Houston, TX and surrounding cities. Our team responds quickly to remove all contaminated water and waste, disinfect every affected surface, and eliminate bacteria and odors using industry-leading equipment. We handle the entire process from start to finish so you don't have to worry about a thing.
            </p>
            <p className="text-lg md:text-xl font-medium text-gray-700 leading-relaxed">
              After the cleanup is complete, we thoroughly sanitize and restore the affected areas to a safe, livable condition. We also guide you on how to maintain your plumbing system to reduce the risk of future backups. Our goal is to leave your property completely clean, safe, and fully restored — with as little disruption to your daily life as possible.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <img 
              src="/media/69cd83bf45ec94717bfb490b.png" 
              alt="Sewage cleanup process 1" 
              className="w-full aspect-video object-cover rounded-sm shadow-xl" 
            />
            <img 
              src="/media/69cd83bf2815919248ee1ea5.png" 
              alt="Sewage cleanup process 2" 
              className="w-full aspect-video object-cover rounded-sm shadow-xl" 
            />
            <img 
              src="/media/69cd83bfc85939f3533be73a.png" 
              alt="Sewage cleanup process 3" 
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

export default SewageBackupPage;

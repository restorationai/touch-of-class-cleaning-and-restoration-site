import { openChatWidget } from '../store';

import React from 'react';



const FinalCTA: React.FC = () => {
  return (
    <section className="relative py-40 bg-navy overflow-hidden">
      {/* Background Image Container */}
      <div className="absolute inset-0 z-0">
        <img 
          src="/media/6976c78bc1fa0c9f59a78f69.png" 
          alt="Professional restoration and construction site" 
          className="w-full h-full object-cover" 
        />
        {/* Dark overlay to ensure text readability */}
        <div className="absolute inset-0 bg-black/40"></div>
      </div>

      <div className="max-w-[1400px] mx-auto px-6 relative z-10 text-center">
        <h2 className="text-5xl md:text-7xl font-black uppercase text-white mb-6 drop-shadow-[0_4px_4px_rgba(0,0,0,0.8)] tracking-tighter">
          Ready to take the next step?
        </h2>
        <h3 className="text-5xl md:text-7xl font-black uppercase text-white mb-16 drop-shadow-[0_4px_4px_rgba(0,0,0,0.8)] tracking-tighter italic opacity-90 drop-shadow-2xl">
          Get a free quote today!
        </h3>
        <button 
          onClick={() => openChatWidget()}
          className="bg-primary hover:bg-opacity-90 text-white font-black uppercase px-16 py-6 rounded-md transition-all text-2xl tracking-[0.3em] shadow-[0_20px_50px_rgba(0,0,0,0.5)] border-2 border-white border-opacity-20 hover:scale-105"
        >
          Get A Free Quote
        </button>
      </div>
    </section>
  );
};

export default FinalCTA;

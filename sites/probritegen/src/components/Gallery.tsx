
import React from 'react';
import { ArrowRight } from 'lucide-react';



const Gallery: React.FC = () => {
  // Using 6 before-and-after images for the home section as requested
  const photos = [
    "/media/6976c32bc1fa0cbbdba6d70d.png",
    "/media/6976c388a87bebeb9de7d09f.png",
    "/media/6977d7fff62bb7666098bdaa.png",
    "/media/6976cc33c1fa0c7e02a83b75.png",
    "/media/6976cc33eb392b5ed868201e.png",
    "/media/6976cc38c1fa0c1523a83c22.png",
  ];

  return (
    <section className="bg-navy py-24 text-white">
      <div className="max-w-[1400px] mx-auto px-6 sm:px-10 lg:px-12">
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-16 gap-8">
          <div>
            <span className="inline-block bg-black text-white px-4 py-1.5 text-xs font-black uppercase tracking-[0.3em] mb-4">See why our customers love us</span>
            <div className="flex items-center gap-6">
              <h2 className="text-5xl md:text-6xl font-black uppercase tracking-tighter">Our Work</h2>
              <div className="hidden md:block flex-grow h-px bg-white/30 w-72"></div>
            </div>
          </div>
          <button 
            onClick={() => onNavigate?.('gallery')}
            className="bg-white text-navy font-black uppercase px-8 py-4 text-base flex items-center gap-3 hover:bg-primary hover:text-white transition-all rounded-sm shadow-xl"
          >
            See All Photos <ArrowRight size={20} />
          </button>
        </div>

        <div className="columns-1 sm:columns-2 lg:columns-3 gap-6 space-y-6">
          {photos.map((src, i) => (
            <div key={i} className="break-inside-avoid overflow-hidden rounded-sm border-4 border-white border-opacity-10 shadow-2xl group transition-all duration-500 hover:border-primary">
              <img 
                src={src} 
                alt={`Restoration project ${i+1}`} 
                className="w-full h-auto transition-all duration-700 transform group-hover:scale-105" 
                referrerPolicy="no-referrer"
              />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Gallery;

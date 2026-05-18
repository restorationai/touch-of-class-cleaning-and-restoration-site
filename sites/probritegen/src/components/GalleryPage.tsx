
import React from 'react';
import { Camera } from 'lucide-react';

const GalleryPage: React.FC = () => {
  const allPhotos = [
    "/media/6976c78bc1fa0c9f59a78f69.png",
    "/media/6976cf73d4fb905a09ee6ab7.png",
    "/media/6976c32bc1fa0cbbdba6d70d.png",
    "/media/6976c388a87bebeb9de7d09f.png",
    "/media/6977d7fff62bb7666098bdaa.png",
    "/media/6976cc33c1fa0c7e02a83b75.png",
    "/media/6976cc33eb392b5ed868201e.png",
    "/media/6976cc38c1fa0c1523a83c22.png"
  ];

  return (
    <div className="flex flex-col bg-navy min-h-screen">
      {/* Hero / Header for Gallery */}
      <section className="relative min-h-[600px] flex items-center justify-center overflow-hidden border-b border-white border-opacity-10">
        <div className="absolute inset-0 z-0">
          <img 
            src="/media/6976c78bc1fa0c9f59a78f69.png" 
            alt="Gallery background" 
            className="w-full h-full object-cover"
          />
        </div>
        <div className="relative z-10 text-center text-white px-6">
          <h1 className="text-6xl md:text-8xl font-black uppercase tracking-tighter mb-4 drop-shadow-2xl">Our Work</h1>
        </div>
      </section>

      {/* Main Grid */}
      <section className="py-24">
        <div className="max-w-[1400px] mx-auto px-6 sm:px-10 lg:px-12">
          <div className="columns-1 sm:columns-2 lg:columns-3 xl:columns-4 gap-6 space-y-6">
            {allPhotos.map((src, i) => (
              <div 
                key={i} 
                className="break-inside-avoid overflow-hidden rounded-sm border-4 border-white border-opacity-10 shadow-2xl group transition-all duration-500 hover:border-primary"
              >
                <img 
                  src={src} 
                  alt={`Project ${i+1}`} 
                  className="w-full h-auto transition-all duration-700 transform group-hover:scale-105" 
                  referrerPolicy="no-referrer"
                />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Trust Quote Section */}
      <section className="bg-black py-20 text-white text-center border-y border-white border-opacity-10">
         <div className="max-w-4xl mx-auto px-6">
            <h2 className="text-3xl md:text-4xl font-black uppercase tracking-tighter mb-6">Quality is our signature</h2>
            <p className="text-xl opacity-60 italic leading-relaxed">
              "We treat every home as if it were our own. From minor water leaks to major restoration projects, our attention to detail and commitment to excellence is reflected in every photo you see here."
            </p>
         </div>
      </section>
    </div>
  );
};

export default GalleryPage;

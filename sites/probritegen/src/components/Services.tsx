
import React from 'react';
import { ArrowRightCircle } from 'lucide-react';



const Services: React.FC = () => {
  const services = [
    {
      title: "WATER DAMAGE RESTORATION",
      image: "/media/6976c78bc1fa0c9f59a78f69.webp",
      page: 'water-damage' as const,
    },
    {
      title: "SEWAGE BACKUP AND CLEANUP",
      image: "/media/69cd83bfc85939f3533be73a.webp",
      page: 'sewage-backup' as const,
    },
    {
      title: "MOLD REMOVAL",
      image: "/media/6976cf73d4fb905a09ee6ab7.webp",
      page: 'mold-remediation' as const,
    },
    {
      title: "WATER SOFTENER SOLUTIONS",
      image: "/media/69cd83bf45ec94335ffb4906.jpg",
      page: 'water-softener' as const,
    },
    {
      title: "HOT WATER INSTALLATION",
      image: "/media/69cd83bfc8593984f53be739.webp",
      page: 'hot-water' as const,
    }
  ];

  return (
    <section className="bg-navy py-24 text-white">
      <div className="max-w-[1400px] mx-auto px-6 sm:px-10 lg:px-12">
        {/* Section Header matching reference */}
        <div className="mb-16">
          <div className="inline-block bg-black px-4 py-2 mb-4">
            <span className="text-white text-sm font-black uppercase tracking-widest">What we are best at</span>
          </div>
          <div className="flex items-center gap-6">
            <h2 className="text-5xl md:text-7xl font-black uppercase tracking-tighter whitespace-nowrap">Our Services</h2>
            <div className="flex-grow h-0.5 bg-white/20"></div>
          </div>
        </div>

        {/* Services Grid with spacing and individual borders */}
        <div className="flex flex-wrap justify-center gap-10">
          {services.map((service, idx) => (
            <div 
              key={idx} 
              className="group relative h-[500px] w-full md:w-[calc((100%-40px)/2)] lg:w-[calc((100%-80px)/3)] border-4 border-white shadow-2xl overflow-hidden cursor-pointer transform transition-transform hover:-translate-y-2"
              onClick={() => onNavigate(service.page)}
            >
              {/* Photo */}
              <img 
                src={service.image} 
                alt={service.title} 
                className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" 
              />
              
              {/* Image Overlay */}
              <div className="absolute inset-0 bg-black/30 group-hover:bg-opacity-10 transition-all duration-500"></div>
              
              {/* Bottom banner containing the text box */}
              <div className="absolute bottom-6 left-6 right-6">
                <div 
                  className="flex items-center justify-between bg-black text-white px-6 py-5 font-black uppercase text-xl border border-white border-opacity-10 shadow-xl group-hover:bg-primary transition-colors duration-300"
                >
                  <span className="tracking-tighter">{service.title}</span>
                  <ArrowRightCircle size={32} className="text-primary group-hover:text-white transition-colors" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Services;

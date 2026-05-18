
import React from 'react';
import { MapPin } from 'lucide-react';

const ServiceAreas: React.FC = () => {
  const areas = [
    "Houston, TX & Surrounding Cities"
  ];

  return (
    <section className="bg-navy py-32 text-white border-t border-white border-opacity-10">
      <div className="max-w-[1400px] mx-auto px-6 sm:px-10 lg:px-12 flex flex-col md:flex-row justify-between items-start gap-16">
         <div className="md:w-1/2">
            <h2 className="text-6xl md:text-7xl font-black uppercase leading-[0.85] tracking-tighter mb-10">
              Proudly Serving
            </h2>
            <p className="text-xl opacity-70 font-medium max-w-md">ProBrite Gen provides reliable restoration and water solutions throughout Houston, TX and surrounding cities.</p>
         </div>
         
         <div className="md:w-1/2 grid grid-cols-1 sm:grid-cols-1 gap-y-10 gap-x-16">
            {areas.map((area, i) => (
              <div key={i} className="flex items-center gap-4 text-xl font-black uppercase tracking-[0.1em] group cursor-pointer">
                <MapPin size={30} className="text-primary group-hover:scale-125 transition-transform duration-300" />
                <span className="group-hover:text-primary transition-colors">{area}</span>
              </div>
            ))}
         </div>
      </div>
    </section>
  );
};

export default ServiceAreas;

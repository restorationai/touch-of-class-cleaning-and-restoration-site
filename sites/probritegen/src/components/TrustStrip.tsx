
import React from 'react';
import { MapPin, Users, Clock, Shield, IdCard } from 'lucide-react';

const TrustStrip: React.FC = () => {
  const items = [
    { icon: <MapPin size={32} />, label: "100% Local" },
    { icon: <Users size={32} />, label: "Family Business" },
    { icon: <Clock size={32} />, label: "12+ Years Experience" },
    { icon: <Shield size={32} />, label: "Insured" },
    { icon: <IdCard size={32} />, label: "Fully Licensed" },
  ];

  return (
    <section className="bg-navy py-16 md:py-8 text-white border-y border-white border-opacity-10">
      <div className="max-w-[1400px] mx-auto px-6">
        
        {/* MOBILE VIEW: Vertical Stack with Icons Aligned to the Left of Text */}
        {/* Using w-fit and mx-auto ensures the whole block is centered, while items-start keeps icons vertically aligned */}
        <div className="flex flex-col lg:hidden items-start w-fit mx-auto gap-12 py-4">
          {items.map((item, idx) => (
            <div key={idx} className="flex items-center gap-6 font-black uppercase text-3xl xs:text-4xl tracking-tighter">
              <span className="text-white shrink-0 flex items-center justify-center w-10">
                {item.icon}
              </span>
              <span className="whitespace-nowrap">{item.label}</span>
            </div>
          ))}
        </div>
        
        {/* DESKTOP VIEW: Horizontal Row */}
        <div className="hidden lg:flex justify-between items-center gap-8 overflow-x-auto whitespace-nowrap">
          {items.map((item, idx) => (
            <div key={idx} className="flex items-center gap-3 font-black uppercase text-base tracking-[0.15em]">
              <span className="text-primary">{React.cloneElement(item.icon as React.ReactElement, { size: 24 })}</span>
              {item.label}
            </div>
          ))}
        </div>

      </div>
    </section>
  );
};

export default TrustStrip;

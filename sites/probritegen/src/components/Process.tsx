
import React from 'react';
import { FileText, Settings, Search, CreditCard, Users2 } from 'lucide-react';

const Process: React.FC = () => {
  const steps = [
    { icon: <Users2 size={45} />, label: "Free Consult" },
    { icon: <FileText size={45} />, label: "Estimation & Proposal" },
    { icon: <Settings size={45} />, label: "We do the work" },
    { icon: <Search size={45} />, label: "Final Inspection" },
    { icon: <CreditCard size={45} />, label: "Completion" },
  ];

  return (
    <section className="bg-navy py-24 text-white border-t border-white border-opacity-10">
      <div className="max-w-[1400px] mx-auto px-6 sm:px-10 lg:px-12 text-center">
        <h2 className="text-5xl md:text-6xl font-black uppercase mb-6 tracking-tighter">Our Process</h2>
        <p className="text-xl opacity-80 mb-20 font-medium">Our professional process ensures a smooth restoration journey from start to finish</p>
        
        <div className="relative flex flex-col md:flex-row justify-between items-center gap-16 md:gap-6">
          {steps.map((step, idx) => (
            <div key={idx} className="flex-1 w-full max-w-[220px] flex flex-col items-center">
               <div className="w-28 h-28 rounded-full border-4 border-white bg-white flex items-center justify-center text-navy mb-12 shadow-2xl relative z-10 transition-transform hover:scale-110 duration-500">
                  {step.icon}
                  {/* Connector Dots for Desktop */}
                  {idx < steps.length - 1 && (
                    <div className="hidden md:block absolute left-full top-1/2 w-full h-1 bg-white opacity-20 -translate-y-1/2"></div>
                  )}
               </div>
               <div className="bg-white text-navy w-full py-5 px-3 font-black uppercase text-sm rounded-sm transform md:skew-x-[-15deg] shadow-2xl relative">
                  <span className="md:skew-x-[15deg] block tracking-wider">{step.label}</span>
                  {/* Arrow Point for Step Effect */}
                  <div className="absolute top-1/2 -right-2 w-5 h-5 bg-white transform rotate-45 -translate-y-1/2 hidden md:block"></div>
               </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Process;

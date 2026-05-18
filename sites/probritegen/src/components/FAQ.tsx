
import React, { useState } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';

const FAQ: React.FC = () => {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const questions = [
    {
      q: "Can you provide references from past clients?",
      a: "Absolutely, we can provide references from past clients. Additionally, you can read the reviews and testimonials from our satisfied customers on our website. If you would like to speak with specific past clients, we can provide their contact information upon request."
    },
    {
      q: "What sets you apart from other restoration companies in the area?",
      a: "At ProBrite Gen, we distinguish ourselves through meticulous attention to detail, a dedication to quality, and a personalized approach. We prioritize client communication and work 24/7 to ensure your home or business is recovered as quickly as possible."
    },
    {
      q: "How long does a typical water damage restoration project take?",
      a: "The timeline depends on the project's size and complexity, but at ProBrite Gen, we pride ourselves on completing projects efficiently and safely while minimizing disruptions. Water drying can take 3-5 days, while major restoration timeline varies by scope."
    },
    {
      q: "Is there a fee for a consultation or estimate/quote?",
      a: "No, ProBrite Gen offers complimentary estimates and inspections to all prospective clients. We believe in transparent pricing and providing value from the very first contact."
    },
    {
      q: "Do you offer emergency services?",
      a: "Yes, we offer 24/7 emergency restoration services for water damage. When disaster strikes, our team is ready to respond immediately to mitigate further damage."
    }
  ];

  return (
    <section className="bg-navy py-24 text-white overflow-hidden border-t border-white border-opacity-10">
      <div className="max-w-[1400px] mx-auto px-6 sm:px-10 lg:px-12">
        <h2 className="text-5xl md:text-6xl font-black uppercase mb-20 tracking-tighter">Frequently Asked Questions</h2>
        
        <div className="max-w-4xl">
          <div className="space-y-6">
            {questions.map((item, idx) => (
              <div key={idx} className="border-b border-white border-opacity-10 last:border-0">
                <button 
                  onClick={() => setOpenIndex(openIndex === idx ? null : idx)}
                  className="w-full flex items-center justify-between py-8 text-left group"
                >
                  <span className="text-xl md:text-2xl font-black uppercase tracking-wide group-hover:text-primary transition-colors pr-10 flex gap-6">
                     <span className="text-primary mt-1">{openIndex === idx ? <ChevronUp size={28} /> : <ChevronDown size={28} />}</span>
                     {item.q}
                  </span>
                </button>
                {openIndex === idx && (
                  <div className="pb-10 text-xl opacity-80 leading-relaxed max-w-4xl animate-fadeIn pl-14">
                    {item.a}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default FAQ;

import React from 'react';
import { openChatWidget } from '../store';

const Footer: React.FC = () => {
  const areas = [
    "Houston, TX & Surrounding Cities"
  ];

  return (
    <footer className="bg-white text-navy pt-24 pb-12">
      <div className="max-w-[1400px] mx-auto px-6 sm:px-10 lg:px-12">
        <div className="grid md:grid-cols-2 lg:grid-cols-6 gap-12 mb-20">
          {/* Company Info Card */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg p-10 shadow-[0_20px_80px_-20px_rgba(0,0,0,0.3)] border border-gray-50 max-w-sm">
               <div className="flex items-center gap-6 mb-8">
                  <div className="w-24 h-24 overflow-hidden flex-shrink-0 flex items-center justify-center p-3 border-4 border-gray-50 shadow-inner">
                    <img 
                      src="/media/69cd6fb6ddfdcb063981acc7.png" 
                      alt="ProBrite Gen" 
                      className="w-full h-auto" 
                    />
                  </div>
                  <div>
                    <h4 className="font-black uppercase text-2xl italic leading-[0.85]">ProBrite Gen<br/><span className="text-sm font-bold opacity-60 not-italic tracking-wider">Water Solutions</span></h4>
                    <p className="text-base font-bold opacity-60 mt-2">Houston, TX</p>
                    <p className="text-xs font-bold opacity-40">service@probritegen.com</p>
                  </div>
               </div>
               
               <div className="flex flex-col gap-3 font-black uppercase text-xs tracking-widest text-center">
                  <a 
                    href="tel:+18326886779" 
                    className="w-full py-4 bg-primary border-2 border-primary text-white rounded-sm hover:bg-transparent hover:text-primary transition-all text-sm shadow-md flex items-center justify-center"
                  >
                    (832) 688-6779
                  </a>
                  <div className="flex gap-3">
                    <a 
                      href="/contact"
                      className="flex-1 py-4 border-2 border-navy hover:bg-navy hover:text-white transition-all text-xs flex items-center justify-center"
                    >
                      Contact
                    </a>
                    <button 
                      onClick={() => openChatWidget()}
                      className="flex-1 py-4 bg-navy text-white hover:bg-opacity-90 transition-all text-xs"
                    >
                      Get Quote
                    </button>
                  </div>
               </div>
            </div>
          </div>

          {/* Links Columns */}
          <div>
            <h5 className="font-black uppercase text-sm tracking-[0.25em] mb-8 border-b-2 border-navy border-opacity-10 pb-2 inline-block whitespace-nowrap">Business</h5>
            <ul className="space-y-4 text-base font-black uppercase tracking-wider opacity-80">
              <li><a href="/" className="block hover:text-primary transition-colors text-left uppercase">Home</a></li>
              <li><a href="/gallery" className="block hover:text-primary transition-colors text-left uppercase">Gallery</a></li>
              <li><a href="/blog" className="block hover:text-primary transition-colors text-left uppercase">Blog</a></li>
              <li><a href="/careers" className="block hover:text-primary transition-colors text-left uppercase">Careers</a></li>
              <li><a href="/contact" className="block hover:text-primary transition-colors text-left uppercase">Contact</a></li>
            </ul>
          </div>

          <div>
            <h5 className="font-black uppercase text-sm tracking-[0.25em] mb-8 border-b-2 border-navy border-opacity-10 pb-2 inline-block whitespace-nowrap">Services</h5>
            <ul className="space-y-4 text-base font-black uppercase tracking-wider opacity-80">
              <li><a href="/water-damage" className="block hover:text-primary transition-colors text-left uppercase">Water Damage</a></li>
              <li><a href="/sewage-backup" className="block hover:text-primary transition-colors text-left uppercase">Sewage Backup</a></li>
              <li><a href="/mold-remediation" className="block hover:text-primary transition-colors text-left uppercase">Mold Removal</a></li>
              <li><a href="/water-softener" className="block hover:text-primary transition-colors text-left uppercase">Water Softener</a></li>
              <li><a href="/hot-water" className="block hover:text-primary transition-colors text-left uppercase">Hot Water</a></li>
            </ul>
          </div>

          <div>
            <h5 className="font-black uppercase text-sm tracking-[0.25em] mb-8 border-b-2 border-navy border-opacity-10 pb-2 inline-block whitespace-nowrap">Service Area</h5>
            <ul className="space-y-4 text-base font-black uppercase tracking-wider opacity-80">
              {areas.map((area, i) => (
                <li key={i} className="hover:text-primary transition-colors cursor-default block">{area}</li>
              ))}
            </ul>
          </div>

          <div>
            <h5 className="font-black uppercase text-sm tracking-[0.25em] mb-8 border-b-2 border-navy border-opacity-10 pb-2 inline-block whitespace-nowrap">Hours</h5>
            <div className="flex flex-col gap-2">
              <p className="text-2xl font-black uppercase italic tracking-tighter text-primary">Open 24/7</p>
              <p className="text-[10px] font-black uppercase tracking-widest opacity-60">Emergency Response Anytime</p>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-12 border-t border-gray-100 flex flex-col md:flex-row justify-between items-center gap-6 text-xs font-black uppercase tracking-widest opacity-50">
           <p>© {new Date().getFullYear()} ProBrite Gen. Professional Restoration and Water Solutions in Houston, TX.</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;

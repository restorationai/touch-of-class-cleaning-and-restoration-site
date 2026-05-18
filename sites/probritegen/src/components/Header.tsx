import React, { useState, useEffect } from 'react';
import { Phone, ChevronDown, Menu, X } from 'lucide-react';
import { openChatWidget } from '../store';

const Header: React.FC = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isServicesOpen, setIsServicesOpen] = useState(false);
  const [isResourcesOpen, setIsResourcesOpen] = useState(false);
  const [isMobileAreasOpen, setIsMobileAreasOpen] = useState(false);

  // Prevent background scrolling when mobile menu is open
  useEffect(() => {
    if (isMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isMenuOpen]);

  const areas = [
    "Houston, TX & Surrounding Cities"
  ];

  const onOpenQuote = () => {
    openChatWidget();
    setIsMenuOpen(false);
  };

  return (
    <header className="bg-navy text-white sticky top-0 z-50 border-b border-white border-opacity-20">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 w-full">
        <div className="flex justify-between items-center h-28 w-full">
          
          {/* MOBILE ONLY: Left & Center buttons */}
          <div className="flex xl:hidden items-center gap-2 flex-1">
            <button 
              onClick={() => openChatWidget()}
              className="bg-primary hover:bg-opacity-90 text-white px-3 py-2.5 text-[10px] xs:text-xs font-black uppercase rounded-sm transition-all shadow-md whitespace-nowrap"
            >
              Get Free Quote
            </button>
            <a 
              href="tel:+18326886779" 
              className="flex items-center gap-2 bg-accent border-2 border-accent text-white px-3 py-2 rounded-sm font-black text-[10px] xs:text-xs hover:bg-transparent hover:text-accent transition-all shadow-md whitespace-nowrap"
            >
              <Phone size={14} className="fill-current" />
              <span className="font-bold">(832) 688-6779</span>
            </a>
          </div>

          {/* DESKTOP ONLY: Logo */}
          <a 
            className="hidden xl:flex flex-shrink-0 items-center gap-4 cursor-pointer"
            href="/"
          >
            <img 
              src="/media/69cd6fb6ddfdcb063981acc7.png" 
              alt="ProBrite Gen Logo" 
              className="h-24 w-auto object-contain"
            />
            <div className="font-black text-xl leading-tight italic">
              ProBrite Gen<br/>
              <span className="text-xs font-bold opacity-80 uppercase not-italic tracking-wider text-primary">Water Solutions Experts</span>
            </div>
          </a>

          {/* DESKTOP ONLY: Navigation */}
          <nav className="hidden xl:flex items-center gap-4 xl:gap-6 text-[10px] xl:text-xs font-black uppercase tracking-widest h-full px-2 flex-wrap">
            <a 
              href="/" 
              className="hover:text-primary transition-colors focus:outline-none py-8 font-black uppercase tracking-widest whitespace-nowrap"
            >
              Home
            </a>
            
            <div className="relative group py-8 h-full flex items-center">
              <div className="flex items-center gap-1 cursor-pointer hover:text-primary transition-colors whitespace-nowrap">
                Services <ChevronDown size={14} />
              </div>
              <div className="absolute top-full left-0 w-72 bg-navy border border-white border-opacity-10 shadow-2xl invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-all duration-200 z-50">
                <div className="flex flex-col">
                  <a href="/water-damage" className="block px-6 py-5 hover:bg-primary text-left transition-colors border-b border-white border-opacity-5">Water Damage Restoration</a>
                  <a href="/sewage-backup" className="block px-6 py-5 hover:bg-primary text-left transition-colors border-b border-white border-opacity-5">Sewage Backup and Cleanup</a>
                  <a href="/mold-remediation" className="block px-6 py-5 hover:bg-primary text-left transition-colors border-b border-white border-opacity-5">Mold Removal</a>
                  <a href="/water-softener" className="block px-6 py-5 hover:bg-primary text-left transition-colors border-b border-white border-opacity-5">Water Softener Solutions</a>
                  <a href="/hot-water" className="block px-6 py-5 hover:bg-primary text-left transition-colors">Hot Water Installation</a>
                </div>
              </div>
            </div>

            <a href="/gallery" className="hover:text-primary transition-colors focus:outline-none py-8 font-black uppercase tracking-widest whitespace-nowrap">Gallery</a>
            
            {/* Service Areas Dropdown */}
            <div className="relative group py-8 h-full flex items-center flex-shrink-0">
              <div className="flex items-center gap-1 cursor-pointer hover:text-primary transition-colors whitespace-nowrap">
                Service Areas <ChevronDown size={14} />
              </div>
              <div className="absolute top-full left-0 w-64 bg-navy border border-white border-opacity-10 shadow-2xl invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-all duration-200 z-50">
                <div className="flex flex-col">
                  {areas.map((area, idx) => (
                    <div 
                      key={idx} 
                      className={`px-6 py-4 hover:bg-primary transition-colors text-xs font-bold tracking-widest ${idx !== areas.length - 1 ? 'border-b border-white border-opacity-5' : ''}`}
                    >
                      {area}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Resources Dropdown */}
            <div className="relative group py-8 h-full flex items-center">
              <div className="flex items-center gap-1 cursor-pointer hover:text-primary transition-colors whitespace-nowrap">
                Resources <ChevronDown size={14} />
              </div>
              <div className="absolute top-full left-0 w-48 bg-navy border border-white border-opacity-10 shadow-2xl invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-all duration-200 z-50">
                <div className="flex flex-col">
                  <a href="/blog" className="block px-6 py-5 hover:bg-primary text-left transition-colors border-b border-white border-opacity-5">Blog</a>
                  <a href="/careers" className="block px-6 py-5 hover:bg-primary text-left transition-colors">Careers</a>
                </div>
              </div>
            </div>

            <a href="/contact" className="hover:text-primary transition-colors font-black uppercase tracking-widest whitespace-nowrap">Contact</a>
          </nav>

          {/* DESKTOP ONLY: Actions */}
          <div className="hidden xl:flex items-center gap-4 flex-shrink-0">
            <button 
              onClick={() => openChatWidget()}
              className="bg-primary hover:bg-opacity-90 text-white px-4 xl:px-6 py-3 text-xs xl:text-sm font-black uppercase rounded-sm transition-all shadow-md whitespace-nowrap"
            >
              Get Free Quote
            </button>
            <a 
              href="tel:+18326886779" 
              className="flex items-center gap-2 bg-accent border-2 border-accent text-white px-4 xl:px-5 py-2.5 rounded-sm font-black text-xs xl:text-sm hover:bg-transparent hover:text-accent transition-all shadow-md whitespace-nowrap"
            >
              <Phone size={14} className="fill-current" />
              <span className="font-bold">(832) 688-6779</span>
            </a>
          </div>

          {/* MOBILE ONLY: Hamburger Menu Button */}
          <div className="xl:hidden flex items-center justify-end ml-4">
            <button 
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="text-white p-2 focus:outline-none"
            >
              {isMenuOpen ? <X size={32} /> : <Menu size={32} />}
            </button>
          </div>

        </div>
      </div>

      {/* MOBILE DROPDOWN MENU */}
      {isMenuOpen && (
        <div className="xl:hidden bg-navy border-t border-white border-opacity-10 absolute top-full left-0 w-full shadow-2xl animate-fadeIn max-h-[calc(100vh-7rem)] overflow-y-auto">
          <nav className="flex flex-col text-sm font-black uppercase tracking-widest">
            <a 
              href="/" 
              className="block px-6 py-6 border-b border-white border-opacity-5 text-left hover:bg-primary transition-colors"
            >
              Home
            </a>
            
            {/* Services Mobile Dropdown */}
            <div className="flex flex-col border-b border-white border-opacity-5">
              <button 
                onClick={() => setIsServicesOpen(!isServicesOpen)}
                className="px-6 py-6 flex items-center justify-between text-left hover:bg-primary transition-colors"
              >
                Services <ChevronDown size={18} className={`transition-transform ${isServicesOpen ? 'rotate-180' : ''}`} />
              </button>
              {isServicesOpen && (
                <div className="bg-black/20 flex flex-col">
                  <a href="/water-damage" className="block px-10 py-5 border-b border-white border-opacity-5 text-left text-xs hover:text-primary transition-colors">Water Damage Restoration</a>
                  <a href="/sewage-backup" className="block px-10 py-5 border-b border-white border-opacity-5 text-left text-xs hover:text-primary transition-colors">Sewage Backup and Cleanup</a>
                  <a href="/mold-remediation" className="block px-10 py-5 border-b border-white border-opacity-5 text-left text-xs hover:text-primary transition-colors">Mold Removal</a>
                  <a href="/water-softener" className="block px-10 py-5 border-b border-white border-opacity-5 text-left text-xs hover:text-primary transition-colors">Water Softener Solutions</a>
                  <a href="/hot-water" className="block px-10 py-5 text-left text-xs hover:text-primary transition-colors">Hot Water Installation</a>
                </div>
              )}
            </div>

            <a 
              href="/gallery" 
              className="block px-6 py-6 border-b border-white border-opacity-5 text-left hover:bg-primary transition-colors"
            >
              Gallery
            </a>
            
            {/* Service Areas Mobile Dropdown */}
            <div className="flex flex-col border-b border-white border-opacity-5">
              <button 
                onClick={() => setIsMobileAreasOpen(!isMobileAreasOpen)}
                className="px-6 py-6 flex items-center justify-between text-left hover:bg-primary transition-colors"
              >
                Service Areas <ChevronDown size={18} className={`transition-transform ${isMobileAreasOpen ? 'rotate-180' : ''}`} />
              </button>
              {isMobileAreasOpen && (
                <div className="bg-black/20 flex flex-col">
                  {areas.map((area, idx) => (
                    <div 
                      key={idx} 
                      className={`px-10 py-4 text-xs font-bold tracking-widest ${idx !== areas.length - 1 ? 'border-b border-white border-opacity-5' : ''}`}
                    >
                      {area}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Resources Mobile Dropdown */}
            <div className="flex flex-col border-b border-white border-opacity-5">
              <button 
                onClick={() => setIsResourcesOpen(!isResourcesOpen)}
                className="px-6 py-6 flex items-center justify-between text-left hover:bg-primary transition-colors"
              >
                Resources <ChevronDown size={18} className={`transition-transform ${isResourcesOpen ? 'rotate-180' : ''}`} />
              </button>
              {isResourcesOpen && (
                <div className="bg-black/20 flex flex-col">
                  <a href="/blog" className="block px-10 py-5 border-b border-white border-opacity-5 text-left text-xs hover:text-primary transition-colors">Blog</a>
                  <a href="/careers" className="block px-10 py-5 text-left text-xs hover:text-primary transition-colors">Careers</a>
                </div>
              )}
            </div>

            <a 
              href="/contact"
              className="block px-6 py-6 text-left hover:bg-primary transition-colors"
            >
              Contact
            </a>

            <div className="p-6 bg-black/20">
               <button 
                 onClick={() => openChatWidget()}
                 className="w-full bg-primary py-4 rounded-sm shadow-xl font-black mb-4"
               >
                 GET FREE QUOTE
               </button>
               <a 
                 href="tel:+18326886779"
                 className="w-full flex items-center justify-center gap-3 bg-accent py-4 rounded-sm shadow-xl font-black"
               >
                 <Phone size={20} className="fill-current" /> (832) 688-6779
               </a>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
};

export default Header;

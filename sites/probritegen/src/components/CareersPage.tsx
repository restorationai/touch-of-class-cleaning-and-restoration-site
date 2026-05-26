import React from 'react';
import { MapPin, Download } from 'lucide-react';

const CareersPage: React.FC = () => {
  const bgImage = "/media/6976c78bc1fa0c9f59a78f69.webp";

  return (
    <div className="flex flex-col">
      {/* Hero Section */}
      <section className="relative min-h-[600px] flex items-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={bgImage} alt="Careers background" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/50"></div>
        </div>
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 relative z-10 w-full py-20 mt-10">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center">
            
            {/* Left Column Content */}
            <div className="text-white flex flex-col items-center lg:items-start text-center lg:text-left w-full">
              <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-black uppercase mb-6 lg:mb-10 leading-[1.1] tracking-tighter drop-shadow-[0_4px_4px_rgba(0,0,0,0.8)]">
                <span className="block whitespace-nowrap">ProBrite Gen</span>
                <span className="block">Careers</span>
              </h1>
              <div className="max-w-xl lg:max-w-2xl flex flex-col items-center lg:items-start space-y-6 lg:space-y-8">
                <p className="text-xl sm:text-2xl md:text-3xl opacity-100 leading-relaxed font-bold drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
                  Join the ProBrite Gen Network
                </p>
                <div className="inline-block border-b-2 border-white pb-1">
                  <span className="text-lg sm:text-xl font-black uppercase tracking-widest text-white">Houston, TX</span>
                </div>
              </div>
            </div>

            {/* Right Column Content - Apply Box */}
            <div className="w-full flex justify-center lg:justify-end mt-12 lg:mt-0">
              <div className="flex flex-col items-center justify-center w-full max-w-md border-2 border-white/80 p-8 sm:p-10 rounded-sm bg-black/40 backdrop-blur-md shadow-2xl text-center space-y-6">
                <h3 className="text-3xl font-black uppercase text-white tracking-tight leading-tight">Ready to join the team?</h3>
                <p className="text-lg font-medium text-white/90 leading-relaxed">
                  Submit your resume and a brief description of your restoration experience.
                </p>
                
                <div className="w-full pt-4">
                  <a 
                    href="/media/application-1099.pdf" 
                    download
                    className="w-full inline-flex justify-center items-center gap-3 bg-primary text-white py-5 px-6 font-black uppercase tracking-widest rounded-sm shadow-xl hover:bg-opacity-90 transition-all text-xl group"
                  >
                    <Download className="group-hover:-translate-y-1 transition-transform" size={24} />
                    Apply Now
                  </a>
                  <p className="mt-4 text-xs font-bold text-white/80 uppercase tracking-widest">
                    Download PDF Application
                  </p>
                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* Body Section */}
      <section className="bg-white py-24">
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12">
          <div className="max-w-4xl mx-auto space-y-16">
            
            {/* Job Title & Overview */}
            <div className="border-b-2 border-navy/10 pb-12 text-center md:text-left">
              <h2 className="text-4xl md:text-5xl font-black uppercase mb-6 text-navy tracking-tight">
                1099 Field Water Restoration Technician
              </h2>
              <div className="flex flex-col space-y-3 text-lg md:text-xl font-bold text-gray-800 uppercase tracking-wide">
                <p>Independent Contractor Field-Based · Houston, TX Area Flexible Schedule</p>
                <p>Water Restoration · 1099 Contract · Vehicle Required</p>
                <p className="text-primary text-2xl mt-4">$35+ / hour · based on experience & certifications</p>
              </div>
            </div>

            {/* About the role */}
            <div>
              <h3 className="text-3xl font-black uppercase mb-6 text-navy">About the role</h3>
              <p className="text-lg md:text-xl font-medium text-gray-700 leading-relaxed">
                ProBrite Gen is a trusted leader in water damage mitigation and restoration. As demand for our services grows, we're expanding our network of independent field technicians. In this role, you'll respond to water damage events across the service area, execute mitigation protocols, and represent ProBrite Gen's commitment to quality and speed. All equipment and materials are provided — you bring the expertise and the wheels.
              </p>
            </div>

            {/* What you'll do */}
            <div>
              <h3 className="text-3xl font-black uppercase mb-6 text-navy">What you'll do</h3>
              <ul className="list-disc pl-6 space-y-3 text-lg md:text-xl font-medium text-gray-700">
                <li>Respond to residential and commercial water damage calls</li>
                <li>Set up and monitor drying equipment (air movers, dehumidifiers)</li>
                <li>Conduct moisture mapping and document affected areas</li>
                <li>Perform water extraction and structural dry-out procedures</li>
                <li>Communicate job progress and document daily readings</li>
                <li>Transport and secure company-provided materials in your vehicle</li>
                <li>Follow IICRC standards and ProBrite Gen protocols</li>
              </ul>
            </div>

            {/* Requirements */}
            <div>
              <h3 className="text-3xl font-black uppercase mb-6 text-navy">Requirements</h3>
              <ul className="list-disc pl-6 space-y-3 text-lg md:text-xl font-medium text-gray-700">
                <li>Minimum 1 year hands-on water restoration / mitigation experience</li>
                <li>Must own or operate a cargo van or full-size covered truck bed</li>
                <li>Active IICRC WRT (Water Restoration Technician) certification</li>
                <li>Active IICRC ASD (Applied Structural Drying) certification</li>
                <li>Active general liability insurance policy</li>
                <li>Valid driver's license and clean driving record</li>
                <li>Ability to lift up to 50 lbs and work in confined or wet spaces</li>
                <li>Strong communication and professional customer-facing skills</li>
                <li>Smartphone with ability to use job management apps</li>
              </ul>
            </div>

            {/* Preferred qualifications */}
            <div>
              <h3 className="text-3xl font-black uppercase mb-6 text-navy">Preferred qualifications</h3>
              <ul className="list-disc pl-6 space-y-3 text-lg md:text-xl font-medium text-gray-700">
                <li>Additional IICRC certifications (FSRT, AMRT, or similar)</li>
                <li>Experience with Xactimate or similar estimating/documentation software</li>
                <li>Prior work with restoration companies, insurance claims, or emergency response</li>
                <li>Bilingual (English/Spanish) is a plus</li>
              </ul>
            </div>

            {/* Contractor details */}
            <div>
              <h3 className="text-3xl font-black uppercase mb-6 text-navy">Contractor details</h3>
              <ul className="list-disc pl-6 space-y-3 text-lg md:text-xl font-medium text-gray-700">
                <li>This is a 1099 independent contractor position — you are responsible for your own taxes</li>
                <li>All drying equipment, materials, and supplies are furnished by ProBrite Gen</li>
                <li>Pay starts at $35/hour and increases based on certifications and performance</li>
                <li>Flexible scheduling — work the jobs that fit your availability</li>
                <li>Opportunity for consistent, high-volume work as our primary service partner</li>
              </ul>
            </div>

            {/* Apply Now Section */}
            <div className="mt-20 pt-16 border-t-2 border-navy/10 text-center">
              <h3 className="text-4xl font-black uppercase mb-6 text-navy tracking-tight">Ready to join the team?</h3>
              <p className="text-xl md:text-2xl font-bold text-gray-700 leading-relaxed mb-10 max-w-2xl mx-auto">
                Submit your resume and a brief description of your restoration experience.
              </p>
              
              <a 
                href="/media/application-1099.pdf" 
                download
                className="inline-flex items-center gap-3 bg-primary text-white py-6 px-10 font-black uppercase text-center tracking-widest rounded-sm shadow-2xl hover:bg-opacity-90 transition-all text-2xl group"
              >
                <Download className="group-hover:-translate-y-1 transition-transform" size={28} />
                Apply Now
              </a>
              <p className="mt-4 text-sm font-medium text-gray-500 opacity-80 uppercase tracking-widest">
                Download PDF Application
              </p>
            </div>

          </div>
        </div>
      </section>

      {/* Proudly Serving Section */}
      <section className="bg-navy py-32 text-white border-t border-white border-opacity-10">
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 flex flex-col items-center">
          <h2 className="text-6xl md:text-7xl font-black uppercase tracking-tighter mb-20 text-center">
            PROUDLY SERVING
          </h2>
          <div className="w-full grid grid-cols-1 md:grid-cols-1 lg:grid-cols-1 gap-y-10 gap-x-32 max-w-4xl text-center">
            <div className="flex items-center justify-center gap-6 text-2xl font-black uppercase tracking-[0.1em] group border-b border-white border-opacity-5 pb-4">
              <MapPin size={32} className="text-primary group-hover:scale-125 transition-transform duration-300" />
              <span className="group-hover:text-primary transition-colors">Houston, TX & Surrounding Cities</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default CareersPage;

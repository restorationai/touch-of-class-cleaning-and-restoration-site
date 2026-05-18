
import React from 'react';

const About: React.FC = () => {
  const logoUrl = "/media/69cd6fb6ddfdcb063981acc7.png";

  return (
    <section className="bg-navy py-24 text-white overflow-hidden relative">
      <div className="max-w-[1400px] mx-auto px-6 sm:px-10 lg:px-12">
        <div className="grid lg:grid-cols-2 gap-20 items-center">
          <div>
            <div className="flex items-center gap-6 mb-8">
              <h2 className="text-5xl md:text-6xl font-black uppercase tracking-tighter">About Us</h2>
              <div className="flex-grow h-px bg-white/30"></div>
            </div>
            
            <p className="text-xl opacity-90 leading-relaxed mb-10 font-medium">
              ProBrite Gen is a premier restoration company dedicated to serving both residential and commercial clients in Houston, TX. 
              We specialize in returning properties to their pre-loss condition after water or mold damage, as well as providing expert water softener and hot water solutions. 
              Our team of professionals is committed to providing reliable, high-quality service to ensure 
              your property is restored safely and efficiently, helping our community recover when it matters most.
            </p>
          </div>

          <div className="relative flex justify-center items-center">
             <img 
               src={logoUrl} 
               alt="ProBrite Gen Logo" 
               className="w-full max-w-[280px] md:max-w-[400px] h-auto object-contain drop-shadow-[0_20px_20px_rgba(0,0,0,0.4)] opacity-100"
             />
          </div>
        </div>
      </div>
    </section>
  );
};

export default About;

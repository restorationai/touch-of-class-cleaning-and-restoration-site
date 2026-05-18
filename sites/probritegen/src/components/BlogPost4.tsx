
import React from 'react';
import Process from './Process';
import ServiceAreas from './ServiceAreas';
import FinalCTA from './FinalCTA';



const BlogPost4: React.FC = () => {
  const bgImage = "/media/6976c78bc1fa0c9f59a78f69.png";

  return (
    <div className="flex flex-col">
      {/* 1. Hero Section */}
      <section className="relative min-h-[600px] flex items-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={bgImage} alt="Smoke Damage background" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/40"></div>
        </div>
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 relative z-10 w-full text-center text-white py-20">
          <div className="inline-block bg-black px-4 py-2 mb-6 shadow-xl">
            <span className="text-xs font-black uppercase tracking-[0.2em]">BLOG</span>
          </div>
          <h1 className="text-4xl md:text-7xl font-black uppercase mb-8 leading-[1.1] tracking-tighter drop-shadow-2xl max-w-5xl mx-auto">
            Signs Your Hot Water Heater Needs Professional Attention
          </h1>
          <div className="flex flex-col items-center gap-2 mt-12 animate-bounce">
            <div className="w-1 h-12 bg-white opacity-40"></div>
            <div className="w-4 h-4 border-r-4 border-b-4 border-white rotate-45 opacity-60"></div>
            <div className="w-4 h-4 border-r-4 border-b-4 border-white rotate-45 opacity-40"></div>
          </div>
        </div>
      </section>

      {/* 2. Blog Body Content */}
      <section className="bg-white py-24">
        <div className="max-w-[1000px] mx-auto px-6 sm:px-12">
          <div className="space-y-12 text-gray-800">
            <div className="space-y-4">
              <h2 className="text-2xl font-black text-navy uppercase tracking-tight">
                Introduction
              </h2>
              <p className="text-lg leading-relaxed opacity-90">
                Your hot water heater is one of the most important appliances in your home, providing comfort and convenience for daily tasks like showering, dishwashing, and laundry. However, like any mechanical system, it can develop problems over time. Recognizing the early warning signs of a failing water heater can help you avoid a sudden cold shower or a costly flood. This post outlines the common indicators that your hot water heater needs professional attention and why you shouldn't ignore them. ProBrite Gen is here to provide expert diagnostics and repairs.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Fluctuating Water Temperatures
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                If your water suddenly goes from hot to cold or takes much longer than usual to heat up, it's a clear sign that something is wrong. This could be due to a failing heating element, a faulty thermostat, or a buildup of sediment in the tank. Sediment can act as an insulator, making it harder for the heater to warm the water efficiently. A professional can diagnose the exact cause and recommend the necessary repairs or a replacement if the unit is near the end of its lifespan.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Strange Noises from the Tank
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Loud popping, banging, or rumbling noises coming from your water heater are often caused by sediment buildup at the bottom of the tank. As the water heats up, air bubbles can get trapped under the layer of sediment and pop, creating these alarming sounds. Over time, this can lead to overheating and damage the tank's structure. Flushing the tank may resolve the issue, but persistent noises often indicate that a more thorough inspection or repair is needed.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Discolored or Rusty Water
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                If the hot water coming from your faucets looks rusty, brown, or cloudy, it could be a sign of corrosion inside your water heater tank. While some discoloration can be caused by old pipes, if it only happens with hot water, the heater is likely the source. Corrosion can eventually lead to leaks and a complete tank failure. A professional can determine if the tank's sacrificial anode rod needs replacement or if the entire unit has reached its limit.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Visible Leaks or Moisture Around the Base
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Any sign of water pooling around the base of your water heater is a serious concern. Leaks can occur from valves, connections, or the tank itself. Even a small drip can lead to significant water damage and mold growth if left unaddressed. If you notice moisture, it's crucial to call a professional immediately. They can identify the source of the leak and determine if it's a simple fix or if the tank has developed a crack that requires a full replacement.
              </p>
            </div>

            <div className="space-y-4">
              <h2 className="text-2xl font-black text-navy uppercase tracking-tight">
                Conclusion
              </h2>
              <p className="text-lg leading-relaxed opacity-90">
                Being proactive about your hot water heater's health can save you from unexpected breakdowns and expensive repairs. By paying attention to temperature changes, unusual noises, water quality, and visible leaks, you can catch problems early and extend the life of your unit. If you're experiencing any of these issues, don't wait for a major failure. ProBrite Gen offers reliable hot water heater services, including diagnostics, repairs, and professional installations. Contact us today to ensure your home's hot water system is running safely and efficiently.
              </p>
            </div>
          </div>
        </div>
      </section>
      <Process />
      <div className="bg-navy border-t border-white border-opacity-10 py-1"></div>
      <ServiceAreas />
      <FinalCTA />
    </div>
  );
};

export default BlogPost4;

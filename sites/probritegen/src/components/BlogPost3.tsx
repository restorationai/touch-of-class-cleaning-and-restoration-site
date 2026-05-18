
import React from 'react';
import Process from './Process';
import ServiceAreas from './ServiceAreas';
import FinalCTA from './FinalCTA';



const BlogPost3: React.FC = () => {
  const bgImage = "/media/6976c78bc1fa0c9f59a78f69.png";

  return (
    <div className="flex flex-col">
      {/* 1. Hero Section */}
      <section className="relative min-h-[600px] flex items-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={bgImage} alt="Fire Damage background" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/40"></div>
        </div>
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 relative z-10 w-full text-center text-white py-20">
          <div className="inline-block bg-black px-4 py-2 mb-6 shadow-xl">
            <span className="text-xs font-black uppercase tracking-[0.2em]">BLOG</span>
          </div>
          <h1 className="text-4xl md:text-7xl font-black uppercase mb-8 leading-[1.1] tracking-tighter drop-shadow-2xl max-w-5xl mx-auto">
            The Benefits of Installing a Water Softener in Houston
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
                Houston's water is known for being hard, meaning it contains high levels of minerals like calcium and magnesium. While not harmful to your health, hard water can take a toll on your home's plumbing, appliances, and even your skin and hair. Installing a water softener is a smart investment that can save you money and improve your quality of life. This post explores the many benefits of water softening and why it's a popular choice for Houston homeowners. ProBrite Gen is here to help you find the right water softener solution for your needs.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Protect Your Plumbing and Appliances
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Hard water causes mineral buildup, or scale, inside your pipes and appliances. Over time, this scale can restrict water flow, lead to clogs, and cause appliances like dishwashers, washing machines, and water heaters to work harder and fail sooner. A water softener removes these minerals before they enter your home's system, extending the lifespan of your plumbing and expensive appliances. This means fewer repairs and replacements, saving you significant money in the long run.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Softer Skin and Healthier Hair
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                If you've noticed that your skin feels dry and itchy or your hair looks dull and brittle after showering, hard water might be the culprit. The minerals in hard water can strip away natural oils and leave a residue on your skin and hair. Softened water allows soaps and shampoos to lather more effectively and rinse away completely, leaving your skin feeling smoother and your hair looking healthier and more vibrant.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Cleaner Dishes and Brighter Laundry
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                Hard water often leaves spots on glassware and a film on dishes, even after a full wash cycle. It can also cause clothes to look dingy and feel stiff. Soft water works better with detergents, meaning you'll need less soap to get better results. Your dishes will come out sparkling clean, and your laundry will stay brighter and feel softer for longer. Plus, you'll spend less time scrubbing mineral deposits off your showerheads and faucets.
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-black text-navy uppercase tracking-tight">
                Energy Efficiency and Cost Savings
              </h3>
              <p className="text-lg leading-relaxed opacity-90">
                When scale builds up in your water heater, it acts as an insulator, requiring more energy to heat the water. By preventing this buildup, a water softener helps your water heater operate more efficiently, which can lead to lower energy bills. Additionally, because soft water requires less soap and detergent, you'll save money on cleaning supplies over time. The initial investment in a water softener often pays for itself through these various savings.
              </p>
            </div>

            <div className="space-y-4">
              <h2 className="text-2xl font-black text-navy uppercase tracking-tight">
                Conclusion
              </h2>
              <p className="text-lg leading-relaxed opacity-90">
                Installing a water softener in your Houston home offers numerous advantages, from protecting your plumbing and appliances to improving your personal care routine and saving you money. It's a simple solution to a common problem that can make a big difference in your daily life. If you're ready to experience the benefits of soft water, ProBrite Gen can provide expert installation and maintenance services. Contact us today to learn more about our water softener solutions and how we can help you enjoy cleaner, softer water throughout your home.
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

export default BlogPost3;

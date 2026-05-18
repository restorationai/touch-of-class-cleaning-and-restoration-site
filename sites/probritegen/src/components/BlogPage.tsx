
import React from 'react';
import { ChevronRight } from 'lucide-react';
import Process from './Process';
import ServiceAreas from './ServiceAreas';
import FinalCTA from './FinalCTA';



const BlogPage: React.FC = () => {
  const bgImage = "/media/6976c78bc1fa0c9f59a78f69.png";

  const blogs = [
    {
      id: 'blog-post-1' as const,
      headline: "What to Do Immediately After Water Damage in Your Home",
      description: "Water damage can spread quickly and cause serious problems if not handled right away. This guide explains the first steps to take after water damage to help protect your property and reduce long-term issues."
    },
    {
      id: 'blog-post-2' as const,
      headline: "Common Causes of Water Damage and How to Prevent Them",
      description: "Water damage often starts from everyday issues like leaks, broken pipes, or appliance failures. Learn about the most common causes of water damage and simple ways to help prevent them."
    },
    {
      id: 'blog-post-3' as const,
      headline: "The Benefits of Installing a Water Softener in Houston",
      description: "Hard water can cause buildup in pipes and damage appliances. This article explains how a water softener can improve your water quality and protect your home's plumbing system."
    },
    {
      id: 'blog-post-4' as const,
      headline: "Signs Your Hot Water Heater Needs Professional Attention",
      description: "A failing water heater can lead to leaks and cold showers. Learn about the common signs that it's time for a professional hot water installation or repair."
    },
    {
      id: 'blog-post-5' as const,
      headline: "What Causes Mold Growth After Water Damage",
      description: "Mold often grows when moisture is left behind after water damage. This blog explains how mold develops, where it commonly appears, and why early action is important."
    },
    {
      id: 'blog-post-6' as const,
      headline: "Signs You May Need Professional Mold Remediation",
      description: "Mold is not always easy to see. Learn about common signs of mold growth and when it may be time to contact a professional to help address the problem safely."
    }
  ];

  return (
    <div className="flex flex-col">
      {/* 1. Hero Section */}
      <section className="relative min-h-[600px] flex items-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={bgImage} alt="Blog background" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/40"></div>
        </div>
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 relative z-10 w-full text-center text-white py-20">
          <h1 className="text-3xl xs:text-4xl sm:text-5xl md:text-7xl font-black uppercase mb-8 leading-tight tracking-tighter drop-shadow-2xl whitespace-nowrap">
            CHECK OUT OUR BLOG
          </h1>
          
          {/* Bouncing Arrow Indicator */}
          <div className="flex flex-col items-center gap-2 mt-12 animate-bounce">
            <div className="w-1 h-12 bg-white opacity-40"></div>
            <div className="w-4 h-4 border-r-4 border-b-4 border-white rotate-45 opacity-60"></div>
            <div className="w-4 h-4 border-r-4 border-b-4 border-white rotate-45 opacity-40"></div>
          </div>
        </div>
      </section>

      {/* 2. Blog Grid Section */}
      <section className="bg-navy py-24">
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {blogs.map((blog, idx) => (
              <div 
                key={idx} 
                className="bg-white rounded-md p-10 flex flex-col h-full shadow-2xl transition-transform hover:-translate-y-1"
              >
                <h2 className="text-2xl md:text-3xl font-black uppercase mb-6 leading-tight tracking-tight text-navy">
                  {blog.headline}
                </h2>
                <p className="text-gray-600 text-lg leading-relaxed mb-10 flex-grow">
                  {blog.description}
                </p>
                
                <button 
                  onClick={() => blog.id && onNavigate(blog.id)}
                  className={`group flex items-center gap-3 font-black uppercase text-lg tracking-wider w-fit ${blog.id ? 'text-accent cursor-pointer' : 'text-gray-300 cursor-default opacity-50'}`}
                >
                  <span>READ FULL POST</span>
                  <div className={`rounded-full border-2 p-1 flex items-center justify-center transition-colors ${blog.id ? 'border-accent group-hover:bg-accent group-hover:text-white' : 'border-gray-300'}`}>
                    <ChevronRight size={20} strokeWidth={4} />
                  </div>
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 3. Re-used Page Content Sections */}
      <Process />
      <div className="bg-navy border-t border-white border-opacity-10 py-1"></div>
      <ServiceAreas />
      <FinalCTA />
    </div>
  );
};

export default BlogPage;

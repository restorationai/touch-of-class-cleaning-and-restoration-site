
import React from 'react';
import Hero from './Hero';
import TrustStrip from './TrustStrip';
import About from './About';
import Services from './Services';
import Process from './Process';
import Gallery from './Gallery';
import FAQ from './FAQ';
import ServiceAreas from './ServiceAreas';
import FinalCTA from './FinalCTA';



const HomePage: React.FC = () => {
  return (
    <>
      <Hero />
      <TrustStrip />
      <About />
      <Services />
      <Process />
      <Gallery />
      <FAQ />
      <ServiceAreas />
      <FinalCTA />
    </>
  );
};

export default HomePage;

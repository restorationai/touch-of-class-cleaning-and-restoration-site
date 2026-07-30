// Real client testimonial videos — uploaded to the client's own YouTube
// channel 2026-07-30 (source: their previous website's video library).
// Keep summaries testimonial-framed: no invented job details.
export interface CaseStudy {
  slug: string;
  videoId: string;
  title: string;
  person: string;
  summary: string;
  relatedService: { label: string; path: string };
}

export const caseStudies: CaseStudy[] = [
  {
    slug: "vandenberg-senior-residence",
    videoId: "lR15NyTxeaM",
    title: "Vandenberg Senior Residence Restoration",
    person: "Vandenberg Senior Residence",
    summary:
      "How our team handled restoration work at a senior residence near Vandenberg — the kind of job where careful containment, clear communication with facility staff, and respect for residents matter as much as the technical work.",
    relatedService: { label: "Water Damage Restoration", path: "/services/water-damage-restoration/" },
  },
  {
    slug: "david-prochaska",
    videoId: "7Hmy0a7qki4",
    title: "David Prochaska's Experience",
    person: "David Prochaska",
    summary:
      "David shares what it was like working with Coastal Restoration Services from the first call through the finished job.",
    relatedService: { label: "Water Damage Restoration", path: "/services/water-damage-restoration/" },
  },
  {
    slug: "bernie-baggarly",
    videoId: "F2xmHkI1J2w",
    title: "Bernie Baggarly's Experience",
    person: "Bernie Baggarly",
    summary:
      "Bernie talks about the crew, the communication, and why he'd recommend Coastal Restoration Services to his neighbors.",
    relatedService: { label: "Mold Remediation", path: "/services/mold-remediation/" },
  },
  {
    slug: "stephanie-vega",
    videoId: "sfwYc4FkHsU",
    title: "Stephanie Vega's Experience",
    person: "Stephanie Vega",
    summary:
      "Stephanie describes how the team treated her home and family during a stressful cleanup.",
    relatedService: { label: "Sewage Cleanup & Remediation", path: "/services/sewage-cleanup/" },
  },
  {
    slug: "monica",
    videoId: "zC16cXqKuDY",
    title: "Monica's Experience",
    person: "Monica",
    summary:
      "Monica shares her experience with our technicians and how the job got done right the first time.",
    relatedService: { label: "Fire & Smoke Restoration", path: "/services/fire-damage-restoration/" },
  },
];

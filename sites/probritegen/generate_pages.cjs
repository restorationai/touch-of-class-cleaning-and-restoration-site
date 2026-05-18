const fs = require('fs');
const path = require('path');

const pagesDir = path.join(__dirname, 'src', 'pages');
if (!fs.existsSync(pagesDir)) {
  fs.mkdirSync(pagesDir, { recursive: true });
}

const pages = [
  { file: 'index.astro', component: 'HomePage', title: 'Home | ProBrite Gen' },
  { file: 'water-damage.astro', component: 'WaterDamagePage', title: 'Water Damage Restoration | ProBrite Gen' },
  { file: 'sewage-backup.astro', component: 'SewageBackupPage', title: 'Sewage Backup Cleanup | ProBrite Gen' },
  { file: 'mold-remediation.astro', component: 'MoldRemediationPage', title: 'Mold Removal | ProBrite Gen' },
  { file: 'water-softener.astro', component: 'WaterSoftenerPage', title: 'Water Softener Solutions | ProBrite Gen' },
  { file: 'hot-water.astro', component: 'HotWaterPage', title: 'Hot Water Installation | ProBrite Gen' },
  { file: 'gallery.astro', component: 'GalleryPage', title: 'Gallery | ProBrite Gen' },
  { file: 'contact.astro', component: 'ContactPage', title: 'Contact Us | ProBrite Gen' },
  { file: 'blog.astro', component: 'BlogPage', title: 'Blog | ProBrite Gen' },
  { file: 'careers.astro', component: 'CareersPage', title: 'Careers | ProBrite Gen' },
  { file: 'blog-post-1.astro', component: 'BlogPost1', title: 'Understanding Water Damage Classes & Categories | ProBrite Gen' },
  { file: 'blog-post-2.astro', component: 'BlogPost2', title: 'The Hidden Dangers of Untreated Sewage Backups | ProBrite Gen' },
  { file: 'blog-post-3.astro', component: 'BlogPost3', title: '5 Signs Your Home Needs a Water Softener | ProBrite Gen' },
  { file: 'blog-post-4.astro', component: 'BlogPost4', title: 'Why Mold Remediation Can’t Wait | ProBrite Gen' },
  { file: 'blog-post-5.astro', component: 'BlogPost5', title: 'Tank vs. Tankless Water Heaters: Which is Right for You? | ProBrite Gen' },
  { file: 'blog-post-6.astro', component: 'BlogPost6', title: 'Preparing Your Home for Houston’s Hurricane Season | ProBrite Gen' }
];

pages.forEach(p => {
  const content = `---
import Layout from '../layouts/Layout.astro';
import ${p.component} from '../components/${p.component}';
---

<Layout title="${p.title}">
  <${p.component} client:load />
</Layout>
`;
  fs.writeFileSync(path.join(pagesDir, p.file), content, 'utf8');
});

console.log("Pages generated.");

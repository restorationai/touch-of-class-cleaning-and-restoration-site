const fs = require('fs');
const path = require('path');

const componentsDir = path.join(__dirname, 'src', 'components');
const files = fs.readdirSync(componentsDir).filter(f => f.endsWith('.tsx') && f !== 'Reviews.tsx');

for (const file of files) {
  const filePath = path.join(componentsDir, file);
  let content = fs.readFileSync(filePath, 'utf8');
  let changed = false;

  if (content.includes('import Reviews from')) {
    content = content.replace(/import\s+Reviews\s+from\s+['"]\.\/Reviews['"];?\n?/g, '');
    changed = true;
  }
  
  if (content.includes('<Reviews')) {
    content = content.replace(/\s*<Reviews\s*\/?>(?:<\/Reviews>)?/g, '');
    changed = true;
  }

  if (changed) {
    fs.writeFileSync(filePath, content, 'utf8');
  }
}

const reviewsFile = path.join(componentsDir, 'Reviews.tsx');
if (fs.existsSync(reviewsFile)) {
  fs.unlinkSync(reviewsFile);
}
console.log('Reviews removed.');

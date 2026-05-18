const fs = require('fs');
const path = require('path');

const componentsDir = path.join(__dirname, 'src', 'components');
const files = fs.readdirSync(componentsDir).filter(f => f.endsWith('.tsx') || f.endsWith('.astro'));

for (const file of files) {
  const filePath = path.join(componentsDir, file);
  let content = fs.readFileSync(filePath, 'utf8');
  let changed = false;

  // Fix Tailwind v4 opacity syntax
  // Replace `bg-black bg-opacity-40` with `bg-black/40`
  const regex = /bg-black\s+bg-opacity-(\d+)/g;
  if (regex.test(content)) {
    content = content.replace(regex, 'bg-black/$1');
    changed = true;
  }
  
  // also handle white
  const regexWhite = /bg-white\s+bg-opacity-(\d+)/g;
  if (regexWhite.test(content)) {
    content = content.replace(regexWhite, 'bg-white/$1');
    changed = true;
  }

  if (changed) {
    fs.writeFileSync(filePath, content, 'utf8');
  }
}

console.log('Opacity classes fixed.');

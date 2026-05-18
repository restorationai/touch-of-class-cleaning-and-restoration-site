const fs = require('fs');
const path = require('path');

const componentsDir = path.join(__dirname, 'src', 'components');
const files = fs.readdirSync(componentsDir).filter(f => f.endsWith('.tsx'));

for (const file of files) {
  const filePath = path.join(componentsDir, file);
  let content = fs.readFileSync(filePath, 'utf8');
  let changed = false;

  if (content.includes('isQuoteModalOpen')) {
    content = content.replace(/import { isQuoteModalOpen } from '\.\.\/store';/g, "import { openChatWidget } from '../store';");
    content = content.replace(/isQuoteModalOpen\.set\(true\)/g, 'openChatWidget()');
    changed = true;
  }

  if (changed) {
    fs.writeFileSync(filePath, content, 'utf8');
  }
}
console.log('Done.');

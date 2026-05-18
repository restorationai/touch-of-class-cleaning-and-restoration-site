const fs = require('fs');
const path = require('path');

const componentsDir = path.join(__dirname, 'src', 'components');
const files = fs.readdirSync(componentsDir).filter(f => f.endsWith('.tsx'));

files.forEach(file => {
  const filePath = path.join(componentsDir, file);
  let content = fs.readFileSync(filePath, 'utf8');

  // 1. Remove props interfaces and arguments
  content = content.replace(/interface\s+\w+Props\s*{[^}]*}/g, (match) => {
    return match.replace(/onOpenQuote\??:\s*\(\)\s*=>\s*void;/g, '')
                .replace(/onNavigate\??:\s*\(page:\s*PageType\)\s*=>\s*void;/g, '');
  });
  content = content.replace(/interface\s+\w+Props\s*{\s*}/g, '');

  content = content.replace(/:\s*React\.FC(?:<\w+Props>)?\s*=\s*\(\{\s*([^}]+)\s*\}\)/g, (match, propsGroup) => {
    let newProps = propsGroup.replace(/onOpenQuote/g, '').replace(/onNavigate/g, '').replace(/,\s*,/g, ',').replace(/^,\s*|\s*,$/g, '');
    if (!newProps.trim()) return ': React.FC = ()';
    return match.replace(propsGroup, newProps);
  });
  content = content.replace(/:\s*React\.FC<\w+Props>\s*=\s*\(\)/g, ': React.FC = ()');

  // 2. Remove prop passing in JSX
  content = content.replace(/\s*onOpenQuote={onOpenQuote}/g, '');
  content = content.replace(/\s*onNavigate={onNavigate}/g, '');

  // 3. Replace onOpenQuote with nanostore update
  if (content.includes('onOpenQuote')) {
    if (!content.includes('import { isQuoteModalOpen }')) {
      content = "import { isQuoteModalOpen } from '../store';\n" + content;
    }
    content = content.replace(/onClick={onOpenQuote}/g, 'onClick={() => isQuoteModalOpen.set(true)}');
    content = content.replace(/onOpenQuote\(\)/g, 'isQuoteModalOpen.set(true)');
  }

  // 4. Replace onNavigate
  content = content.replace(/onNavigate\??\(\s*'([^']+)'\s*\)/g, "window.location.href = '/$1'");
  content = content.replace(/window\.location\.href\s*=\s*'\/home'/g, "window.location.href = '/'");

  // Fix App and PageType imports
  content = content.replace(/import\s*{\s*PageType\s*}\s*from\s*'[^']+';?\n?/g, '');

  fs.writeFileSync(filePath, content, 'utf8');
});

console.log("Refactoring complete.");

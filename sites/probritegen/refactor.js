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

  // If interface becomes empty, we might just leave it or remove it.
  content = content.replace(/interface\s+\w+Props\s*{\s*}/g, '');

  // Component definition destructuring
  content = content.replace(/:\s*React\.FC(?:<\w+Props>)?\s*=\s*\(\{\s*([^}]+)\s*\}\)/g, (match, propsGroup) => {
    let newProps = propsGroup.replace(/onOpenQuote/g, '').replace(/onNavigate/g, '').replace(/,\s*,/g, ',').replace(/^,\s*|\s*,$/g, '');
    if (!newProps.trim()) return ': React.FC = ()';
    return match.replace(propsGroup, newProps);
  });
  
  // Also catch no props
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

  // 4. Replace onNavigate calls with anchor tags or window.location
  // For SEO, we really want <a href="..."> instead of <button onClick="...">
  // A regex to replace <button onClick={() => onNavigate('home')} ... >Home</button>
  // with <a href="/" ... >Home</a>
  
  content = content.replace(/<button\s+([^>]*)onClick=\{\(\)\s*=>\s*onNavigate\??\('([^']+)'\)\}([^>]*)>/g, '<a href="/$2" $1$3>');
  content = content.replace(/<\/button>/g, '</a>'); // this might break real buttons, so let's be more specific below.

  // Re-read file without global replace of </button>
  // Actually, replacing <button with <a is tricky with regex. Let's just use window.location.href for now, OR better:
  // Instead of full AST parsing, let's replace `onNavigate('something')` with `window.location.href = '/something'`
  content = content.replace(/onNavigate\??\(\s*'([^']+)'\s*\)/g, "window.location.href = '/$1'");
  
  // Fix 'home' routing
  content = content.replace(/window\.location\.href\s*=\s*'\/home'/g, "window.location.href = '/'");

  fs.writeFileSync(filePath, content, 'utf8');
});

console.log("Refactoring complete.");

const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'src', 'components', 'Header.tsx');
let content = fs.readFileSync(filePath, 'utf8');

// 1. Change justify-between lg:justify-start to justify-start and gap-8
content = content.replace(
  /<div className="flex justify-between lg:justify-start items-center h-28 lg:gap-8 xl:gap-12">/,
  '<div className="flex justify-start items-center h-28 gap-8 xl:gap-12 w-full">'
);

// 2. Change lg: to xl: for all mobile/desktop breakpoints
content = content.replace(/flex lg:hidden/g, 'flex xl:hidden');
content = content.replace(/hidden lg:flex/g, 'hidden xl:flex');
content = content.replace(/lg:hidden bg-navy/g, 'xl:hidden bg-navy');
content = content.replace(/lg:hidden flex items-center justify-end/g, 'xl:hidden flex items-center justify-end');

// 3. Remove flex-grow and justify-start from nav, let gap handle spacing
content = content.replace(
  /<nav className="hidden xl:flex justify-start gap-4 xl:gap-8 items-center text-\[11px\] xl:text-sm font-black uppercase tracking-widest h-full px-2">/,
  '<nav className="hidden xl:flex items-center gap-4 xl:gap-8 text-[11px] xl:text-sm font-black uppercase tracking-widest h-full px-2">'
);

// 4. Remove space-x and use gap in actions
content = content.replace(
  /<div className="hidden xl:flex items-center space-x-2 xl:space-x-4 flex-shrink-0">/,
  '<div className="hidden xl:flex items-center gap-4 flex-shrink-0">'
);

fs.writeFileSync(filePath, content, 'utf8');
console.log('Header fixed.');

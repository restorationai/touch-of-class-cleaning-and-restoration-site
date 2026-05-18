const fs = require('fs');
const path = require('path');
const https = require('https');

const componentsDir = path.join(__dirname, 'src', 'components');
const mediaDir = path.join(__dirname, 'public', 'media');

if (!fs.existsSync(mediaDir)) {
  fs.mkdirSync(mediaDir, { recursive: true });
}

const urls = fs.readFileSync('images.txt', 'utf8').split('\n').filter(Boolean);

async function download(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    https.get(url, (response) => {
      response.pipe(file);
      file.on('finish', () => {
        file.close(resolve);
      });
    }).on('error', (err) => {
      fs.unlink(dest, () => reject(err));
    });
  });
}

(async () => {
  const urlMap = {};
  for (const url of urls) {
    const filename = path.basename(url);
    const dest = path.join(mediaDir, filename);
    console.log(`Downloading ${filename}...`);
    try {
      await download(url, dest);
      urlMap[url] = `/media/${filename}`;
    } catch (e) {
      console.error(`Failed to download ${url}`, e);
    }
  }

  // Replace in files
  const files = fs.readdirSync(componentsDir).filter(f => f.endsWith('.tsx'));
  for (const file of files) {
    const filePath = path.join(componentsDir, file);
    let content = fs.readFileSync(filePath, 'utf8');
    let changed = false;
    for (const [url, newUrl] of Object.entries(urlMap)) {
      if (content.includes(url)) {
        content = content.split(url).join(newUrl);
        changed = true;
      }
    }
    if (changed) {
      fs.writeFileSync(filePath, content, 'utf8');
    }
  }
  console.log('All images downloaded and code updated.');
})();

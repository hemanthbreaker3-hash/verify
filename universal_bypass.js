const http = require('http');
const https = require('https');

const MAX_REDIRECTS = 10;
const MAX_TELEGRAM_URL_LENGTH = 4096;

// Supported target parameter names
const TARGET_KEYS = [
  'nicktrick',
  'url',
  'target',
  'link',
  'dest',
  'destination',
  'go',
  'to',
  'out'
];

const inputUrl = process.argv[2];
const customReferer = process.argv[3] || null;

if (!inputUrl) {
  console.log('Usage:');
  console.log('node universal_bypass.js "<INPUT_URL>"');
  console.log('');
  console.log('Optional custom Referer:');
  console.log('node universal_bypass.js "<INPUT_URL>" "https://spaceb.in/"');
  process.exit(1);
}

/**
 * Extract target URL and wrapper/referer URL.
 *
 * Supported:
 *
 * https://domain.com=https://target.com
 *
 * https://domain.com/path=https://target.com
 *
 * https://domain.com/links?nicktrick=https://target.com
 *
 * https://domain.com/?url=https://target.com
 */
function extractTargetAndReferer(input) {
  let targetUrl = null;
  let refererUrl = null;

  // --------------------------------------------------
  // Format:
  // https://domain.com=https://target.com
  // --------------------------------------------------
  const equalIndex = input.indexOf('=http');

  if (equalIndex !== -1 && !input.slice(0, equalIndex).includes('?')) {
    refererUrl = input.substring(0, equalIndex);
    targetUrl = input.substring(equalIndex + 1);

    return {
      targetUrl,
      refererUrl
    };
  }

  // --------------------------------------------------
  // Normal URL/query-string formats
  // --------------------------------------------------
  try {
    const parsed = new URL(input);

    // Wrapper domain becomes the default Referer
    refererUrl = `${parsed.protocol}//${parsed.host}/`;

    // Search known parameters
    for (const key of TARGET_KEYS) {
      const value = parsed.searchParams.get(key);

      if (value && /^https?:\/\//i.test(value)) {
        targetUrl = value;
        break;
      }
    }

    // --------------------------------------------------
    // Raw fallback:
    // ?anything=https://target.com
    // --------------------------------------------------
    if (!targetUrl) {
      const match = input.match(/=(https?:\/\/[^\s&]+)/i);

      if (match) {
        targetUrl = decodeURIComponent(match[1]);
      }
    }
  } catch (error) {
    console.error('[-] Invalid input URL.');
    process.exit(1);
  }

  return {
    targetUrl: targetUrl || input,
    refererUrl: refererUrl || input
  };
}

/**
 * Upload long URL to Spacebin.
 *
 * Spacebin is ONLY used when the final URL is
 * longer than Telegram's 2000-character message limit.
 */
function uploadToSpacebin(content) {
  return new Promise((resolve) => {
    const body = JSON.stringify({
      content,
      extension: 'txt'
    });

    const options = {
      hostname: 'spaceb.in',
      path: '/api/v1/documents',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body)
      }
    };

    const req = https.request(options, (res) => {
      let data = '';

      res.on('data', chunk => {
        data += chunk;
      });

      res.on('end', () => {
        try {
          const json = JSON.parse(data);

          if (
            json &&
            json.payload &&
            json.payload.id
          ) {
            resolve(`https://spaceb.in/${json.payload.id}`);
          } else {
            console.error('[-] Spacebin returned an unexpected response.');
            console.error(data);
            resolve(null);
          }
        } catch (error) {
          console.error('[-] Could not parse Spacebin response.');
          console.error(data);
          resolve(null);
        }
      });
    });

    req.on('error', (error) => {
      console.error(`[-] Spacebin upload error: ${error.message}`);
      resolve(null);
    });

    req.write(body);
    req.end();
  });
}

/**
 * Perform one HTTP/HTTPS request.
 */
function requestUrl(targetUrl, referer) {
  return new Promise((resolve, reject) => {
    let parsed;

    try {
      parsed = new URL(targetUrl);
    } catch (error) {
      reject(new Error(`Invalid URL: ${targetUrl}`));
      return;
    }

    const client =
      parsed.protocol === 'https:'
        ? https
        : http;

    const options = {
      headers: {
        'User-Agent':
          'Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36',

        'Referer': referer,

        'Accept':
          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',

        'Accept-Language':
          'en-US,en;q=0.9'
      }
    };

    const req = client.get(targetUrl, options, (res) => {
      resolve(res);
    });

    req.setTimeout(20000, () => {
      req.destroy(
        new Error('Request timed out after 20 seconds.')
      );
    });

    req.on('error', reject);
  });
}

/**
 * Follow redirects manually.
 *
 * This avoids axios dependency and makes the script
 * easier to run in Termux.
 */
async function resolveUniversal(
  startUrl,
  referer,
  depth = 0
) {
  if (depth > MAX_REDIRECTS) {
    console.log('[-] Maximum redirect limit reached.');
    return null;
  }

  console.log(`[*] Requesting: ${startUrl}`);

  let response;

  try {
    response = await requestUrl(startUrl, referer);
  } catch (error) {
    console.error(`[-] Network Error: ${error.message}`);
    return null;
  }

  console.log(`[+] Status: ${response.statusCode}`);

  const redirectCodes = [
    301,
    302,
    303,
    307,
    308
  ];

  if (
    redirectCodes.includes(response.statusCode) &&
    response.headers.location
  ) {
    const redirectUrl = new URL(
      response.headers.location,
      startUrl
    ).toString();

    console.log(`[>] Redirecting to: ${redirectUrl}`);

    // Use the current URL as Referer for the next request.
    return resolveUniversal(
      redirectUrl,
      startUrl,
      depth + 1
    );
  }

  // Consume response data so the socket can close cleanly.
  response.resume();

  console.log('');
  console.log('[SUCCESS] Final Destination:');
  console.log(startUrl);

  return startUrl;
}

/**
 * Main
 */
async function main() {
  console.log('========================================');
  console.log(' Universal URL Resolver');
  console.log('========================================');
  console.log('');

  const {
    targetUrl,
    refererUrl
  } = extractTargetAndReferer(inputUrl);

  // Custom Referer has priority.
  const finalReferer =
    customReferer || refererUrl;

  console.log(`[*] Input URL   : ${inputUrl}`);
  console.log(`[*] Referer     : ${finalReferer}`);
  console.log(`[*] Target URL  : ${targetUrl}`);
  console.log('');

  const finalUrl = await resolveUniversal(
    targetUrl,
    finalReferer
  );

  if (!finalUrl) {
    process.exit(1);
  }

  console.log('');

  // --------------------------------------------------
  // Long URL handling
  // --------------------------------------------------
  if (finalUrl.length > MAX_TELEGRAM_URL_LENGTH) {
    console.log(
      `[!] Final URL is ${finalUrl.length} characters.`
    );

    console.log(
      '[*] Uploading long URL to Spacebin...'
    );

    const spacebinLink =
      await uploadToSpacebin(finalUrl);

    console.log('');
    console.log('========================================');

    if (spacebinLink) {
      console.log(
        '[SUCCESS] Spacebin Link:'
      );
      console.log(spacebinLink);
    } else {
      console.log(
        '[-] Spacebin upload failed.'
      );
      console.log('');
      console.log(
        'Final URL:'
      );
      console.log(finalUrl);
    }

    console.log('========================================');
  } else {
    console.log('========================================');
    console.log('[SUCCESS] Final URL:');
    console.log(finalUrl);
    console.log('========================================');
  }
}

main().catch((error) => {
  console.error(`[-] Fatal Error: ${error.message}`);
  process.exit(1);
});

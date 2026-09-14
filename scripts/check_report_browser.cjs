#!/usr/bin/env node
// Real local Chrome inspection over anonymous CDP pipes; no npm dependencies.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {pathToFileURL} = require('node:url');

(async () => {
  const source = path.resolve(process.argv[2] || '');
  if (!fs.statSync(source).isFile()) throw new Error('Expected a local report file');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'ahas-browser-'));
  const chrome = spawn(process.env.AHAS_CHROME || 'google-chrome', [
    '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
    '--remote-debugging-pipe', '--disable-background-networking', '--disable-sync',
    '--disable-extensions', '--disable-component-update', '--disable-default-apps',
    '--no-first-run', '--no-default-browser-check', '--metrics-recording-only',
    '--window-size=1440,1000',
    '--disable-features=MediaRouter,OptimizationHints,PasswordLeakDetection',
    '--user-data-dir=' + profile, 'about:blank',
  ], {stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe']});
  let serial = 0, buffer = '', stderr = '';
  const pending = new Map(), listeners = new Map(), attempted = [], dialogs = [];
  chrome.stderr.on('data', data => { stderr = (stderr + data).slice(-6000); });
  for (const pipe of [chrome.stdio[3], chrome.stdio[4]]) pipe.on('error', error => {
    for (const request of pending.values()) request.reject(new Error(String(error)+': '+stderr));
  });
  const timeout = setTimeout(() => {
    chrome.kill('SIGKILL');
    for (const {reject} of pending.values()) reject(new Error('Chrome inspection timeout: ' + stderr));
  }, 30000);
  function call(method, params = {}, sessionId) {
    return new Promise((resolve, reject) => {
      const id = ++serial;
      pending.set(id, {resolve, reject});
      chrome.stdio[3].write(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}) + '\0');
    });
  }
  chrome.stdio[4].on('data', data => {
    buffer += data.toString();
    let delimiter;
    while ((delimiter = buffer.indexOf('\0')) >= 0) {
      const message = JSON.parse(buffer.slice(0, delimiter));
      buffer = buffer.slice(delimiter + 1);
      if (message.id && pending.has(message.id)) {
        const request = pending.get(message.id); pending.delete(message.id);
        message.error ? request.reject(new Error(JSON.stringify(message.error))) : request.resolve(message.result);
      } else {
        for (const listener of listeners.get(message.method) || []) listener(message.params, message.sessionId);
      }
    }
  });
  chrome.on('error', error => { for (const request of pending.values()) request.reject(error); });
  chrome.on('exit', code => { for (const request of pending.values()) request.reject(new Error('Chrome exited '+code+': '+stderr)); });
  const on = (event, fn) => listeners.set(event, [...(listeners.get(event) || []), fn]);
  try {
    const version = await call('Browser.getVersion');
    const {targetId} = await call('Target.createTarget', {url: 'about:blank'});
    const {sessionId} = await call('Target.attachToTarget', {targetId, flatten: true});
    await call('Page.enable', {}, sessionId);
    await call('Network.enable', {}, sessionId);
    await call('Network.emulateNetworkConditions', {offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0}, sessionId);
    on('Network.requestWillBeSent', params => attempted.push(params.request.url));
    on('Fetch.requestPaused', (params, session) => {
      if (/^(?:https?|ftp|wss?):/i.test(params.request.url)) {
        attempted.push(params.request.url);
        call('Fetch.failRequest', {requestId: params.requestId, errorReason: 'BlockedByClient'}, session).catch(() => {});
      } else call('Fetch.continueRequest', {requestId: params.requestId}, session).catch(() => {});
    });
    on('Page.javascriptDialogOpening', (params, session) => {
      dialogs.push(params.type);
      call('Page.handleJavaScriptDialog', {accept: false}, session).catch(() => {});
    });
    await call('Fetch.enable', {patterns: [{urlPattern: '*'}]}, sessionId);
    const loaded = new Promise(resolve => on('Page.loadEventFired', resolve));
    await call('Page.navigate', {url: pathToFileURL(source).href}, sessionId);
    await loaded;
    const evaluated = await call('Runtime.evaluate', {returnByValue: true, expression: `(() => ({
      activeElements: Array.from(document.querySelectorAll('script,iframe,object,embed,base,form')).map(e=>e.tagName),
      eventHandlers: Array.from(document.querySelectorAll('*')).flatMap(e=>Array.from(e.attributes).filter(a=>/^on/i.test(a.name)).map(a=>a.name)),
      unsafeLinks: Array.from(document.querySelectorAll('[href]')).map(e=>e.getAttribute('href')).filter(v=>/^\\s*(?:javascript|vbscript|data):/i.test(v)),
      sourceExecuted: Boolean(window.__AHAS_EXECUTED),
      title: document.title, documentURL: location.href, bodyTextLength: document.body.innerText.length
    }))()`}, sessionId);
    if (evaluated.result.value.documentURL !== pathToFileURL(source).href || !evaluated.result.value.bodyTextLength) throw new Error('Local report did not load');
    if (process.argv[3]) {
      if (process.argv[4]) {
        const scrolled = await call('Runtime.evaluate', {returnByValue: true,
          expression: `(() => {const target=document.getElementById(${JSON.stringify(process.argv[4])}); if (!target) return false; target.scrollIntoView(); return true;})()`}, sessionId);
        if (!scrolled.result.value) throw new Error('Requested screenshot section is absent');
      }
      const output = path.resolve(process.argv[3]);
      fs.mkdirSync(path.dirname(output), {recursive: true});
      const screenshot = await call('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false}, sessionId);
      fs.writeFileSync(output, Buffer.from(screenshot.data, 'base64'));
    }
    const remoteRequests = [...new Set(attempted.filter(url => /^(?:https?|ftp|wss?):/i.test(url)))].sort();
    const audit = {browser: version.product, isolation: process.env.AHAS_BROWSER_NETWORK_ISOLATION || 'cdp_offline_and_fetch_interception',
      remoteRequests, dialogs, ...evaluated.result.value};
    process.stdout.write(JSON.stringify(audit) + '\n');
    if (remoteRequests.length || dialogs.length || audit.activeElements.length || audit.eventHandlers.length || audit.unsafeLinks.length || audit.sourceExecuted) process.exitCode = 1;
  } finally {
    clearTimeout(timeout);
    if (chrome.exitCode === null && chrome.signalCode === null) {
      chrome.kill('SIGKILL');
      await new Promise(resolve => chrome.once('close', resolve));
    }
    fs.rmSync(profile, {recursive: true, force: true});
  }
})().catch(error => { process.stderr.write(String(error.stack || error) + '\n'); process.exitCode = 1; });

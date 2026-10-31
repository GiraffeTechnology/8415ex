"use strict";
// Test-only DOM/event adapter: execute the exact product script, never a live browser or source.
const assert = require("node:assert/strict");
const vm = require("node:vm");
let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", chunk => { input += chunk; });
process.stdin.on("end", async () => {
  try {
    const value = JSON.parse(input);
    const timers = new Map(), events = new Map();
    let sequence = 0, replaced = 0, aborted = 0, hold = false;
    const requests = [];
    function listener(name, fn, options) {
      const list = events.get(name) || [];
      list.push({fn, once: !!options?.once}); events.set(name, list);
    }
    function emit(name, event = {}) {
      for (const entry of [...(events.get(name) || [])]) {
        if (entry.once) events.set(name, events.get(name).filter(x => x !== entry));
        entry.fn(event);
      }
    }
    const error = {hidden: true};
    const disclosure = {open: value.case === "disclosure-open"};
    const nextDisclosure = {open: false};
    const current = {replaceWith() { replaced++; }, querySelector(selector) { return selector === "details" ? disclosure : error; }};
    const next = {tagName: "SECTION", id: "commodity-reference", attributes: [],
                  querySelectorAll() { return []; },
                  querySelector(selector) { return selector === "details" ? nextDisclosure : null; }};
    const document = {hidden: false, getElementById() { return current; },
      importNode(node) { return node; }, addEventListener: listener};
    const window = {location: {href: "https://market.example/market?lang=en#nfts"},
                    addEventListener: listener};
    class Parser {
      parseFromString() {
        return {body: {children: [next], firstElementChild: next}, head: {children: []}};
      }
    }
    async function read(url, options) {
      requests.push({url, options});
      if (hold) return new Promise((resolve, reject) => {
        options.signal.addEventListener("abort", () => {
          aborted++; reject(new Error("test read aborted"));
        }, {once: true});
      });
      const responseURL = new URL(url); responseURL.hash = "";
      let sent = false;
      return {ok: true, url: responseURL.href,
        headers: {get: () => "text/html; charset=utf-8"},
        body: {getReader: () => ({
          read: async () => sent ? {done: true} : (sent = true,
            {done: false, value: new TextEncoder().encode('<section id="commodity-reference"></section>')}),
          cancel: async () => {}
        })}};
    }
    const context = {document, window, URL, AbortController, TextDecoder, Uint8Array,
      DOMParser: Parser, fetch: read,
      setTimeout(fn, delay) { const id = ++sequence; timers.set(id, {fn, delay}); return id; },
      clearTimeout(id) { timers.delete(id); }};
    vm.runInNewContext(value.script, context, {timeout: 1000});
    const first = [...timers].find(([, row]) => row.delay === 60000);
    assert.ok(first, "initial refresh must be scheduled");
    timers.delete(first[0]);
    await first[1].fn();
    assert.equal(requests.length, 1);
    if (value.case === "fragment") {
      assert.equal(requests[0].url, "https://market.example/market?lang=en&reference=1");
      assert.equal(replaced, 1, "valid response must replace only the reference panel");
      assert.equal(error.hidden, true);
    } else if (value.case === "repeated-exit") {
      assert.equal(replaced, 1);
      emit("pagehide");
      hold = true;
      emit("pageshow", {persisted: true});
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(requests.length, 2);
      assert.equal(requests[1].options.signal.aborted, false);
      emit("pagehide");
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(aborted, 1, "second exit must cancel the restored page's active read");
      assert.equal(requests[1].options.signal.aborted, true);
      assert.equal(timers.size, 0, "exited pages must not schedule another poll");
    } else if (value.case === "disclosure-open" || value.case === "disclosure-closed") {
      assert.equal(replaced, 1);
      assert.equal(nextDisclosure.open, disclosure.open, "refresh must retain user disclosure state");
    } else throw new Error("unknown test case");
    process.stdout.write(JSON.stringify({case: value.case, passed: true}));
  } catch (error) { console.error(error); process.exitCode = 1; }
});

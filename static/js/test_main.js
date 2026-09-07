// Checks for the parts of main.js that are easy to break silently.
// Run: node static/js/test_main.js
//
// No framework and no jsdom: the functions under test touch a handful of DOM
// properties, so a hand-rolled stub is smaller than a dependency.

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// ---------------------------------------------------------------- stub DOM
const TEXT_NODE = 3, ELEMENT_NODE = 1;

function text(value) {
    return { nodeType: TEXT_NODE, nodeValue: value, childNodes: [] };
}

function el(tagName, children = []) {
    return { nodeType: ELEMENT_NODE, tagName, childNodes: children };
}

// forEach over a plain array is what the real NodeList gives us.
const sandbox = {
    Node: { TEXT_NODE, ELEMENT_NODE },
    document: { getElementById: () => null, querySelectorAll: () => [] },
    window: {},
    localStorage: {
        _v: {},
        getItem(k) { return k in this._v ? this._v[k] : null; },
        setItem(k, v) { this._v[k] = String(v); },
    },
    console,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

// Only the pieces that do not need a live page. Pulling the whole file in would
// run the DOMContentLoaded wiring, which needs a real document.
const source = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
function extract(name) {
    const start = source.indexOf('function ' + name + '(');
    assert.notStrictEqual(start, -1, 'could not find ' + name);
    let depth = 0, i = source.indexOf('{', start);
    for (let j = i; j < source.length; j++) {
        if (source[j] === '{') depth++;
        else if (source[j] === '}' && --depth === 0) {
            return source.slice(start, j + 1);
        }
    }
    throw new Error('unbalanced braces in ' + name);
}

vm.createContext(sandbox);
vm.runInContext(
    [
        'const WALKTHROUGH_HEADINGS = ' + JSON.stringify([
            'What This Program Does', 'Packages And Imports', 'Step By Step Walkthrough',
            'Key Functions Explained', 'Things To Try']) + ';',
        'const BLOCK_TAGS = /^(P|DIV|LI|H[1-6]|PRE|UL|OL|TR|SECTION|ARTICLE|BLOCKQUOTE)$/;',
        extract('escapeHtml'),
        extract('formatMarkdown'),
        extract('readBlockText'),
    ].join('\n'), sandbox);

const { escapeHtml, formatMarkdown, readBlockText } = sandbox;

// ------------------------------------------------------- escaping is real
// The four feature pages hand model output straight to innerHTML, so this is
// the only thing standing between a stray tag and the DOM.
assert.strictEqual(
    escapeHtml('<img src=x onerror=alert(1)>'),
    '&lt;img src=x onerror=alert(1)&gt;');
assert.ok(!formatMarkdown('<script>alert(1)</script>').includes('<script>'),
    'formatMarkdown must escape its input');
assert.ok(formatMarkdown('a & b').includes('&amp;'), 'ampersands are escaped');

// Escaping must not eat ordinary prose or the headings feature.
assert.ok(formatMarkdown('Packages And Imports\n\nSome text.')
    .includes('<h4>Packages And Imports</h4>'), 'headings still promoted');
assert.ok(formatMarkdown('- one\n- two').includes('<li>one</li>'), 'lists still built');

// ------------------------------------------- readBlockText survives hiding
// The bug this replaces: innerText returns '' inside a hidden tab panel, so the
// lesson download silently lost whichever tab the learner had not opened.
const walkthrough = el('DIV', [
    el('P', [text('First paragraph.')]),
    el('P', [text('Second paragraph.')]),
    el('UL', [el('LI', [text('point one')]), el('LI', [text('point two')])]),
]);
const got = readBlockText(walkthrough);
assert.ok(got.includes('First paragraph.'), 'text survives');
assert.ok(got.includes('Second paragraph.'), 'later blocks survive');
assert.ok(got.includes('point one') && got.includes('point two'), 'list items survive');
// The whole point: blocks do not run together into one line.
assert.ok(/First paragraph\.\s*\n/.test(got), 'blocks are separated by a newline');
assert.ok(!got.includes('First paragraph.Second'), 'blocks must not concatenate');

// <br> is a line break, not a word joiner.
assert.strictEqual(readBlockText(el('P', [text('a'), el('BR'), text('b')])), 'a\nb');

// Inline elements must not introduce breaks.
assert.strictEqual(
    readBlockText(el('P', [text('keep '), el('EM', [text('this')]), text(' together')])),
    'keep this together');

// Degenerate input must not throw - buildLesson calls this on ids that may not exist.
assert.strictEqual(readBlockText(null), '');
assert.strictEqual(readBlockText(el('DIV', [])), '');

// Runs of blank lines are collapsed rather than padding the file out.
assert.ok(!/\n{3,}/.test(readBlockText(el('DIV', [
    el('P', [text('a')]), el('P', []), el('P', []), el('P', [text('b')]),
]))), 'blank runs collapsed');

console.log('main.js checks passed');

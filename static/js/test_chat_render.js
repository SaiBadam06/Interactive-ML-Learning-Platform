// Checks for the chat's markdown renderer.
// Run: node static/js/test_chat_render.js
//
// This is the one place model output becomes HTML, so the escaping half matters
// as much as the formatting half.

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const source = fs.readFileSync(path.join(__dirname, 'chat.js'), 'utf8');

// Lift the three renderer functions out of the page IIFE. They touch no DOM.
function extract(name) {
    const start = source.indexOf('function ' + name + '(');
    assert.notStrictEqual(start, -1, 'could not find ' + name);
    let depth = 0;
    for (let i = source.indexOf('{', start); i < source.length; i++) {
        if (source[i] === '{') depth++;
        else if (source[i] === '}' && --depth === 0) return source.slice(start, i + 1);
    }
    throw new Error('unbalanced braces in ' + name);
}

const sandbox = { console };
vm.createContext(sandbox);
vm.runInContext([extract('esc'), extract('inline'), extract('renderMarkdown')].join('\n'), sandbox);
const { renderMarkdown } = sandbox;

// ---------------------------------------------------------------- escaping
// Everything here is written by a language model, so this is the boundary.
const attack = '<img src=x onerror=alert(1)>';
assert.ok(!renderMarkdown(attack).includes('<img'), 'raw tags must not survive');
assert.ok(renderMarkdown(attack).includes('&lt;img'), 'tags are escaped, not dropped');
assert.ok(!renderMarkdown('<script>alert(1)</script>').includes('<script>'));
assert.ok(renderMarkdown('Tom & Jerry').includes('&amp;'));
// A tag smuggled inside a code span is still only text.
assert.ok(!renderMarkdown('`<b>hi</b>`').includes('<b>'));

// ------------------------------------------------------------------ inline
// An identifier set in the same face as the prose is what made answers a wall.
assert.ok(renderMarkdown('Call `np.vstack` on it.').includes('<code>np.vstack</code>'));
assert.ok(renderMarkdown('This is **overfitting** here.').includes('<strong>overfitting</strong>'));
// Single-asterisk italics are deliberately unsupported - see below.
assert.ok(!renderMarkdown('a *stressed* word').includes('<em>'));
// Underscores are ordinary in identifiers, so they must not become emphasis.
const ident = renderMarkdown('`n_init` and `random_state` matter');
assert.ok(!ident.includes('<em>'), 'underscores in identifiers are not italics');
// Multiplication must survive: 2 * 3 * 4 is not emphasis.
// The reason italics are off: in this subject an asterisk is usually maths.
assert.ok(!renderMarkdown('2 * 3 * 4 = 24').includes('<em>'), 'bare asterisks are not emphasis');
assert.ok(renderMarkdown('loss = w * x + b').includes('w * x'), 'multiplication survives intact');

// ------------------------------------------------------------------ blocks
const lists = renderMarkdown('Steps:\n\n- pick k\n- assign points\n- move centres');
assert.ok(lists.includes('<ul>') && (lists.match(/<li>/g) || []).length === 3);

const ordered = renderMarkdown('1. first\n2. second');
assert.ok(ordered.includes('<ol>') && (ordered.match(/<li>/g) || []).length === 2);

// Headings never rise above h3: the page already has an h1.
const heads = renderMarkdown('# Top\n\n## Second\n\n### Third');
assert.ok(!heads.includes('<h1') && !heads.includes('<h2'), 'no h1/h2 inside a turn');
assert.ok(heads.includes('<h3'), 'headings still render');

// Paragraphs are separated by a blank line, not by every newline.
const paras = renderMarkdown('One sentence.\nStill the same idea.\n\nA new point.');
assert.strictEqual((paras.match(/<p>/g) || []).length, 2);

// ------------------------------------------------------------- code fences
const fenced = renderMarkdown('Here:\n\n```python\nx = 1\nprint(x)\n```\n\nDone.');
assert.ok(fenced.includes('<pre class="chat-code">'), 'fences become blocks');
assert.ok(fenced.includes('print(x)'));
assert.ok(!fenced.includes('```'), 'the fence markers themselves are consumed');
// Markdown inside a fence is code, not formatting.
const literal = renderMarkdown('```\n**not bold** and `not code`\n```');
assert.ok(!literal.includes('<strong>'), 'a fence is verbatim');

// A reply is rendered while it streams, so it is constantly half-finished.
const midStream = renderMarkdown('Here it is:\n\n```python\nx = 1');
assert.ok(midStream.includes('x = 1'), 'an unclosed fence still shows what arrived');

// ----------------------------------------------------------------- degenerate
assert.strictEqual(renderMarkdown(''), '');
assert.strictEqual(renderMarkdown(null), '');
assert.strictEqual(renderMarkdown(undefined), '');
assert.ok(renderMarkdown('   \n\n   ') === '');

console.log('chat renderer checks passed');

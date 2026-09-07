// Pyodide lives in this worker, not on the main thread. Python cannot be
// interrupted from JavaScript, so a generated program with a runaway loop would
// freeze the whole page; terminating the worker is the only reliable stop
// button. Nothing here ever talks to our server - the code runs in the browser.
//
// This is a MODULE worker loading the ESM build (pyodide.mjs) via dynamic
// import, not the classic build via importScripts: cross-origin importScripts
// is blocked in some environments (it failed outright in the test browser here
// while fetch and import() both worked), and the ESM build then uses import()
// for its own sub-assets too.
const PYODIDE_BASE = 'https://cdn.jsdelivr.net/pyodide/v314.0.6/full/';

let pyodide = null;

const send = (msg) => self.postMessage(msg);

// Collect whatever matplotlib drew. Wrapped in try/except so a program that
// never imports matplotlib (most of them) is completely unaffected.
const COLLECT_FIGURES = `
import base64, io, json
_figs = []
try:
    import matplotlib.pyplot as plt
    for _n in plt.get_fignums():
        _buf = io.BytesIO()
        plt.figure(_n).savefig(_buf, format='png', bbox_inches='tight')
        _figs.append(base64.b64encode(_buf.getvalue()).decode())
    plt.close('all')
except Exception:
    pass
json.dumps(_figs)
`;

async function boot() {
    if (pyodide) return pyodide;
    send({ type: 'status', text: 'Loading Python runtime (~15 MB, first time only)...' });
    const { loadPyodide } = await import(PYODIDE_BASE + 'pyodide.mjs');
    pyodide = await loadPyodide({ indexURL: PYODIDE_BASE });
    // batched fires per line and hands over the line WITHOUT its newline, so put
    // it back or every print() run together in the output panel.
    pyodide.setStdout({ batched: (text) => send({ type: 'stdout', text: text + '\n' }) });
    pyodide.setStderr({ batched: (text) => send({ type: 'stderr', text: text + '\n' }) });
    // Must be set before the program imports matplotlib: any interactive
    // backend fails outright in a worker with no DOM.
    await pyodide.runPythonAsync('import os\nos.environ["MPLBACKEND"] = "AGG"');
    return pyodide;
}

self.onmessage = async (event) => {
    const code = String((event.data && event.data.code) || '');
    const started = Date.now();
    try {
        const py = await boot();
        send({ type: 'status', text: 'Loading packages...' });
        // Pulls numpy/scikit-learn/etc. out of the Pyodide distribution based on
        // the import lines. A package that is not in the build simply is not
        // loaded here and raises a normal ImportError below, which the learner
        // sees as a traceback.
        // messageCallback keeps "Loading numpy, matplotlib..." in the status line
        // instead of letting it land in the program's own output.
        await py.loadPackagesFromImports(code, {
            messageCallback: (text) => send({ type: 'status', text }),
            errorCallback: (text) => send({ type: 'stderr', text: text + '\n' }),
        });
        send({ type: 'status', text: 'Running...' });
        await py.runPythonAsync(code);
        try {
            const figures = JSON.parse(await py.runPythonAsync(COLLECT_FIGURES));
            if (figures.length) send({ type: 'images', images: figures });
        } catch (e) {
            // A broken figure must not turn a successful run into an error.
        }
        send({ type: 'done', ms: Date.now() - started });
    } catch (err) {
        send({ type: 'error', text: String((err && err.message) || err), ms: Date.now() - started });
    }
};

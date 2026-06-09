"use strict";
(self["webpackChunkmordornotebook"] = self["webpackChunkmordornotebook"] || []).push([["lib_index_js"],{

/***/ "./lib/index.js"
/*!**********************!*\
  !*** ./lib/index.js ***!
  \**********************/
(__unused_webpack_module, __webpack_exports__, __webpack_require__) {

__webpack_require__.r(__webpack_exports__);
/* harmony export */ __webpack_require__.d(__webpack_exports__, {
/* harmony export */   "default": () => (__WEBPACK_DEFAULT_EXPORT__)
/* harmony export */ });
/* harmony import */ var _jupyterlab_apputils__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! @jupyterlab/apputils */ "webpack/sharing/consume/default/@jupyterlab/apputils");
/* harmony import */ var _jupyterlab_apputils__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(_jupyterlab_apputils__WEBPACK_IMPORTED_MODULE_0__);
/* harmony import */ var _jupyterlab_mainmenu__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! @jupyterlab/mainmenu */ "webpack/sharing/consume/default/@jupyterlab/mainmenu");
/* harmony import */ var _jupyterlab_mainmenu__WEBPACK_IMPORTED_MODULE_1___default = /*#__PURE__*/__webpack_require__.n(_jupyterlab_mainmenu__WEBPACK_IMPORTED_MODULE_1__);
/* harmony import */ var _jupyterlab_notebook__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! @jupyterlab/notebook */ "webpack/sharing/consume/default/@jupyterlab/notebook");
/* harmony import */ var _jupyterlab_notebook__WEBPACK_IMPORTED_MODULE_2___default = /*#__PURE__*/__webpack_require__.n(_jupyterlab_notebook__WEBPACK_IMPORTED_MODULE_2__);
/* harmony import */ var _lumino_widgets__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! @lumino/widgets */ "webpack/sharing/consume/default/@lumino/widgets");
/* harmony import */ var _lumino_widgets__WEBPACK_IMPORTED_MODULE_3___default = /*#__PURE__*/__webpack_require__.n(_lumino_widgets__WEBPACK_IMPORTED_MODULE_3__);




const OPEN_PANEL_COMMAND = 'mordornotebook:open-panel';
function activeNotebook(notebooks) {
    const panel = notebooks.currentWidget;
    if (!panel || !panel.content || !panel.context) {
        throw new Error('No active JupyterLab notebook is selected.');
    }
    if (!panel.context.path) {
        throw new Error('Active notebook has no document path.');
    }
    return panel;
}
function sourceLines(source) {
    if (!source) {
        return [];
    }
    const lines = source.split(/\r?\n/);
    return lines.map((line, index) => (index < lines.length - 1 ? `${line}\n` : line));
}
function safeRequestId(value) {
    if (value && /^[A-Za-z0-9_.:-]+$/.test(value)) {
        return value;
    }
    const cryptoObj = globalThis.crypto;
    if (cryptoObj && typeof cryptoObj.randomUUID === 'function') {
        return cryptoObj.randomUUID();
    }
    return `mordor-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
function localStorageValue(key, fallback) {
    try {
        return window.localStorage.getItem(key) || fallback;
    }
    catch (error) {
        return fallback;
    }
}
function defaultRepo() {
    return localStorageValue('mordorDefaultRepo', '');
}
function normalizeBase(value) {
    let base = String(value || '/').trim() || '/';
    if (!base.startsWith('/')) {
        base = `/${base}`;
    }
    if (!base.endsWith('/')) {
        base += '/';
    }
    return base;
}
function jupyterConfigBase() {
    const node = document.getElementById('jupyter-config-data');
    if (!node || !node.textContent) {
        return '';
    }
    try {
        const cfg = JSON.parse(node.textContent);
        return cfg.baseUrl || cfg.base_url || '';
    }
    catch (error) {
        return '';
    }
}
function inferApiBase() {
    const configured = jupyterConfigBase();
    if (configured) {
        return new URL(`${normalizeBase(configured)}mordor/api/`, window.location.origin).toString();
    }
    const path = window.location.pathname || '/';
    for (const marker of ['/lab', '/notebooks/', '/tree/']) {
        const index = path.indexOf(marker);
        if (index >= 0) {
            return new URL(`${normalizeBase(path.slice(0, index + 1))}mordor/api/`, window.location.origin).toString();
        }
    }
    return new URL('/mordor/api/', window.location.origin).toString();
}
async function callMordorApi(path, method = 'GET', body = null) {
    const response = await fetch(new URL(path.replace(/^\/+/, ''), inferApiBase()).toString(), {
        method,
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : null
    });
    const text = await response.text();
    let payload;
    try {
        payload = JSON.parse(text);
    }
    catch (error) {
        payload = text;
    }
    if (!response.ok) {
        throw new Error(`HTTP ${response.status} ${response.statusText}: ${typeof payload === 'string' ? payload : JSON.stringify(payload)}`);
    }
    return payload;
}
function notebookContext(panel) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m;
    return {
        notebook_path: panel.context.path,
        kernel_id: (_c = (_b = (_a = panel.sessionContext.session) === null || _a === void 0 ? void 0 : _a.kernel) === null || _b === void 0 ? void 0 : _b.id) !== null && _c !== void 0 ? _c : null,
        kernel_name: (_f = (_e = (_d = panel.sessionContext.session) === null || _d === void 0 ? void 0 : _d.kernel) === null || _e === void 0 ? void 0 : _e.name) !== null && _f !== void 0 ? _f : null,
        kernel_display_name: (_g = panel.sessionContext.kernelDisplayName) !== null && _g !== void 0 ? _g : null,
        kernel_status: (_h = panel.sessionContext.kernelDisplayStatus) !== null && _h !== void 0 ? _h : null,
        kernel_ready: Boolean((_k = (_j = panel.sessionContext) === null || _j === void 0 ? void 0 : _j.session) === null || _k === void 0 ? void 0 : _k.kernel),
        session_id: (_m = (_l = panel.sessionContext.session) === null || _l === void 0 ? void 0 : _l.id) !== null && _m !== void 0 ? _m : null,
        active_cell_index: panel.content.activeCellIndex,
        cell_count: panel.content.widgets.length,
        dirty: panel.context.model.dirty
    };
}
async function ensureKernel(panel, onEvent) {
    var _a, _b, _c, _d, _e, _f, _g, _h;
    if ((_b = (_a = panel.sessionContext) === null || _a === void 0 ? void 0 : _a.session) === null || _b === void 0 ? void 0 : _b.kernel) {
        return;
    }
    onEvent === null || onEvent === void 0 ? void 0 : onEvent('waiting_for_kernel', 'Waiting for the active notebook kernel');
    if (!panel.sessionContext.isReady) {
        await panel.sessionContext.ready;
    }
    if ((_d = (_c = panel.sessionContext) === null || _c === void 0 ? void 0 : _c.session) === null || _d === void 0 ? void 0 : _d.kernel) {
        return;
    }
    onEvent === null || onEvent === void 0 ? void 0 : onEvent('starting_kernel', 'Starting a kernel for the active notebook');
    await panel.sessionContext.initialize();
    if (!((_f = (_e = panel.sessionContext) === null || _e === void 0 ? void 0 : _e.session) === null || _f === void 0 ? void 0 : _f.kernel)) {
        await panel.sessionContext.startKernel();
    }
    if (!((_h = (_g = panel.sessionContext) === null || _g === void 0 ? void 0 : _g.session) === null || _h === void 0 ? void 0 : _h.kernel)) {
        throw new Error('Active notebook has no running kernel after JupyterLab kernel startup.');
    }
}
function setCellSource(panel, index, source) {
    var _a;
    const cell = panel.content.widgets[index];
    if (!cell) {
        throw new Error(`Inserted cell index ${index} is not visible in the notebook model.`);
    }
    const model = cell.model;
    if (typeof ((_a = model.sharedModel) === null || _a === void 0 ? void 0 : _a.setSource) === 'function') {
        model.sharedModel.setSource(source);
    }
    else {
        model.sharedModel.source = source;
    }
}
function setCellMetadata(panel, index, metadata) {
    const cell = panel.content.widgets[index];
    if (!cell) {
        return;
    }
    for (const [key, value] of Object.entries(metadata)) {
        cell.model.setMetadata(key, value);
    }
}
async function saveNotebook(panel) {
    await panel.context.save();
}
async function runCell(panel, index) {
    panel.content.activeCellIndex = index;
    panel.content.scrollToItem(index, 'smart');
    const ok = await _jupyterlab_notebook__WEBPACK_IMPORTED_MODULE_2__.NotebookActions.run(panel.content, panel.sessionContext);
    await saveNotebook(panel);
    return Boolean(ok);
}
async function runActiveCell(notebooks) {
    const panel = activeNotebook(notebooks);
    await ensureKernel(panel);
    if (panel.content.activeCellIndex < 0) {
        panel.content.activeCellIndex = 0;
    }
    const index = panel.content.activeCellIndex;
    const ok = await runCell(panel, index);
    return {
        ok,
        notebookPath: panel.context.path,
        activeCellIndex: index
    };
}
function silentAttachSource(repo, notebookPath) {
    return [
        'from mordornotebook import attach',
        '',
        `MORDOR_REPO = ${JSON.stringify(repo)}`,
        `MORDOR_GOAL = ${JSON.stringify(`JupyterLab Mordor button: ${notebookPath}`)}`,
        '',
        'existing_mordor = globals().get("mordor")',
        'if existing_mordor is None or not hasattr(existing_mordor, "panel"):',
        '    mordor = attach(repo=MORDOR_REPO, goal=MORDOR_GOAL)',
        'else:',
        '    mordor = existing_mordor',
        ''
    ].join('\n');
}
async function openMordorPanel(notebooks) {
    var _a;
    const panel = activeNotebook(notebooks);
    await ensureKernel(panel);
    const repo = defaultRepo();
    const kernel = (_a = panel.sessionContext.session) === null || _a === void 0 ? void 0 : _a.kernel;
    if (!kernel) {
        throw new Error('Active notebook has no running kernel after startup.');
    }
    const future = kernel.requestExecute({
        code: silentAttachSource(repo, panel.context.path),
        silent: true,
        store_history: false
    }, false);
    await future.done;
    const context = notebookContext(panel);
    await callMordorApi('session', 'POST', { browser_session: { ...context, notebook_url: window.location.pathname } });
    const markup = await callMordorApi('panel/markup');
    const html = String(markup.html || '');
    if (!html.trim()) {
        throw new Error('Mordor server returned empty panel markup.');
    }
    renderPanelMarkup(html);
    await saveNotebook(panel);
    return {
        ok: true,
        notebookPath: panel.context.path,
        repo,
        inserted: [],
        renderedPanel: true
    };
}
function renderPanelMarkup(html) {
    document.querySelectorAll('[data-mordor-product-panel]').forEach((node) => node.remove());
    const template = document.createElement('template');
    template.innerHTML = html;
    const nodes = Array.from(template.content.childNodes);
    for (const node of nodes) {
        if (node.nodeName.toLowerCase() === 'script') {
            const script = document.createElement('script');
            script.textContent = node.textContent || '';
            document.body.appendChild(script);
        }
        else {
            document.body.appendChild(node);
        }
    }
}
function insertedCellInfo(panel, index, spec) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k;
    const cell = panel.content.widgets[index];
    const outputs = (_a = cell === null || cell === void 0 ? void 0 : cell.model) === null || _a === void 0 ? void 0 : _a.outputs;
    let hasError = false;
    let errorName = '';
    let errorValue = '';
    if (outputs && typeof outputs.length === 'number') {
        for (let i = 0; i < outputs.length; i += 1) {
            const output = typeof outputs.get === 'function' ? outputs.get(i) : null;
            const data = (output === null || output === void 0 ? void 0 : output.toJSON) ? output.toJSON() : output;
            if ((data === null || data === void 0 ? void 0 : data.output_type) === 'error' || (data === null || data === void 0 ? void 0 : data.type) === 'error') {
                hasError = true;
                errorName = String((_d = (_c = (_b = data.ename) !== null && _b !== void 0 ? _b : data.errorName) !== null && _c !== void 0 ? _c : data.name) !== null && _d !== void 0 ? _d : '');
                errorValue = String((_g = (_f = (_e = data.evalue) !== null && _e !== void 0 ? _e : data.errorValue) !== null && _f !== void 0 ? _f : data.message) !== null && _g !== void 0 ? _g : '');
                break;
            }
        }
    }
    return {
        index,
        role: (_h = spec.role) !== null && _h !== void 0 ? _h : null,
        cell_type: spec.cell_type,
        first_line: (_j = spec.source.split(/\r?\n/, 1)[0]) !== null && _j !== void 0 ? _j : '',
        model_id: (_k = cell === null || cell === void 0 ? void 0 : cell.model.id) !== null && _k !== void 0 ? _k : null,
        output_count: typeof (outputs === null || outputs === void 0 ? void 0 : outputs.length) === 'number' ? outputs.length : 0,
        has_error: hasError,
        error_name: errorName || null,
        error_value: errorValue || null
    };
}
async function insertCells(notebooks, cells, options = {}) {
    var _a, _b;
    const panel = activeNotebook(notebooks);
    const onEvent = options.onEvent;
    if (cells.some((cell) => cell.execute && cell.cell_type === 'code')) {
        await ensureKernel(panel, onEvent);
    }
    const requestId = safeRequestId(String((_a = options.requestId) !== null && _a !== void 0 ? _a : ''));
    const notebook = panel.content;
    const inserted = [];
    for (const spec of cells) {
        const beforeCount = notebook.widgets.length;
        notebook.activeCellIndex = Math.max(0, notebook.widgets.length - 1);
        _jupyterlab_notebook__WEBPACK_IMPORTED_MODULE_2__.NotebookActions.insertBelow(notebook);
        _jupyterlab_notebook__WEBPACK_IMPORTED_MODULE_2__.NotebookActions.changeCellType(notebook, spec.cell_type);
        const index = notebook.activeCellIndex >= 0 ? notebook.activeCellIndex : beforeCount;
        setCellSource(panel, index, spec.source);
        setCellMetadata(panel, index, {
            mordor: {
                request_id: requestId,
                role: (_b = spec.role) !== null && _b !== void 0 ? _b : null,
                inserted_by: 'mordor-labextension',
                inserted_at: new Date().toISOString()
            }
        });
        panel.content.scrollToItem(index, 'smart');
        inserted.push(insertedCellInfo(panel, index, spec));
        if (spec.execute && spec.cell_type === 'code') {
            const ok = await runCell(panel, index);
            inserted[inserted.length - 1].executed = ok;
            inserted[inserted.length - 1] = {
                ...inserted[inserted.length - 1],
                ...insertedCellInfo(panel, index, spec)
            };
        }
    }
    await saveNotebook(panel);
    return {
        ok: true,
        requestId,
        notebookPath: panel.context.path,
        inserted
    };
}
async function ask(notebooks, payload, onEvent) {
    const requestId = safeRequestId(payload.requestId);
    const events = [];
    const emit = (status, message, detail) => {
        const event = { status, message, detail };
        events.push(event);
        if (onEvent) {
            onEvent(event);
        }
    };
    try {
        const panel = activeNotebook(notebooks);
        emit('queued', 'Prompt received');
        emit('reading_notebook', `Using active notebook ${panel.context.path}`, notebookContext(panel));
        emit('agent_required', 'Prompt will be handled by the selected managed agent backend.');
        return {
            ok: false,
            handled: false,
            requestId,
            notebookPath: panel.context.path,
            events,
            cells: [],
            error: 'Prompt requires the selected managed agent backend.'
        };
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        emit('failed', message);
        return {
            ok: false,
            handled: true,
            requestId,
            notebookPath: '',
            events,
            cells: [],
            error: message
        };
    }
}
function createApi(notebooks) {
    return {
        version: '0.2.0',
        currentNotebook: () => notebookContext(activeNotebook(notebooks)),
        runActiveCell: () => runActiveCell(notebooks),
        openPanel: () => openMordorPanel(notebooks),
        insertCells: (cells, options) => insertCells(notebooks, cells, options),
        ask: (payload, onEvent) => ask(notebooks, payload, onEvent)
    };
}
class MordorNotebookButtonExtension {
    constructor(app) {
        this.app = app;
    }
    createNew(panel) {
        const button = new _jupyterlab_apputils__WEBPACK_IMPORTED_MODULE_0__.ToolbarButton({
            label: 'Mordor',
            tooltip: 'Open Mordor Notebook in this notebook',
            onClick: () => {
                void this.app.commands.execute(OPEN_PANEL_COMMAND);
            }
        });
        panel.toolbar.insertItem(10, 'mordor-notebook', button);
        return button;
    }
}
const plugin = {
    id: 'mordornotebook:live-notebook',
    autoStart: true,
    requires: [_jupyterlab_notebook__WEBPACK_IMPORTED_MODULE_2__.INotebookTracker],
    optional: [_jupyterlab_mainmenu__WEBPACK_IMPORTED_MODULE_1__.IMainMenu],
    activate: (app, notebooks, mainMenu) => {
        window.mordorNotebookLab = createApi(notebooks);
        app.commands.addCommand(OPEN_PANEL_COMMAND, {
            label: 'Open Mordor Notebook',
            caption: 'Open the Mordor Notebook prompt panel in the active notebook',
            isEnabled: () => Boolean(notebooks.currentWidget),
            execute: async () => {
                try {
                    return await openMordorPanel(notebooks);
                }
                catch (error) {
                    await (0,_jupyterlab_apputils__WEBPACK_IMPORTED_MODULE_0__.showErrorMessage)('Mordor Notebook failed to open', error instanceof Error ? error : String(error));
                    throw error;
                }
            }
        });
        if (mainMenu) {
            const menu = new _lumino_widgets__WEBPACK_IMPORTED_MODULE_3__.Menu({ commands: app.commands });
            menu.title.label = 'Mordor';
            menu.addItem({ command: OPEN_PANEL_COMMAND });
            mainMenu.addMenu(menu, true, { rank: 90 });
        }
        app.docRegistry.addWidgetExtension('Notebook', new MordorNotebookButtonExtension(app));
        console.log('Mordor Notebook JupyterLab extension activated');
    }
};
/* harmony default export */ const __WEBPACK_DEFAULT_EXPORT__ = (plugin);


/***/ }

}]);
//# sourceMappingURL=lib_index_js.8c5e2f068ba0a08e5f4c.js.map
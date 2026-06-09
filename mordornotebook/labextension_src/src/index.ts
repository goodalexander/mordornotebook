import { JupyterFrontEnd, JupyterFrontEndPlugin } from '@jupyterlab/application';
import { showErrorMessage, ToolbarButton } from '@jupyterlab/apputils';
import { DocumentRegistry } from '@jupyterlab/docregistry';
import { IMainMenu } from '@jupyterlab/mainmenu';
import { INotebookModel, INotebookTracker, NotebookActions, NotebookPanel } from '@jupyterlab/notebook';
import { Menu } from '@lumino/widgets';

type CellKind = 'markdown' | 'code';

interface MordorCellSpec {
  cell_type: CellKind;
  source: string;
  role?: string;
  execute?: boolean;
}

interface MordorAskPayload {
  prompt: string;
  requestId?: string;
  repo?: string;
  sessionId?: string;
}

interface MordorEvent {
  status: string;
  message: string;
  detail?: Record<string, unknown>;
}

interface MordorAskResult {
  ok: boolean;
  handled?: boolean;
  requestId: string;
  notebookPath: string;
  events: MordorEvent[];
  cells: Array<Record<string, unknown>>;
  error?: string;
}

declare global {
  interface Window {
    mordorNotebookLab?: MordorLabApi;
  }
}

interface MordorLabApi {
  version: string;
  currentNotebook: () => Record<string, unknown>;
  runActiveCell: () => Promise<Record<string, unknown>>;
  openPanel: () => Promise<Record<string, unknown>>;
  insertCells: (cells: MordorCellSpec[], options?: Record<string, unknown>) => Promise<Record<string, unknown>>;
  ask: (payload: MordorAskPayload, onEvent?: (event: MordorEvent) => void) => Promise<MordorAskResult>;
}

const OPEN_PANEL_COMMAND = 'mordornotebook:open-panel';

function activeNotebook(notebooks: INotebookTracker): NotebookPanel {
  const panel = notebooks.currentWidget;
  if (!panel || !panel.content || !panel.context) {
    throw new Error('No active JupyterLab notebook is selected.');
  }
  if (!panel.context.path) {
    throw new Error('Active notebook has no document path.');
  }
  return panel;
}

function sourceLines(source: string): string[] {
  if (!source) {
    return [];
  }
  const lines = source.split(/\r?\n/);
  return lines.map((line, index) => (index < lines.length - 1 ? `${line}\n` : line));
}

function safeRequestId(value?: string): string {
  if (value && /^[A-Za-z0-9_.:-]+$/.test(value)) {
    return value;
  }
  const cryptoObj = globalThis.crypto;
  if (cryptoObj && typeof cryptoObj.randomUUID === 'function') {
    return cryptoObj.randomUUID();
  }
  return `mordor-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function localStorageValue(key: string, fallback: string): string {
  try {
    return window.localStorage.getItem(key) || fallback;
  } catch (error) {
    return fallback;
  }
}

function defaultRepo(): string {
  return localStorageValue('mordorDefaultRepo', '');
}

function normalizeBase(value: string): string {
  let base = String(value || '/').trim() || '/';
  if (!base.startsWith('/')) {
    base = `/${base}`;
  }
  if (!base.endsWith('/')) {
    base += '/';
  }
  return base;
}

function jupyterConfigBase(): string {
  const node = document.getElementById('jupyter-config-data');
  if (!node || !node.textContent) {
    return '';
  }
  try {
    const cfg = JSON.parse(node.textContent);
    return cfg.baseUrl || cfg.base_url || '';
  } catch (error) {
    return '';
  }
}

function inferApiBase(): string {
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

async function callMordorApi(path: string, method = 'GET', body: Record<string, unknown> | null = null): Promise<Record<string, unknown>> {
  const response = await fetch(new URL(path.replace(/^\/+/, ''), inferApiBase()).toString(), {
    method,
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : null
  });
  const text = await response.text();
  let payload: unknown;
  try {
    payload = JSON.parse(text);
  } catch (error) {
    payload = text;
  }
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${response.statusText}: ${typeof payload === 'string' ? payload : JSON.stringify(payload)}`);
  }
  return payload as Record<string, unknown>;
}

function notebookContext(panel: NotebookPanel): Record<string, unknown> {
  return {
    notebook_path: panel.context.path,
    kernel_id: panel.sessionContext.session?.kernel?.id ?? null,
    kernel_name: panel.sessionContext.session?.kernel?.name ?? null,
    kernel_display_name: panel.sessionContext.kernelDisplayName ?? null,
    kernel_status: panel.sessionContext.kernelDisplayStatus ?? null,
    kernel_ready: Boolean(panel.sessionContext?.session?.kernel),
    session_id: panel.sessionContext.session?.id ?? null,
    active_cell_index: panel.content.activeCellIndex,
    cell_count: panel.content.widgets.length,
    dirty: panel.context.model.dirty
  };
}

async function ensureKernel(
  panel: NotebookPanel,
  onEvent?: (status: string, message: string, detail?: Record<string, unknown>) => void
): Promise<void> {
  if (panel.sessionContext?.session?.kernel) {
    return;
  }
  onEvent?.('waiting_for_kernel', 'Waiting for the active notebook kernel');
  if (!panel.sessionContext.isReady) {
    await panel.sessionContext.ready;
  }
  if (panel.sessionContext?.session?.kernel) {
    return;
  }
  onEvent?.('starting_kernel', 'Starting a kernel for the active notebook');
  await panel.sessionContext.initialize();
  if (!panel.sessionContext?.session?.kernel) {
    await panel.sessionContext.startKernel();
  }
  if (!panel.sessionContext?.session?.kernel) {
    throw new Error('Active notebook has no running kernel after JupyterLab kernel startup.');
  }
}

function setCellSource(panel: NotebookPanel, index: number, source: string): void {
  const cell = panel.content.widgets[index];
  if (!cell) {
    throw new Error(`Inserted cell index ${index} is not visible in the notebook model.`);
  }
  const model = cell.model;
  if (typeof model.sharedModel?.setSource === 'function') {
    model.sharedModel.setSource(source);
  } else {
    model.sharedModel.source = source;
  }
}

function setCellMetadata(panel: NotebookPanel, index: number, metadata: Record<string, unknown>): void {
  const cell = panel.content.widgets[index];
  if (!cell) {
    return;
  }
  for (const [key, value] of Object.entries(metadata)) {
    cell.model.setMetadata(key, value as never);
  }
}

async function saveNotebook(panel: NotebookPanel): Promise<void> {
  await panel.context.save();
}

async function runCell(panel: NotebookPanel, index: number): Promise<boolean> {
  panel.content.activeCellIndex = index;
  panel.content.scrollToItem(index, 'smart');
  const ok = await NotebookActions.run(panel.content, panel.sessionContext);
  await saveNotebook(panel);
  return Boolean(ok);
}

async function runActiveCell(notebooks: INotebookTracker): Promise<Record<string, unknown>> {
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

function silentAttachSource(repo: string, notebookPath: string): string {
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

async function openMordorPanel(notebooks: INotebookTracker): Promise<Record<string, unknown>> {
  const panel = activeNotebook(notebooks);
  await ensureKernel(panel);
  const repo = defaultRepo();
  const kernel = panel.sessionContext.session?.kernel;
  if (!kernel) {
    throw new Error('Active notebook has no running kernel after startup.');
  }
  const future = kernel.requestExecute(
    {
      code: silentAttachSource(repo, panel.context.path),
      silent: true,
      store_history: false
    },
    false
  );
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

function renderPanelMarkup(html: string): void {
  document.querySelectorAll('[data-mordor-product-panel]').forEach((node) => node.remove());
  const template = document.createElement('template');
  template.innerHTML = html;
  const nodes = Array.from(template.content.childNodes);
  for (const node of nodes) {
    if (node.nodeName.toLowerCase() === 'script') {
      const script = document.createElement('script');
      script.textContent = node.textContent || '';
      document.body.appendChild(script);
    } else {
      document.body.appendChild(node);
    }
  }
}

function insertedCellInfo(panel: NotebookPanel, index: number, spec: MordorCellSpec): Record<string, unknown> {
  const cell = panel.content.widgets[index];
  const outputs = (cell?.model as any)?.outputs;
  let hasError = false;
  let errorName = '';
  let errorValue = '';
  if (outputs && typeof outputs.length === 'number') {
    for (let i = 0; i < outputs.length; i += 1) {
      const output = typeof outputs.get === 'function' ? outputs.get(i) : null;
      const data = output?.toJSON ? output.toJSON() : output;
      if (data?.output_type === 'error' || data?.type === 'error') {
        hasError = true;
        errorName = String(data.ename ?? data.errorName ?? data.name ?? '');
        errorValue = String(data.evalue ?? data.errorValue ?? data.message ?? '');
        break;
      }
    }
  }
  return {
    index,
    role: spec.role ?? null,
    cell_type: spec.cell_type,
    first_line: spec.source.split(/\r?\n/, 1)[0] ?? '',
    model_id: cell?.model.id ?? null,
    output_count: typeof outputs?.length === 'number' ? outputs.length : 0,
    has_error: hasError,
    error_name: errorName || null,
    error_value: errorValue || null
  };
}

async function insertCells(
  notebooks: INotebookTracker,
  cells: MordorCellSpec[],
  options: Record<string, unknown> = {}
): Promise<Record<string, unknown>> {
  const panel = activeNotebook(notebooks);
  const onEvent = options.onEvent as ((status: string, message: string, detail?: Record<string, unknown>) => void) | undefined;
  if (cells.some((cell) => cell.execute && cell.cell_type === 'code')) {
    await ensureKernel(panel, onEvent);
  }
  const requestId = safeRequestId(String(options.requestId ?? ''));
  const notebook = panel.content;
  const inserted: Array<Record<string, unknown>> = [];

  for (const spec of cells) {
    const beforeCount = notebook.widgets.length;
    notebook.activeCellIndex = Math.max(0, notebook.widgets.length - 1);
    NotebookActions.insertBelow(notebook);
    NotebookActions.changeCellType(notebook, spec.cell_type);
    const index = notebook.activeCellIndex >= 0 ? notebook.activeCellIndex : beforeCount;
    setCellSource(panel, index, spec.source);
    setCellMetadata(panel, index, {
      mordor: {
        request_id: requestId,
        role: spec.role ?? null,
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

async function ask(
  notebooks: INotebookTracker,
  payload: MordorAskPayload,
  onEvent?: (event: MordorEvent) => void
): Promise<MordorAskResult> {
  const requestId = safeRequestId(payload.requestId);
  const events: MordorEvent[] = [];
  const emit = (status: string, message: string, detail?: Record<string, unknown>) => {
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
  } catch (error) {
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

function createApi(notebooks: INotebookTracker): MordorLabApi {
  return {
    version: '0.2.0',
    currentNotebook: () => notebookContext(activeNotebook(notebooks)),
    runActiveCell: () => runActiveCell(notebooks),
    openPanel: () => openMordorPanel(notebooks),
    insertCells: (cells: MordorCellSpec[], options?: Record<string, unknown>) => insertCells(notebooks, cells, options),
    ask: (payload: MordorAskPayload, onEvent?: (event: MordorEvent) => void) => ask(notebooks, payload, onEvent)
  };
}

class MordorNotebookButtonExtension implements DocumentRegistry.IWidgetExtension<NotebookPanel, INotebookModel> {
  constructor(private readonly app: JupyterFrontEnd) {}

  createNew(panel: NotebookPanel): ToolbarButton {
    const button = new ToolbarButton({
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

const plugin: JupyterFrontEndPlugin<void> = {
  id: 'mordornotebook:live-notebook',
  autoStart: true,
  requires: [INotebookTracker],
  optional: [IMainMenu],
  activate: (app: JupyterFrontEnd, notebooks: INotebookTracker, mainMenu: IMainMenu | null) => {
    window.mordorNotebookLab = createApi(notebooks);
    app.commands.addCommand(OPEN_PANEL_COMMAND, {
      label: 'Open Mordor Notebook',
      caption: 'Open the Mordor Notebook prompt panel in the active notebook',
      isEnabled: () => Boolean(notebooks.currentWidget),
      execute: async () => {
        try {
          return await openMordorPanel(notebooks);
        } catch (error) {
          await showErrorMessage('Mordor Notebook failed to open', error instanceof Error ? error : String(error));
          throw error;
        }
      }
    });
    if (mainMenu) {
      const menu = new Menu({ commands: app.commands });
      menu.title.label = 'Mordor';
      menu.addItem({ command: OPEN_PANEL_COMMAND });
      mainMenu.addMenu(menu, true, { rank: 90 });
    }
    app.docRegistry.addWidgetExtension('Notebook', new MordorNotebookButtonExtension(app));
    console.log('Mordor Notebook JupyterLab extension activated');
  }
};

export default plugin;

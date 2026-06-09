"""Notebook-rendered Mordor controls."""

from __future__ import annotations

import html
from typing import Any


def panel_markup(session: Any) -> str:
    metadata = session.metadata()
    repo = html.escape(str(metadata.get("repo") or "not configured"))
    session_id = html.escape(str(metadata.get("session_id")))
    repo_json = html.escape(str(metadata.get("repo") or ""))
    session_json = html.escape(str(metadata.get("session_id") or ""))
    panel_id = f"mordor-{str(metadata.get('session_id')).replace('-', '')}"
    return f"""
    <div id="{panel_id}" data-mordor-product-panel style="position:fixed;right:16px;top:72px;z-index:9999;width:430px;max-height:84vh;overflow:auto;background:#111;color:#f5f5f5;border:1px solid #555;padding:12px;font-family:system-ui,sans-serif;box-shadow:0 12px 30px rgba(0,0,0,.28)">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
        <h3 style="margin:0 0 8px 0;font-size:16px">Mordor Notebook</h3>
        <button type="button" data-mordor-close style="background:#333;color:#fff;border:1px solid #666;padding:2px 8px">x</button>
      </div>
      <div style="font-size:12px;line-height:1.35;color:#ddd">
        <div><b>Repo:</b> <code>{repo}</code></div>
        <div><b>Notebook:</b> <code data-mordor-notebook>detecting active notebook...</code></div>
        <div><b>Status:</b> <span data-mordor-status style="display:inline-block;padding:2px 6px;border:1px solid #666;background:#222;color:#f5f5f5">Starting</span></div>
        <label style="display:flex;align-items:center;gap:6px;margin-top:6px"><b>Agent:</b>
          <select data-mordor-agent-select style="flex:1;min-width:0;background:#1d1d1d;color:#fff;border:1px solid #555;padding:4px">
            <option value="codex">Codex</option>
            <option value="cursor">Cursor</option>
          </select>
        </label>
      </div>
      <textarea data-mordor-prompt style="box-sizing:border-box;width:100%;height:104px;margin-top:10px;background:#1d1d1d;color:#fff;border:1px solid #555;padding:8px;resize:vertical" placeholder="Ask Mordor to inspect this notebook or add notebook cells..."></textarea>
      <div style="display:flex;gap:8px;margin:8px 0">
        <button type="button" data-mordor-send style="flex:1;background:#f5f5f5;color:#111;border:0;padding:8px;font-weight:600">Send</button>
        <button type="button" data-mordor-stop style="display:none;background:#332711;color:#ffe8b8;border:1px solid #a87928;padding:8px;font-weight:600">Stop</button>
      </div>
      <div data-mordor-warning style="display:none;margin:8px 0;padding:8px;border:1px solid #a66;background:#2b1111;color:#ffd6d6;font-size:12px"></div>
      <div style="margin-top:10px">
        <div style="font-size:12px;font-weight:700;color:#f5f5f5;margin-bottom:4px">Activity</div>
        <ul data-mordor-activity style="margin:0;padding-left:18px;font-size:12px;line-height:1.45;color:#ddd"><li>Waiting for JupyterLab extension</li></ul>
      </div>
      <div style="margin-top:10px">
        <div style="font-size:12px;font-weight:700;color:#f5f5f5;margin-bottom:4px">Generated Cells</div>
        <ul data-mordor-cells style="margin:0;padding-left:18px;font-size:12px;line-height:1.45;color:#ddd"><li>none yet</li></ul>
      </div>
      <details style="margin-top:10px">
        <summary style="cursor:pointer;font-size:12px;color:#ddd">Agent Log</summary>
        <pre data-mordor-log style="white-space:pre-wrap;max-height:180px;overflow:auto;background:#050505;color:#ddd;border:1px solid #333;padding:8px;margin:6px 0 0"></pre>
      </details>
    </div>
    <script>
    (() => {{
      const root = document.getElementById({panel_id!r});
      if (!root) return;
      const repo = {repo_json!r};
      const sessionId = {session_json!r};
      const prompt = root.querySelector('[data-mordor-prompt]');
      const send = root.querySelector('[data-mordor-send]');
      const stop = root.querySelector('[data-mordor-stop]');
      const agentSelect = root.querySelector('[data-mordor-agent-select]');
      const notebookNode = root.querySelector('[data-mordor-notebook]');
      const statusNode = root.querySelector('[data-mordor-status]');
      const warning = root.querySelector('[data-mordor-warning]');
      const activity = root.querySelector('[data-mordor-activity]');
      const cells = root.querySelector('[data-mordor-cells]');
      const log = root.querySelector('[data-mordor-log]');
      let busy = false;
      let abortRequested = false;
      let activeAgentSession = null;
      let activeAgentBackend = null;
      let stopSent = false;
      const appliedOperationIds = new Set();
      const localSetting = (key, fallback) => {{
        try {{
          const value = window.localStorage.getItem(key);
          return value || fallback;
        }} catch (err) {{
          return fallback;
        }}
      }};
      const positiveNumberSetting = (key, fallback) => {{
        const raw = Number(localSetting(key, String(fallback)));
        return Number.isFinite(raw) && raw > 0 ? raw : fallback;
      }};
      const codexCommand = localSetting('mordorCodexCommand', 'codex --sandbox danger-full-access --ask-for-approval never');
      const cursorCommand = localSetting('mordorCursorCommand', 'cursor-agent');
      const cursorModel = localSetting('mordorCursorModel', '');
      const cursorSandbox = localSetting('mordorCursorSandbox', 'disabled');
      const cursorForce = true;
      const initialBackend = localSetting('mordorAgentBackend', 'codex').toLowerCase() === 'cursor' ? 'cursor' : 'codex';
      agentSelect.value = initialBackend;
      agentSelect.onchange = () => {{
        try {{ window.localStorage.setItem('mordorAgentBackend', agentSelect.value); }} catch (err) {{}}
      }};
      const agentTimeoutMs = positiveNumberSetting('mordorAgentTimeoutMs', 12 * 60 * 1000);
      const agentStallMs = positiveNumberSetting('mordorAgentStallMs', 90 * 1000);
      const mordorctl = (repo || '').replace(/\\/$/, '') + '/.venv/bin/mordorctl';
      const selectedBackend = () => agentSelect.value === 'cursor' ? 'cursor' : 'codex';
      const agentLabel = (backend) => backend === 'cursor' ? 'Cursor' : 'Codex';
      const setStatus = (label, tone='neutral') => {{
        statusNode.textContent = label;
        const colors = {{
          neutral: ['#222', '#f5f5f5', '#666'],
          running: ['#182234', '#d7e7ff', '#4777bb'],
          ok: ['#132417', '#d8ffdf', '#4a8b58'],
          warn: ['#332711', '#ffe8b8', '#a87928'],
          fail: ['#341818', '#ffd6d6', '#a66']
        }};
        const [bg, fg, border] = colors[tone] || colors.neutral;
        statusNode.style.background = bg;
        statusNode.style.color = fg;
        statusNode.style.borderColor = border;
      }};
      const clearList = (node) => {{ node.innerHTML = ''; }};
      const append = (node, text) => {{
        const li = document.createElement('li');
        li.textContent = text;
        node.appendChild(li);
      }};
      const setWarning = (text) => {{
        warning.textContent = text || '';
        warning.style.display = text ? 'block' : 'none';
      }};
      const normalizeBase = (value) => {{
        let base = String(value || '/').trim() || '/';
        if (!base.startsWith('/')) base = '/' + base;
        if (!base.endsWith('/')) base += '/';
        return base;
      }};
      const jupyterConfigBase = () => {{
        const node = document.getElementById('jupyter-config-data');
        if (!node || !node.textContent) return '';
        try {{
          const cfg = JSON.parse(node.textContent);
          return cfg.baseUrl || cfg.base_url || '';
        }} catch (err) {{
          return '';
        }}
      }};
      const inferBase = () => {{
        const configured = jupyterConfigBase();
        if (configured) return normalizeBase(configured);
        const path = window.location.pathname || '/';
        const markers = ['/lab', '/notebooks/', '/tree/'];
        for (const marker of markers) {{
          const idx = path.indexOf(marker);
          if (idx >= 0) return normalizeBase(path.slice(0, idx + 1));
        }}
        return '/';
      }};
      const apiBase = new URL(inferBase() + 'mordor/api/', window.location.origin).toString();
      const endpoint = (path) => new URL(String(path || '').replace(/^\\/+/, ''), apiBase).toString();
      const call = async (path, method='GET', body=null) => {{
        const response = await fetch(endpoint(path), {{
          method,
          credentials: 'same-origin',
          headers: {{'Content-Type': 'application/json'}},
          body: body ? JSON.stringify(body) : null
        }});
        const text = await response.text();
        let payload;
        try {{ payload = JSON.parse(text); }} catch {{ payload = text; }}
        if (!response.ok) {{
          throw new Error(`HTTP ${{response.status}} ${{response.statusText}}: ${{typeof payload === 'string' ? payload : JSON.stringify(payload)}}`);
        }}
        return payload;
      }};
      const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const showStop = (visible) => {{
        stop.style.display = visible ? 'inline-block' : 'none';
        stop.disabled = !visible;
      }};
      const firstLine = (source) => String(source || '').split(/\\r?\\n/, 1)[0] || '';
      const escapeRegExp = (source) => String(source || '').replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
      const jsonEventText = (event) => {{
        if (!event || !['assistant', 'result'].includes(String(event.type || ''))) return '';
        if (typeof event.result === 'string') return event.result;
        const content = event.message && event.message.content;
        if (Array.isArray(content)) {{
          return content.map((part) => typeof part === 'string' ? part : String((part && part.text) || '')).join('');
        }}
        return typeof content === 'string' ? content : '';
      }};
      const agentCompletionSeen = (captureText, doneMarker, donePattern) => {{
        if (donePattern.test(captureText)) return true;
        for (const line of String(captureText || '').split(/\\r?\\n/)) {{
          let event;
          try {{ event = JSON.parse(line); }} catch {{ continue; }}
          if (jsonEventText(event).includes(doneMarker)) return true;
        }}
        return false;
      }};
      const lab = () => window.mordorNotebookLab;
      const postNotebookContext = async () => {{
        const ctx = lab().currentNotebook();
        notebookNode.textContent = ctx.notebook_path || '(unknown)';
        await call('session', 'POST', {{browser_session: {{...ctx, notebook_url: window.location.pathname}}}});
        return ctx;
      }};
      const syncNotebook = async () => {{
        if (!lab()) {{
          notebookNode.textContent = 'JupyterLab extension not active';
          setStatus('Blocked', 'fail');
          setWarning('Mordor JupyterLab extension is not active. Restart JupyterLab after installing/enabling the labextension.');
          return false;
        }}
        try {{
          const ctx = await postNotebookContext();
          setWarning('');
          setStatus(ctx.kernel_ready ? 'Ready' : 'Ready: kernel pending', ctx.kernel_ready ? 'ok' : 'warn');
          clearList(activity);
          append(activity, `Ready in ${{ctx.notebook_path}}`);
          append(activity, `Agent backend: ${{agentLabel(selectedBackend())}}`);
          if (!ctx.kernel_ready) append(activity, 'Kernel will start when generated code needs to run');
          return true;
        }} catch (err) {{
          notebookNode.textContent = 'no active notebook';
          setStatus('Blocked', 'fail');
          setWarning(String(err && err.message ? err.message : err));
          return false;
        }}
      }};
      const recordEvent = (event) => {{
        if (!event) return;
        const label = event.message || event.status || JSON.stringify(event);
        append(activity, label);
        if (event.status) {{
          const tone = event.status === 'failed' ? 'fail' : event.status === 'complete' ? 'ok' : 'running';
          setStatus(event.status.replaceAll('_', ' '), tone);
        }}
      }};
      const appendCellRow = (cell) => {{
        append(cells, `${{cell.cell_type}}: ${{cell.role || cell.first_line || 'generated cell'}}`);
      }};
      const applyCellOperation = async (op, minCreatedAt=0) => {{
        if (!op || op.op_type !== 'insert_cell' || !op.id || appliedOperationIds.has(op.id)) return null;
        if (sessionId && op.session_id && op.session_id !== sessionId) return null;
        if (!['queued', 'persisted', 'runtime_delivery_attempted'].includes(String(op.status || ''))) return null;
        const createdAt = Date.parse(String(op.created_at || ''));
        if (minCreatedAt && Number.isFinite(createdAt) && createdAt < minCreatedAt) return null;
        const cellType = op.cell_type === 'markdown' ? 'markdown' : 'code';
        const source = String(op.source || '');
        if (!source.trim()) return null;
        const inserted = await lab().insertCells(
          [{{cell_type: cellType, source, role: op.id, execute: cellType === 'code'}}],
          {{requestId: op.id}}
        );
        appliedOperationIds.add(op.id);
        await call(`notebook/ops/${{encodeURIComponent(op.id)}}/ack`, 'POST', {{status: 'live_applied'}});
        return {{
          cell_type: cellType,
          role: op.id,
          first_line: firstLine(source),
          inserted
        }};
      }};
      const applyAvailableCellOperations = async (minCreatedAt=0) => {{
        const payload = await call('notebook/ops');
        const ops = Array.isArray(payload.operations) ? payload.operations.slice().reverse() : [];
        const applied = [];
        for (const op of ops) {{
          const row = await applyCellOperation(op, minCreatedAt);
          if (row) applied.push(row);
        }}
        if (applied.length) await postNotebookContext();
        return applied;
      }};
      const buildAgentPrompt = (userText, requestId, backend) => [
        'You are operating inside a live Jupyter notebook through Mordor Notebook.',
        '',
        `User prompt: ${{userText}}`,
        `Request id: ${{requestId}}`,
        `Repository: ${{repo}}`,
        `Agent backend: ${{agentLabel(backend)}}`,
        `Use this exact mordorctl binary: ${{mordorctl}}`,
        '',
        'Rules:',
        '- Do not edit notebook files directly.',
        '- Do not ask the user to run commands.',
        '- Inspect the active notebook context first with: mordorctl notebook context --json',
        '- Inspect in-kernel memory with: mordorctl memory list --json',
        '- Before writing notebook code, run: mordorctl helpers ensure --json',
        '- Before creating any new helper or analysis code, run: mordorctl helpers list --json and check mordor/helpers.json for an existing helper.',
        '- Prefer short notebook cells that import and call repo-local helpers from mordorhelper; put reusable logic in helper modules, not giant inline notebook code blocks.',
        '- If no helper fits, create or update a small accessible helper under mordorhelper/ and update mordor/helpers.json with a plain-English description, import path, call shape, inputs, and outputs.',
        '- Notebook cells should contain request parameters, helper imports, helper calls, and display calls only when practical.',
        '- Inspect the repo as needed with rg and normal shell reads.',
        '- Answer by creating complete notebook cells with mordorctl cell insert.',
        '- Insert a markdown audit/summary cell first when useful.',
        '- Insert executable code cells when the user asks for data inspection, charts, or calculations.',
        '- Keep generated cells bounded and runnable in the active notebook.',
        '- The first line of every generated cell must include "Mordor generated".',
        backend === 'cursor' ? '- Cursor may load repo rules, AGENTS.md, MCP, and skills; use them only when they help, but this notebook cell contract is mandatory.' : '- Use the repo and shell tools normally, but this notebook cell contract is mandatory.',
        '- Before printing the done marker, run: mordorctl cells list --json',
        '- Verify that list includes every generated cell you inserted; if the user asked for data inspection, charts, calculations, or executable work, verify that at least one generated code cell is present.',
        `- When all requested cells have been inserted and verified, print this marker as a standalone line: MORDOR_NOTEBOOK_DONE ${{requestId}}`,
        '',
        'Proceed now.'
      ].join('\\n');
      const stopActiveAgent = async () => {{
        if (!activeAgentSession || stopSent) return;
        stopSent = true;
        try {{
          await call('agent/stop', 'POST', {{
            repo,
            backend: activeAgentBackend || selectedBackend(),
            session: activeAgentSession,
            codex_command: codexCommand,
            cursor_command: cursorCommand,
            cursor_model: cursorModel,
            cursor_sandbox: cursorSandbox,
            cursor_force: cursorForce
          }});
        }} catch (err) {{
          append(activity, `Stop request failed: ${{err && err.message ? err.message : err}}`);
        }}
      }};
      const runAgentRequest = async (userText, requestId, backend) => {{
        const doneMarker = `MORDOR_NOTEBOOK_DONE ${{requestId}}`;
        const donePattern = new RegExp(`(^|\\\\n)\\\\s*${{escapeRegExp(doneMarker)}}\\\\s*($|\\\\n)`);
        const label = agentLabel(backend);
        const agentSession = `mordor-${{backend}}-${{requestId.replace(/[^A-Za-z0-9_.:-]+/g, '-')}}`;
        activeAgentSession = agentSession;
        activeAgentBackend = backend;
        const agentPrompt = buildAgentPrompt(userText, requestId, backend);
        const requestStartedAt = Date.now() - 1000;
        append(activity, `Starting managed ${{label}} agent`);
        const sent = await call('agent/send', 'POST', {{
          repo,
          backend,
          session: agentSession,
          codex_command: codexCommand,
          cursor_command: cursorCommand,
          cursor_model: cursorModel,
          cursor_sandbox: cursorSandbox,
          cursor_force: cursorForce,
          text: agentPrompt
        }});
        if (!sent.ok) {{
          throw new Error(sent.error || sent.stderr || `${{label}} agent did not accept the prompt.`);
        }}
        append(activity, `${{label}} agent working`);
        const appliedCells = [];
        const deadline = Date.now() + agentTimeoutMs;
        let lastProgressAt = Date.now();
        let lastAgentText = '';
        let stalled = false;
        let doneSeenAt = 0;
        let doneQuietCycles = 0;
        while (Date.now() < deadline) {{
          if (abortRequested) {{
            await stopActiveAgent();
            return {{
              ok: false,
              cancelled: true,
              requestId,
              events: [{{status: 'cancelled', message: 'Request cancelled by user'}}],
              cells: appliedCells,
              error: 'Request cancelled by user.'
            }};
          }}
          const applied = await applyAvailableCellOperations(requestStartedAt);
          for (const cell of applied) {{
            appliedCells.push(cell);
            appendCellRow(cell);
          }}
          if (applied.length) {{
            lastProgressAt = Date.now();
            stalled = false;
            doneQuietCycles = 0;
          }}
          let capture = null;
          try {{
            capture = await call(`agent/capture?session=${{encodeURIComponent(agentSession)}}&backend=${{encodeURIComponent(backend)}}`);
          }} catch (err) {{
            capture = {{ok: false, error: String(err && err.message ? err.message : err)}};
          }}
          const captureText = String((capture && capture.text) || '');
          if (captureText && captureText !== lastAgentText) {{
            lastAgentText = captureText;
            lastProgressAt = Date.now();
            stalled = false;
            log.textContent = captureText.slice(-12000);
          }}
          const exitMatch = captureText.match(/MORDOR_AGENT_EXIT_CODE=(\\d+)/);
          if (exitMatch && Number(exitMatch[1]) !== 0) {{
            await stopActiveAgent();
            throw new Error(`${{label}} agent exited with code ${{exitMatch[1]}} before completing the notebook request.`);
          }}
          if (agentCompletionSeen(captureText, doneMarker, donePattern)) {{
            if (!doneSeenAt) {{
              doneSeenAt = Date.now();
              doneQuietCycles = 0;
              append(activity, `${{label}} reported completion; draining queued notebook cells`);
            }} else if (!applied.length) {{
              doneQuietCycles += 1;
            }}
          }}
          if (doneSeenAt && appliedCells.length > 0 && doneQuietCycles >= 2) {{
            await postNotebookContext();
            await stopActiveAgent();
            return {{
              ok: true,
              requestId,
              notebookPath: String((lab().currentNotebook() || {{}}).notebook_path || ''),
              events: [{{status: 'complete', message: `${{label}} generated notebook cells`}}],
              cells: appliedCells
            }};
          }}
          if (!stalled && Date.now() - lastProgressAt > agentStallMs) {{
            stalled = true;
            setStatus('Stalled', 'warn');
            append(activity, `No new notebook cells or agent output for ${{Math.round(agentStallMs / 1000)}} seconds`);
            setWarning('The managed agent is still running but has not produced notebook changes. Stop it or wait for the timeout.');
          }}
          const pollDelayMs = doneSeenAt ? 500 : Math.min(3000, Math.max(250, Math.floor(agentStallMs / 3)));
          await sleep(pollDelayMs);
        }}
        await stopActiveAgent();
        throw new Error(`${{label}} agent did not finish inserting notebook cells before the ${{Math.round(agentTimeoutMs / 1000)}} second timeout.`);
      }};
      root.querySelector('[data-mordor-close]').onclick = () => root.remove();
      showStop(false);
      stop.onclick = async () => {{
        if (!busy) return;
        abortRequested = true;
        stop.disabled = true;
        setStatus('Cancelling', 'warn');
        append(activity, 'Cancellation requested');
        await stopActiveAgent();
      }};
      send.onclick = async () => {{
        if (busy) return;
        const text = prompt.value.trim();
        if (!text) {{
          setWarning('Enter a prompt first.');
          return;
        }}
        if (!(await syncNotebook())) return;
        busy = true;
        abortRequested = false;
        activeAgentSession = null;
        activeAgentBackend = null;
        stopSent = false;
        send.disabled = true;
        showStop(true);
        setWarning('');
        clearList(activity);
        clearList(cells);
        log.textContent = '';
        const requestId = 'mordor-' + Date.now().toString(36);
        try {{
          setStatus('Queued', 'running');
          append(activity, 'Prompt sent');
          let result = await lab().ask({{prompt: text, requestId, repo, sessionId}}, recordEvent);
          if (!result.ok && result.handled === false) {{
            append(activity, `Local notebook handler unavailable: ${{result.error || 'unsupported prompt'}}`);
            setWarning('');
            const backend = selectedBackend();
            setStatus(`${{agentLabel(backend)}} agent working`, 'running');
            result = await runAgentRequest(text, requestId, backend);
          }}
          log.textContent = JSON.stringify({{requestId, ok: result.ok, notebookPath: result.notebookPath, events: result.events}}, null, 2);
          clearList(cells);
          if (result.cells && result.cells.length) {{
            result.cells.forEach(appendCellRow);
          }} else {{
            append(cells, 'none');
          }}
          if (!result.ok && result.cancelled) {{
            setWarning(result.error || 'Request cancelled.');
            setStatus('Cancelled', 'warn');
          }} else if (!result.ok) {{
            setWarning(result.error || 'Mordor request failed.');
            setStatus('Failed', 'fail');
          }} else {{
            await postNotebookContext();
            setStatus('Done', 'ok');
          }}
        }} catch (err) {{
          const message = String(err && err.message ? err.message : err);
          setWarning(message);
          if (abortRequested || /cancel/i.test(message)) {{
            append(activity, 'Cancelled');
            setStatus('Cancelled', 'warn');
          }} else {{
            append(activity, 'Failed');
            setStatus('Failed', 'fail');
          }}
        }} finally {{
          busy = false;
          send.disabled = false;
          activeAgentSession = null;
          activeAgentBackend = null;
          showStop(false);
        }}
      }};
      syncNotebook();
    }})();
    </script>
    """


def display_panel(session: Any) -> Any:
    """Render a lightweight in-notebook status panel.

    This is intentionally simple. The full JupyterLab side panel can layer on
    top of the same runtime bridge and operation queue.
    """
    try:
        from IPython.display import HTML, display
    except Exception as exc:  # pragma: no cover - only meaningful in notebooks
        raise RuntimeError("IPython display is unavailable") from exc
    return display(HTML(panel_markup(session)))

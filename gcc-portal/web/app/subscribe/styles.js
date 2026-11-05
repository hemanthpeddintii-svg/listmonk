// Page-level CSS for subscribe/weekly pages (kept out of globals.css, which the lead owns).
export const css = `
.sub-form{position:relative;display:grid;gap:18px}
.sub-row{display:flex;gap:10px;flex-wrap:wrap}.sub-row input{flex:1 1 240px;font-size:18px}
.sub-form fieldset{border:0;padding:0;margin:0}.sub-form legend{font:700 12px var(--mono);letter-spacing:.12em;text-transform:uppercase;margin-bottom:10px;padding:0}
.sub-chips{display:flex;flex-wrap:wrap;gap:8px}
.sub-chip{position:relative;cursor:pointer}.sub-chip input{position:absolute;opacity:0;inset:0;width:100%;height:100%;margin:0;cursor:pointer}
.sub-chip span{display:inline-block;border:2px solid var(--ink);border-radius:99px;padding:4px 14px;font-weight:600;background:#fff;transition:background .15s,color .15s}
.sub-chip input:checked+span{background:var(--ink);color:var(--paper)}.sub-chip input:focus-visible+span{box-shadow:3px 3px 0 var(--hot)}
.sub-done{border:2px solid var(--ink);border-radius:16px;background:var(--lime);padding:18px 20px;box-shadow:5px 5px 0 var(--ink)}.sub-done p{margin:12px 0 0;word-break:break-all}
.err{color:#b3200a;font-weight:600}.ok{color:#1c6b2a;font-weight:600}
.sub-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:34px;align-items:start;margin-top:26px}
@media(max-width:860px){.sub-grid{grid-template-columns:1fr}}
.wk-list{list-style:none;padding:0;margin:26px 0;display:grid;gap:14px}
.wk-item{display:grid;grid-template-columns:auto 1fr auto;gap:18px;align-items:center;text-decoration:none;background:#fff;border:2px solid var(--ink);border-radius:18px;padding:16px 20px;box-shadow:4px 4px 0 var(--ink);transition:transform .2s var(--ease),box-shadow .2s var(--ease)}
.wk-item:hover{transform:translate(-2px,-2px);box-shadow:7px 7px 0 var(--ink)}
.wk-no{font:500 38px/1 var(--serif);color:var(--hot);min-width:2.2ch}
.wk-item h2{font-size:22px;margin:0 0 4px}.wk-item p{margin:0;color:var(--mut);font:600 12px var(--mono);letter-spacing:.04em}
.wk-stats{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
@media(max-width:640px){.wk-item{grid-template-columns:auto 1fr}.wk-stats{grid-column:1/-1;justify-content:flex-start}}
.issue{max-width:700px;margin:26px auto}
.issue td,.issue th{white-space:normal;border-bottom:0;padding:0;text-align:left;vertical-align:top}.issue td[align=right]{text-align:right}.issue td[align=center]{text-align:center}.issue table{width:auto}.issue table[width='100%']{width:100%}.issue-nav{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;max-width:700px;margin:0 auto}
.issue-nav a{font-weight:600}
.issue-cta{max-width:700px;margin:30px auto;background:var(--ink);color:var(--paper);border-radius:24px;padding:26px 28px}.issue-cta h2{color:var(--paper);font-size:30px;margin-bottom:12px}
.issue-cta .sub-row input{border-color:var(--paper)}.issue-cta p{margin:0 0 14px;opacity:.85}
`;

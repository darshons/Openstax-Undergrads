/* Scenario Studio · backend client
 *
 * Thin wrappers around the BackEnd FastAPI endpoints (see BackEnd/api.py).
 * Exposed on window.OSApi so the in-browser-Babel React app can call them
 * without a bundler.
 *
 * Override the API host by setting window.OS_API_BASE before this script
 * loads (e.g. <script>window.OS_API_BASE="http://my-host:9000";</script>).
 */
(function(){
  const DEFAULT_BASE = "http://localhost:8000";
  const apiBase = () => (window.OS_API_BASE || DEFAULT_BASE).replace(/\/+$/, "") + "/api";

  async function postJSON(path, body){
    const res = await fetch(apiBase() + path, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    let data = null;
    try { data = await res.json(); } catch (_) { /* non-JSON */ }
    if (!res.ok){
      const detail = data && (data.detail || data.message) || `${res.status} ${res.statusText}`;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  /**
   * POST /api/initial_script — generate a fresh branching script.
   * @param {{book_title:string, unit_num:number, chapter_num?:number,
   *          page_num?:string, user_query:string, model_choice:"anthropic"|"gemini"}} req
   * @returns the script object (response.script from the backend).
   */
  async function fetchInitialScript(req){
    const data = await postJSON("/initial_script", req);
    if (!data || !data.script){
      throw new Error("Backend returned no script.");
    }
    return data.script;
  }

  /**
   * POST /api/modified_script — submit the user's edits.
   * @param {object} script — the full script object (matches /initial_script's response.script).
   */
  async function submitModifiedScript(script){
    return postJSON("/modified_script", {script});
  }

  window.OSApi = {fetchInitialScript, submitModifiedScript};
})();

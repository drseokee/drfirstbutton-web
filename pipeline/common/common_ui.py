import re, sys

LIGHTS_OLD = """scene.add(new THREE.HemisphereLight(0xffffff, 0x3a4256, 0.85));
const key = new THREE.DirectionalLight(0xffffff, 0.8); scene.add(key);
const fill = new THREE.DirectionalLight(0xbfd0ff, 0.3); fill.position.set(-0.6, -0.2, 0.4); scene.add(fill);
const rim = new THREE.DirectionalLight(0xffffff, 0.45); rim.position.set(0, 0.4, -1); scene.add(rim);"""
LIGHTS_NEW = """// calmer studio: softer ambient, one key from above-front, weak fill, a small rim — so bone surfaces keep tone and boundaries read
scene.add(new THREE.HemisphereLight(0xf2ede4, 0x2a3142, 0.5));
const key = new THREE.DirectionalLight(0xfff4e6, 0.62); scene.add(key);
const fill = new THREE.DirectionalLight(0xbfd0ff, 0.16); fill.position.set(-0.6, -0.2, 0.4); scene.add(fill);
const rim = new THREE.DirectionalLight(0xffffff, 0.28); rim.position.set(0, 0.4, -1); scene.add(rim);
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 0.95;"""

HELP_HTML = """    <h2>조작</h2>
    <div style="color:var(--dim);font-size:11.5px;line-height:1.6">
      드래그 회전 · 우클릭/가운데/Shift+드래그 이동 · 휠 확대<br>
      Ctrl+드래그 확대 · Alt+드래그 화면 기울이기<br>
      더블클릭: 그 지점을 중심으로 · Shift+휠: 위아래 이동<br>
      방향키 회전 · Shift+방향키 이동 · +/− 확대 · R 원래대로<br>
      Space/PageDown 다음 · PageUp 이전 · 1~5 단계
    </div>
"""

CONTROLS = r"""// ---------- camera (common) ----------
const target = new THREE.Vector3(), off = new THREE.Vector3(0, 0, 0.30), up = new THREE.Vector3(0, 1, 0);
const camGoal = { off: off.clone(), up: up.clone(), target: target.clone(), t: 1 };
function applyCam(){ camera.position.copy(target).add(off); camera.up.copy(up); camera.lookAt(target);
  key.position.copy(camera.position).add(new THREE.Vector3(0.1, 0.15, 0)); }
__VIEWS__
function setView(name, instant){
  if (name === 'reset') name = __RESET__;
  const v = VIEWS[name]; if (!v) return;
  camGoal.target.set(...(v.target || [0,0,0]));
  camGoal.off.set(...v.off).normalize().multiplyScalar(v.r);
  const f = camGoal.target.clone().sub(camGoal.target.clone().add(camGoal.off)).normalize();
  camGoal.up.set(...v.up); camGoal.up.sub(f.clone().multiplyScalar(camGoal.up.dot(f))).normalize();
  camGoal.t = instant === false ? 0 : 1;
  if (camGoal.t >= 1) { off.copy(camGoal.off); up.copy(camGoal.up); target.copy(camGoal.target); applyCam(); }
}
function camTick(dt){ if (camGoal.t >= 1) return; camGoal.t = Math.min(1, camGoal.t + dt * 1.6); const s = camGoal.t * camGoal.t * (3 - 2 * camGoal.t);
  off.lerp(camGoal.off, s); up.lerp(camGoal.up, s).normalize(); target.lerp(camGoal.target, s); applyCam(); }
(function camLoop(){ let last = performance.now(); (function f(now){ requestAnimationFrame(f); let dt = (now - last) / 1000; if (!(dt >= 0)) dt = 0; last = now; camTick(Math.min(0.05, dt)); })(performance.now()); })();
function rotate(dx, dy){ camGoal.t = 1;
  const f = target.clone().sub(camera.position).normalize(), right = new THREE.Vector3().crossVectors(f, up).normalize();
  const q = new THREE.Quaternion().setFromAxisAngle(up, -dx * 0.007).multiply(new THREE.Quaternion().setFromAxisAngle(right, -dy * 0.007));
  off.applyQuaternion(q); up.applyQuaternion(q).normalize(); applyCam(); }
function zoom(f){ camGoal.t = 1; off.setLength(Math.min(2.0, Math.max(0.02, off.length() * f))); applyCam(); }
function panKeys(dx, dy){ camGoal.t = 1; const k = off.length() * 0.0016;
  const r = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0), u = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 1);
  target.addScaledVector(r, -dx*k).addScaledVector(u, dy*k); applyCam(); }
let drag = null, pinch0 = 0; const pointers = new Set();
canvas.addEventListener('pointerdown', e => { if (typeof onPointerDownExtra === 'function' && onPointerDownExtra(e)) return;
  pointers.add(e.pointerId); drag = { x:e.clientX, y:e.clientY, b:e.button, shift:e.shiftKey, ctrl:e.ctrlKey || e.metaKey, alt:e.altKey }; canvas.setPointerCapture(e.pointerId); });
canvas.addEventListener('pointerup', e => { pointers.delete(e.pointerId); drag = null; if (typeof onPointerUpExtra === 'function') onPointerUpExtra(e); });
canvas.addEventListener('pointercancel', e => { pointers.delete(e.pointerId); drag = null; });
canvas.addEventListener('contextmenu', e => e.preventDefault());
canvas.addEventListener('pointermove', e => {
  if (typeof onPointerMoveExtra === 'function' && onPointerMoveExtra(e)) return;
  hover(e); if (!drag || pointers.size > 1) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y; drag.x = e.clientX; drag.y = e.clientY;
  if (drag.ctrl) { zoom(Math.exp(dy * 0.006)); }
  else if (drag.alt) { camGoal.t = 1; const f = target.clone().sub(camera.position).normalize(); up.applyQuaternion(new THREE.Quaternion().setFromAxisAngle(f, -dx * 0.006)).normalize(); applyCam(); }
  else if (drag.b === 2 || drag.b === 1 || drag.shift) { panKeys(dx, dy); }
  else rotate(dx, dy); });
canvas.addEventListener('dblclick', e => {
  ptr.x = (e.clientX / innerWidth) * 2 - 1; ptr.y = -(e.clientY / innerHeight) * 2 + 1; ray.setFromCamera(ptr, camera);
  const hit = ray.intersectObjects(meshes.filter(m => m.visible))[0];
  if (hit) { camGoal.target.copy(hit.point); camGoal.off.copy(off).setLength(Math.max(0.03, off.length() * 0.7)); camGoal.up.copy(up); camGoal.t = 0; } });
canvas.addEventListener('wheel', e => { e.preventDefault();
  if (e.shiftKey) { const u = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 1); camGoal.t = 1; target.addScaledVector(u, -e.deltaY * off.length() * 0.0008); applyCam(); }
  else zoom(Math.exp(e.deltaY * (e.ctrlKey ? 0.0004 : 0.0012))); }, { passive:false });
addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  const step = e.shiftKey ? 12 : 0;
  if (e.key === 'ArrowLeft')  { e.preventDefault(); e.shiftKey ? panKeys(-step, 0) : rotate(-18, 0); }
  if (e.key === 'ArrowRight') { e.preventDefault(); e.shiftKey ? panKeys(step, 0) : rotate(18, 0); }
  if (e.key === 'ArrowUp')    { e.preventDefault(); e.shiftKey ? panKeys(0, -step) : rotate(0, -18); }
  if (e.key === 'ArrowDown')  { e.preventDefault(); e.shiftKey ? panKeys(0, step) : rotate(0, 18); }
  if (e.key === '+' || e.key === '=') zoom(0.85);
  if (e.key === '-' || e.key === '_') zoom(1 / 0.85);
  if (e.key === 'Home' || e.key === 'r' || e.key === 'R') setView('reset', false);
  if (typeof goStage === 'function' && typeof STAGES !== 'undefined') {
    if (e.key === ' ' || e.key === 'PageDown') { e.preventDefault(); goStage(Math.min(STAGES.length - 1, Math.max(0, stage + 1))); }
    if (e.key === 'PageUp' || e.key === 'Backspace') { e.preventDefault(); goStage(Math.max(0, stage - 1)); }
    if (e.key >= '1' && e.key <= '5') goStage(+e.key - 1);
  }
});
"""

def apply_common(t, reset_view):
    # lights
    if LIGHTS_OLD in t: t = t.replace(LIGHTS_OLD, LIGHTS_NEW)
    # controls: replace from the camera header to the wheel listener (inclusive)
    m0 = re.search(r"// ---------- free orbit camera ----------|// ---------- camera ----------", t)
    m1 = re.search(r"canvas\.addEventListener\('wheel'.*?\n", t[m0.start():], flags=re.S)
    block = t[m0.start(): m0.start() + m1.end()]
    views = re.search(r"const VIEWS = \{.*?\n\};", block, flags=re.S).group(0)
    t = t[:m0.start()] + CONTROLS.replace("__VIEWS__", views).replace("__RESET__", repr(reset_view)) + t[m0.start() + m1.end():]
    # any leftover stage keydown handler in the pack (the common one handles it)
    t = re.sub(r"\naddEventListener\('keydown', e => \{ if \(e\.target\.tagName === 'INPUT'\) return; if \(e\.key === ' '.*?\}\);\n", "\n", t, flags=re.S)
    # collapsible panel with help
    t = t.replace("  details summary { cursor:pointer; color:var(--dim); font-size:12px; margin:8px 0 4px; }\n", "")
    t = t.replace("  #panel h2 {", "  details summary { cursor:pointer; color:var(--dim); font-size:12px; margin:8px 0 4px; }\n  #panel h2 {", 1)
    if "<details>" not in t:
        t = re.sub(r"(<p class=\"sub\">.*?</p>\n)", r"\1  <details>\n    <summary>층 보이기 · 표현 · 보는 방향 · 조작</summary>\n", t, count=1, flags=re.S)
        t = t.replace('  <h2>보는 방향</h2>\n  <div class="views">', HELP_HTML + '  <h2>보는 방향</h2>\n  <div class="views">', 1)
        # close details after the views block
        t = re.sub(r'(<div class="views">.*?</div>\n)', r"\1  </details>\n", t, count=1, flags=re.S)
    return t

if __name__ == "__main__":
    src, dst, reset = sys.argv[1], sys.argv[2], sys.argv[3]
    t = open(src).read(); t2 = apply_common(t, reset); open(dst, "w").write(t2); print("patched", dst)

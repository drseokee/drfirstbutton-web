/* Muscle / tendon "line of action" deformer, shared by the 3D viewers (THREE r128 global).
 *
 * Linear blend skinning bends a muscle like a garden hose wherever it crosses a joint: the part that is blended between two
 * bones folds, pinches and cuts through the bone. Real muscles and tendons do not bend there: they run as straight cords
 * between where they are held (origin / pulley) and where they are pulled (insertion) and only get longer or shorter,
 * wrapping over a bone where they would otherwise cut through it. Same idea as the rotator-cuff viewer (PR #9), in general form:
 *
 *  - every vertex belongs to one bone (pure) or to the zone that crosses a joint (mixed, between bone s0 and the next bone s1);
 *  - pure vertices ride rigidly on their bone;
 *  - each mixed vertex sits on a fibre that runs from an anchor on s0 to an anchor on s1. The anchors are smooth soft-min
 *    averages of the ring of pure vertices where that piece of the muscle leaves the zone, so neighbouring vertices get
 *    neighbouring fibres and nothing tears. The fibre is the straight chord between the anchors, softly pushed out of a sphere
 *    around the joint centre (a rope over a ball), never closer to it than at rest;
 *  - the vertex keeps its place along the fibre (as a fraction of its length) and its offset across it; the offset turns from
 *    s0's rotation to s1's along the fibre. A shortened muscle belly thickens a little (≈ constant volume), tendons do not.
 *  The rest pose is reproduced exactly.
 *
 * MuscleFibres.build({ rest, index, seg0, seg1, t, joint(s0, s1) → { seg, c:[x,y,z] }, soft, margin, thicken })
 *   rest   Float32Array xyz in the rig space (the space the bone transforms act in)
 *   t      per-vertex weight of seg1 (0 = pure seg0, 1 = pure seg1, between = in the joint zone)
 *   joint  centre of the joint between two bones (rest space) and the bone that carries it
 * .apply(out, M, Q)   M[s]: THREE.Matrix4 rest → current of bone s, Q[s]: its rotation (THREE.Quaternion)
 */
(function () {
  const FS = 12, NR = 32;
  const EV = { x: 0, y: 0, z: 0 }, AV = { x: 0, y: 0, z: 0, tx: 0, ty: 0, tz: 0 };
  const PL = new Float64Array((FS + 1) * 3), CL = new Float64Array(FS + 1);
  // point at parameter t ∈ [0,1] of the (pushed) chord a→b. Push over the sphere (centre c, radius r):
  // |p − c| → r + m·ln(1 + e^((|p − c| − r)/m)), along p − c + h (h biases the push to the side the muscle lies on)
  function fibPt(F, t) {
    let x = F.ax + (F.bx - F.ax) * t, y = F.ay + (F.by - F.ay) * t, z = F.az + (F.bz - F.az) * t;
    if (F.r > 0) {
      const qx = x - F.cx, qy = y - F.cy, qz = z - F.cz, dr = Math.sqrt(qx * qx + qy * qy + qz * qz), sx = (dr - F.r) / F.m;
      if (sx < 12) {
        const push = F.m * (sx > 0 ? Math.log1p(Math.exp(-sx)) : Math.log1p(Math.exp(sx)) - sx);
        const px = qx + F.hx, py = qy + F.hy, pz = qz + F.hz, d = Math.sqrt(px * px + py * py + pz * pz);
        if (d > 1e-9) { const g = push / d; x += px * g; y += py * g; z += pz * g; }
      }
    }
    EV.x = x; EV.y = y; EV.z = z; return EV;
  }
  function fibPoly(F) {
    let L = 0;
    for (let k = 0; k <= FS; k++) {
      const e = fibPt(F, k / FS); PL[3 * k] = e.x; PL[3 * k + 1] = e.y; PL[3 * k + 2] = e.z;
      if (k) { const dx = e.x - PL[3 * k - 3], dy = e.y - PL[3 * k - 2], dz = e.z - PL[3 * k - 1]; L += Math.sqrt(dx * dx + dy * dy + dz * dz); }
      CL[k] = L;
    }
    return L;
  }
  // point + smooth tangent at arc-length fraction ua of the last fibPoly
  function fibArc(ua) {
    const s = Math.min(1, Math.max(0, ua)) * CL[FS]; let k = 0; while (k < FS - 1 && CL[k + 1] < s) k++;
    const sl = Math.max(1e-12, CL[k + 1] - CL[k]), t = Math.min(1, Math.max(0, (s - CL[k]) / sl));
    const ax = PL[3 * k], ay = PL[3 * k + 1], az = PL[3 * k + 2];
    AV.x = ax + (PL[3 * k + 3] - ax) * t; AV.y = ay + (PL[3 * k + 4] - ay) * t; AV.z = az + (PL[3 * k + 5] - az) * t;
    const k0 = Math.max(0, k - 1), k2 = Math.min(FS, k + 2);
    const t0x = PL[3 * k + 3] - PL[3 * k0], t0y = PL[3 * k + 4] - PL[3 * k0 + 1], t0z = PL[3 * k + 5] - PL[3 * k0 + 2];
    const t1x = PL[3 * k2] - PL[3 * k], t1y = PL[3 * k2 + 1] - PL[3 * k + 1], t1z = PL[3 * k2 + 2] - PL[3 * k + 2];
    const l0 = Math.sqrt(t0x * t0x + t0y * t0y + t0z * t0z) || 1, l1 = Math.sqrt(t1x * t1x + t1y * t1y + t1z * t1z) || 1;
    const tx = t0x / l0 * (1 - t) + t1x / l1 * t, ty = t0y / l0 * (1 - t) + t1y / l1 * t, tz = t0z / l0 * (1 - t) + t1z / l1 * t, l = Math.sqrt(tx * tx + ty * ty + tz * tz) || 1;
    AV.tx = tx / l; AV.ty = ty / l; AV.tz = tz / l; return AV;
  }

  function build(o) {
    const rest = o.rest, n = rest.length / 3, idx = o.index, S0 = o.seg0, S1 = o.seg1;
    const soft = o.soft || 0.004, cut = soft * 9, m = o.margin || 0.002, E = o.pure || 0.02;
    // nearest-bone weights are noisy: islands of "pure" vertices inside a joint zone would ride rigidly while their neighbours
    // slide along fibres, and tear. Smoothing the weight over the mesh first gives one clean band across each joint.
    let T = o.t;
    if (o.smooth) {
      const nb = Array.from({ length: n }, () => []);
      for (let f = 0; f < idx.length; f += 3) for (let e = 0; e < 3; e++) { const a = idx[f + e], b = idx[f + (e + 1) % 3]; if (S0[a] === S0[b] && S1[a] === S1[b]) { nb[a].push(b); nb[b].push(a); } }
      let cur = Float32Array.from(T), nxt = new Float32Array(n);
      for (let it = 0; it < o.smooth; it++) { for (let i = 0; i < n; i++) { const L = nb[i]; if (!L.length) { nxt[i] = cur[i]; continue; } let s = 0; for (const j of L) s += cur[j]; nxt[i] = 0.5 * cur[i] + 0.5 * s / L.length; } [cur, nxt] = [nxt, cur]; }
      T = cur;
    }
    const kind = new Uint8Array(n);                       // 0 pure seg0, 1 pure seg1, 2 mixed
    for (let i = 0; i < n; i++) kind[i] = T[i] <= E ? 0 : T[i] >= 1 - E ? 1 : 2;
    // connected pieces (one mesh often holds several muscles / tendons)
    const par = new Int32Array(n); for (let i = 0; i < n; i++) par[i] = i;
    const find = a => { while (par[a] !== a) { par[a] = par[par[a]]; a = par[a]; } return a; };
    for (let f = 0; f < idx.length; f += 3) { const a = find(idx[f]), b = find(idx[f + 1]), c = find(idx[f + 2]); par[b] = a; par[find(c)] = a; }
    // pieces that only touch (e.g. a common tendon and its slips, modelled as separate shells) move as one
    const welds = [];
    { const h = o.weld || 0.0006, grid = new Map(), cell = (x) => Math.floor(x / h);
      for (let i = 0; i < n; i++) { const k = cell(rest[3 * i]) + ',' + cell(rest[3 * i + 1]) + ',' + cell(rest[3 * i + 2]); let L = grid.get(k); if (!L) grid.set(k, L = []); L.push(i); }
      for (let i = 0; i < n; i++) { const cx = cell(rest[3 * i]), cy = cell(rest[3 * i + 1]), cz = cell(rest[3 * i + 2]);
        for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (let dz = -1; dz <= 1; dz++) { const L = grid.get((cx + dx) + ',' + (cy + dy) + ',' + (cz + dz)); if (!L) continue;
          for (const j of L) if (j > i && Math.hypot(rest[3 * i] - rest[3 * j], rest[3 * i + 1] - rest[3 * j + 1], rest[3 * i + 2] - rest[3 * j + 2]) < h) { const a = find(i), b = find(j); if (a !== b) par[b] = a; welds.push(i, j); } } } }
    // ring of pure vertices where each piece leaves each joint zone, one ring per (piece, joint, side)
    const rings = new Map(), pairOf = i => S0[i] * 256 + S1[i];
    const ringKey = (comp, pair, side) => comp * 131072 + pair * 2 + side, seen = new Set();
    const faces = [];   // triangles, plus the welded seams as two-vertex "faces"
    for (let f = 0; f < idx.length; f += 3) faces.push([idx[f], idx[f + 1], idx[f + 2]]);
    for (let w = 0; w < welds.length; w += 2) faces.push([welds[w], welds[w + 1]]);
    for (const v of faces) {
      const mx = v.find(i => kind[i] === 2);
      if (mx === undefined) continue;
      for (const i of v) {
        if (kind[i] === 2) continue;
        const bone = kind[i] === 0 ? S0[i] : S1[i], side = bone === S0[mx] ? 0 : bone === S1[mx] ? 1 : -1;   // pure vertex of either bone of this joint
        if (side < 0) continue;
        const key = ringKey(find(i), pairOf(mx), side);
        const sk = key + ':' + i; if (seen.has(sk)) continue; seen.add(sk);
        let r = rings.get(key); if (!r) rings.set(key, r = []); r.push(rest[3 * i], rest[3 * i + 1], rest[3 * i + 2]);
      }
    }
    // a piece that starts or ends inside a zone (a short muscle inserting just past the joint) has no ring on that side:
    // its own end there is the attachment — the vertices with the extreme weight in the zone, carried by that bone
    { const ext = new Map();
      for (let i = 0; i < n; i++) if (kind[i] === 2) { const kc = find(i) * 65536 + pairOf(i); let e = ext.get(kc); if (!e) ext.set(kc, e = { lo: 1, hi: 0, comp: find(i), pr: pairOf(i) }); e.lo = Math.min(e.lo, T[i]); e.hi = Math.max(e.hi, T[i]); }
      for (let i = 0; i < n; i++) if (kind[i] === 2) { const e = ext.get(find(i) * 65536 + pairOf(i));
        for (const side of [0, 1]) { const key = ringKey(e.comp, e.pr, side); if (rings.has(key) && !e['syn' + side]) continue; e['syn' + side] = true;
          if (side === 0 ? T[i] <= e.lo + 0.06 : T[i] >= e.hi - 0.06) { let r = rings.get(key); if (!r) rings.set(key, r = []); r.push(rest[3 * i], rest[3 * i + 1], rest[3 * i + 2]); } } } }
    for (const [k, r] of rings) rings.set(k, Float64Array.from(r));
    const SD = new Float64Array(4096);
    function anchor(P, x, y, z, out, j) {                // soft-min average of the ring: weight e^(−(d − d_min)/soft) — glides, never jumps
      const np = P.length / 3; let best = 1e9; const sd = np > SD.length ? new Float64Array(np) : SD;
      for (let k = 0; k < np; k++) { const dx = P[3 * k] - x, dy = P[3 * k + 1] - y, dz = P[3 * k + 2] - z, d = Math.sqrt(dx * dx + dy * dy + dz * dz); sd[k] = d; if (d < best) best = d; }
      let w = 0, ax = 0, ay = 0, az = 0;
      for (let k = 0; k < np; k++) { const e = sd[k] - best; if (e > cut) continue; const g = Math.exp(-e / soft); w += g; ax += P[3 * k] * g; ay += P[3 * k + 1] * g; az += P[3 * k + 2] * g; }
      out[j] = ax / w; out[j + 1] = ay / w; out[j + 2] = az / w;
    }
    const mixed = []; for (let i = 0; i < n; i++) if (kind[i] === 2) mixed.push(i);
    const nm = mixed.length, MI = Int32Array.from(mixed);
    const A = new Float32Array(nm * 3), B = new Float32Array(nm * 3), Cc = new Float32Array(nm * 3), Cs = new Uint8Array(nm), H = new Float32Array(nm * 3), R = new Float32Array(nm);
    const WF = new Float32Array(nm), U = new Float32Array(nm), OFF = new Float32Array(nm * 3), AL = new Float32Array(nm), T0 = new Float32Array(nm * 3), L0 = new Float32Array(nm), OK = new Uint8Array(nm);
    const F = { ax: 0, ay: 0, az: 0, bx: 0, by: 0, bz: 0, cx: 0, cy: 0, cz: 0, r: 0, m, hx: 0, hy: 0, hz: 0 };
    const pairs = new Map();                               // pair → slot for the per-frame slerp tables
    // wrap radius per piece and joint: the closest the piece itself comes to the joint centre at rest (its inner surface lies on
    // the bone there). The cord is then held out at that distance like a tendon under its retinaculum: when the joint moves the
    // straight cord would cut across the bone, the push keeps it on the surface instead.
    const WR = new Map();
    for (let j = 0; j < nm; j++) { const i = MI[j], J = o.joint(S0[i], S1[i]), key = find(i) * 65536 + pairOf(i);
      const d = Math.hypot(rest[3 * i] - J.c[0], rest[3 * i + 1] - J.c[1], rest[3 * i + 2] - J.c[2]); if (!(WR.get(key) <= d)) WR.set(key, d); }
    for (let j = 0; j < nm; j++) {
      const i = MI[j], px = rest[3 * i], py = rest[3 * i + 1], pz = rest[3 * i + 2], comp = find(i), pr = pairOf(i);
      const ra = rings.get(ringKey(comp, pr, 0)), rb = rings.get(ringKey(comp, pr, 1));
      if (!pairs.has(pr)) pairs.set(pr, pairs.size);
      if (!ra || !rb || o.blend) continue;                 // no ring on a side (or blend asked for): plain blend for it
      OK[j] = 1;
      anchor(ra, px, py, pz, A, 3 * j); anchor(rb, px, py, pz, B, 3 * j);
      const J = o.joint(S0[i], S1[i]); Cs[j] = J.seg; Cc[3 * j] = J.c[0]; Cc[3 * j + 1] = J.c[1]; Cc[3 * j + 2] = J.c[2];
      Object.assign(F, { ax: A[3 * j], ay: A[3 * j + 1], az: A[3 * j + 2], bx: B[3 * j], by: B[3 * j + 1], bz: B[3 * j + 2], cx: J.c[0], cy: J.c[1], cz: J.c[2], r: 0 });
      const vx = px - F.cx, vy = py - F.cy, vz = pz - F.cz, vl = Math.hypot(vx, vy, vz) || 1;
      F.r = R[j] = Math.max(0, WR.get(comp * 65536 + pr) - m);
      F.hx = H[3 * j] = vx / vl * F.r * 0.6; F.hy = H[3 * j + 1] = vy / vl * F.r * 0.6; F.hz = H[3 * j + 2] = vz / vl * F.r * 0.6;
      const cx = F.bx - F.ax, cy = F.by - F.ay, cz = F.bz - F.az, cc = cx * cx + cy * cy + cz * cz;
      // place along the fibre = projection onto the anchor chord (linear in position, so neighbours never jump to different places)
      const bt = cc > 1e-12 ? Math.min(1, Math.max(0, ((px - F.ax) * cx + (py - F.ay) * cy + (pz - F.az) * cz) / cc)) : 0;
      const L = fibPoly(F), kk = Math.min(FS - 1, Math.floor(bt * FS)), ua = (CL[kk] + (CL[kk + 1] - CL[kk]) * (bt * FS - kk)) / Math.max(1e-12, L);
      // near either edge of the zone the vertex eases back onto its bone, so the zone joins its rigid neighbours without a seam
      { const e = Math.min(T[i] - E, 1 - E - T[i]) / (o.ease || 0.15), c = Math.min(1, Math.max(0, e)); WF[j] = c * c * (3 - 2 * c); }
      const f = fibArc(ua), dx = px - f.x, dy = py - f.y, dz = pz - f.z, al = dx * f.tx + dy * f.ty + dz * f.tz;
      U[j] = ua; L0[j] = L; T0[3 * j] = f.tx; T0[3 * j + 1] = f.ty; T0[3 * j + 2] = f.tz; AL[j] = al;
      OFF[3 * j] = dx - al * f.tx; OFF[3 * j + 1] = dy - al * f.ty; OFF[3 * j + 2] = dz - al * f.tz;
    }
    const ROT = [...pairs.keys()].map(() => Array.from({ length: NR + 1 }, () => new Float64Array(9)));
    const _q = new THREE.Quaternion(), _m = new THREE.Matrix4(), _v = new THREE.Vector3(), _c = new THREE.Vector3();
    const thicken = !!o.thicken;

    function apply(out, M, Q) {
      for (const [pr, slot] of pairs) {                     // rotation tables: s0's rotation turning into s1's along the fibre
        const s0 = pr >> 8, s1 = pr & 255;
        for (let b = 0; b <= NR; b++) { _q.copy(Q[s0]).slerp(Q[s1], b / NR); _m.makeRotationFromQuaternion(_q); const e = _m.elements, d = ROT[slot][b];
          d[0] = e[0]; d[1] = e[1]; d[2] = e[2]; d[3] = e[4]; d[4] = e[5]; d[5] = e[6]; d[6] = e[8]; d[7] = e[9]; d[8] = e[10]; }
      }
      for (let i = 0; i < n; i++) if (kind[i] !== 2) {
        _v.set(rest[3 * i], rest[3 * i + 1], rest[3 * i + 2]).applyMatrix4(M[kind[i] === 0 ? S0[i] : S1[i]]);
        out[3 * i] = _v.x; out[3 * i + 1] = _v.y; out[3 * i + 2] = _v.z;
      }
      for (let j = 0; j < nm; j++) {
        const i = MI[j], s0 = S0[i], s1 = S1[i], RT = ROT[pairs.get(s0 * 256 + s1)];
        if (!OK[j]) {                                        // fallback: rigid blend (rotation slerp, translation lerp)
          const t = T[i], x = rest[3 * i], y = rest[3 * i + 1], z = rest[3 * i + 2], m0 = M[s0].elements, m1 = M[s1].elements;
          const ax = m0[0] * x + m0[4] * y + m0[8] * z + m0[12], ay = m0[1] * x + m0[5] * y + m0[9] * z + m0[13], az = m0[2] * x + m0[6] * y + m0[10] * z + m0[14];
          const bx = m1[0] * x + m1[4] * y + m1[8] * z + m1[12], by = m1[1] * x + m1[5] * y + m1[9] * z + m1[13], bz = m1[2] * x + m1[6] * y + m1[10] * z + m1[14];
          out[3 * i] = ax + (bx - ax) * t; out[3 * i + 1] = ay + (by - ay) * t; out[3 * i + 2] = az + (bz - az) * t;
          continue;
        }
        _v.set(A[3 * j], A[3 * j + 1], A[3 * j + 2]).applyMatrix4(M[s0]); F.ax = _v.x; F.ay = _v.y; F.az = _v.z;
        _v.set(B[3 * j], B[3 * j + 1], B[3 * j + 2]).applyMatrix4(M[s1]); F.bx = _v.x; F.by = _v.y; F.bz = _v.z;
        _c.set(Cc[3 * j], Cc[3 * j + 1], Cc[3 * j + 2]).applyMatrix4(M[Cs[j]]); F.cx = _c.x; F.cy = _c.y; F.cz = _c.z; F.r = R[j];
        const Rh = RT[NR >> 1], hx = H[3 * j], hy = H[3 * j + 1], hz = H[3 * j + 2];
        F.hx = Rh[0] * hx + Rh[3] * hy + Rh[6] * hz; F.hy = Rh[1] * hx + Rh[4] * hy + Rh[7] * hz; F.hz = Rh[2] * hx + Rh[5] * hy + Rh[8] * hz;
        const u = U[j], L = fibPoly(F);
        let kv = 1;
        if (thicken) { const k = Math.min(1.2, Math.max(0.85, Math.sqrt(L0[j] / Math.max(1e-6, L)))); kv = 1 + (k - 1) * Math.sin(Math.PI * Math.min(1, Math.max(0, u))); }
        const f = fibArc(u), w = u * u * (3 - 2 * u), Rm = RT[Math.min(NR, Math.max(0, Math.round(w * NR)))];
        const al = AL[j], px = OFF[3 * j] * kv + T0[3 * j] * al, py = OFF[3 * j + 1] * kv + T0[3 * j + 1] * al, pz = OFF[3 * j + 2] * kv + T0[3 * j + 2] * al;
        let x = f.x + Rm[0] * px + Rm[3] * py + Rm[6] * pz, y = f.y + Rm[1] * px + Rm[4] * py + Rm[7] * pz, z = f.z + Rm[2] * px + Rm[5] * py + Rm[8] * pz;
        const wf = WF[j];
        if (wf < 1) { _v.set(rest[3 * i], rest[3 * i + 1], rest[3 * i + 2]).applyMatrix4(M[T[i] < 0.5 ? s0 : s1]); x = _v.x + (x - _v.x) * wf; y = _v.y + (y - _v.y) * wf; z = _v.z + (z - _v.z) * wf; }
        out[3 * i] = x; out[3 * i + 1] = y; out[3 * i + 2] = z;
      }
    }
    return { apply, rest, mixed: nm, fallback: nm - OK.reduce((a, b) => a + b, 0), dbg: { U, MI } };
  }

  // Bone transforms rest → current in the space of `space` (an Object3D the rigged meshes hang in), from bones / groups.
  // Capture once in the rest pose; then call update() each frame and pass .M / .Q to apply().
  function rig(space, bones) {
    const inv = new THREE.Matrix4(), rest = bones.map(b => { space.updateMatrixWorld(true); return new THREE.Matrix4().copy(inv.copy(space.matrixWorld).invert()).multiply(b.matrixWorld).invert(); });
    const M = bones.map(() => new THREE.Matrix4()), Q = bones.map(() => new THREE.Quaternion()), _p = new THREE.Vector3(), _s = new THREE.Vector3();
    function update() {
      space.updateMatrixWorld(true); inv.copy(space.matrixWorld).invert();
      bones.forEach((b, k) => { M[k].copy(inv).multiply(b.matrixWorld).multiply(rest[k]); M[k].decompose(_p, Q[k], _s); });
    }
    return { M, Q, update };
  }

  window.MuscleFibres = { build, rig };
})();

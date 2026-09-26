/* AuthShield 360 – Python Cyber Theme Background */
(function () {
  "use strict";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Cursor glow
  var glow = document.getElementById("glow");
  if (glow) {
    window.addEventListener("pointermove", function (e) {
      glow.style.setProperty("--mx", e.clientX + "px");
      glow.style.setProperty("--my", e.clientY + "px");
    }, { passive: true });
  }

  var canvas = document.getElementById("scene");
  if (!canvas || typeof THREE === "undefined") return;

  var renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);

  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
  camera.position.set(0, 0, 11);

  function glowTexture(color) {
    var c = document.createElement("canvas"); c.width = c.height = 128;
    var ctx = c.getContext("2d");
    var g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, color + "ff"); g.addColorStop(0.4, color + "55"); g.addColorStop(1, color + "00");
    ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }

  // ---- Centerpiece: Python-style double helix / interlocked rings ----
  var core = new THREE.Group();
  scene.add(core);

  var goldColor = 0xc9a86a, emColor = 0x4d8a6c;

  var outerGeo = new THREE.TorusGeometry(2.2, 0.08, 16, 64);
  var outerRing = new THREE.Mesh(outerGeo, new THREE.MeshBasicMaterial({
    color: goldColor, transparent: true, opacity: 0.55,
  }));
  core.add(outerRing);

  var ring2 = new THREE.Mesh(new THREE.TorusGeometry(1.6, 0.06, 16, 48),
    new THREE.MeshBasicMaterial({ color: emColor, transparent: true, opacity: 0.45 }));
  ring2.rotation.x = Math.PI / 2;
  core.add(ring2);

  var ring3 = new THREE.Mesh(new THREE.TorusGeometry(1.0, 0.05, 16, 32),
    new THREE.MeshBasicMaterial({ color: 0xeccf94, transparent: true, opacity: 0.4 }));
  ring3.rotation.z = Math.PI / 3;
  core.add(ring3);

  // ---- Particle field (warm gold dots) ----
  var pCount = 900;
  var pPos = new Float32Array(pCount * 3);
  var pCol = new Float32Array(pCount * 3);
  var cGold = new THREE.Color(0xeccf94), cEm = new THREE.Color(0x6fae8c);
  for (var i = 0; i < pCount; i++) {
    var r = 3 + Math.random() * 4;
    var th = Math.random() * Math.PI * 2, ph = Math.acos((Math.random() * 2) - 1);
    pPos[i*3]     = r * Math.sin(ph) * Math.cos(th);
    pPos[i*3 + 1] = r * Math.sin(ph) * Math.sin(th);
    pPos[i*3 + 2] = r * Math.cos(ph);
    var mix = Math.random() > 0.75 ? cEm : cGold;
    pCol[i*3] = mix.r; pCol[i*3 + 1] = mix.g; pCol[i*3 + 2] = mix.b;
  }
  var pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute("position", new THREE.BufferAttribute(pPos, 3));
  pGeo.setAttribute("color", new THREE.BufferAttribute(pCol, 3));
  var points = new THREE.Points(pGeo, new THREE.PointsMaterial({
    size: 0.06, map: glowTexture("#eccf94"), transparent: true,
    vertexColors: true, depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  scene.add(points);

  // ---- Glow sprite ----
  var glowSprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: glowTexture("#c9a86a"), transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending, opacity: 0.35,
  }));
  glowSprite.scale.set(10, 10, 1);
  glowSprite.position.z = -2;
  scene.add(glowSprite);

  // ---- Python-themed floating symbols ----
  function wireMat(color, op) { return new THREE.LineBasicMaterial({ color: color, transparent: true, opacity: op === undefined ? 0.25 : op }); }

  // Python logo: two interlocked snakes (simplified)
  function makePythonLogo(color) {
    var g = new THREE.Group();
    var s1 = new THREE.Mesh(
      new THREE.TorusKnotGeometry(0.4, 0.06, 64, 8, 3, 4),
      new THREE.MeshBasicMaterial({ color: color, wireframe: true, transparent: true, opacity: 0.55 })
    );
    g.add(s1);
    return g;
  }

  // Terminal window
  function makeTerminal(color) {
    var g = new THREE.Group();
    // Window frame
    var box = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(1.8, 1.1, 0.05)),
      wireMat(color, 0.35)
    );
    g.add(box);
    // Title bar
    var bar = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(1.8, 0.15, 0.06)),
      wireMat(color, 0.4)
    );
    bar.position.y = 0.47;
    g.add(bar);
    // Code lines
    var lineMat = wireMat(color, 0.5);
    for (var i = 0; i < 4; i++) {
      var w = 0.3 + Math.random() * 0.8;
      var lineGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(-0.75, 0.25 - i*0.18, 0.04),
        new THREE.Vector3(-0.75 + w, 0.25 - i*0.18, 0.04),
      ]);
      g.add(new THREE.Line(lineGeo, lineMat));
    }
    return g;
  }

  // Curly braces symbol
  function makeBrace(color) {
    var g = new THREE.Group();
    var s = new THREE.Shape();
    s.moveTo(0.3, 0.7);
    s.quadraticCurveTo(0, 0.7, 0, 0.35);
    s.lineTo(0, 0.1);
    s.quadraticCurveTo(0, 0, -0.15, 0);
    s.quadraticCurveTo(0, 0, 0, -0.1);
    s.lineTo(0, -0.35);
    s.quadraticCurveTo(0, -0.7, 0.3, -0.7);
    var geo = new THREE.ExtrudeGeometry(s, { depth: 0.08, bevelEnabled: false });
    geo.center();
    g.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo), wireMat(color, 0.4)));
    return g;
  }

  // Database cylinder
  function makeDatabase(color) {
    var g = new THREE.Group();
    var body = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.CylinderGeometry(0.4, 0.4, 0.9, 16)),
      wireMat(color, 0.35)
    );
    g.add(body);
    for (var i = 0; i < 3; i++) {
      var disc = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.CylinderGeometry(0.4, 0.4, 0.02, 16)),
        wireMat(color, 0.3)
      );
      disc.position.y = 0.3 - i * 0.3;
      g.add(disc);
    }
    return g;
  }

  // Server rack
  function makeServer(color) {
    var g = new THREE.Group();
    var frame = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(0.7, 1.2, 0.5)),
      wireMat(color, 0.3)
    );
    g.add(frame);
    for (var i = 0; i < 4; i++) {
      var slot = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(0.6, 0.16, 0.4)),
        wireMat(color, 0.3)
      );
      slot.position.y = 0.4 - i * 0.25;
      g.add(slot);
    }
    return g;
  }

  // Binary panel
  function makeBinaryPanel() {
    var c = document.createElement("canvas"); c.width = 256; c.height = 256;
    var ctx = c.getContext("2d");
    ctx.fillStyle = "#c9a86a"; ctx.font = "bold 22px monospace";
    for (var row = 0; row < 8; row++) {
      var str = "";
      for (var col = 0; col < 8; col++) str += Math.random() > 0.5 ? "1" : "0";
      ctx.fillText(str, 6, 30 + row * 30);
    }
    var tex = new THREE.CanvasTexture(c);
    var mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(1.6, 1.6),
      new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: 0.28, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    var g = new THREE.Group(); g.add(mesh);
    return g;
  }

  // ---- Add drifting shapes ----
  var driftShapes = [];
  function addDrift(makerFn, color, x, y, z, s, speed, sway, side) {
    var m = makerFn(color);
    m.position.set(x, y, z); m.scale.setScalar(s);
    scene.add(m);
    driftShapes.push({
      mesh: m, speed: speed, base: { x: x, y: y },
      phase: Math.random() * Math.PI * 2, swayAmp: sway, side: side,
    });
  }

  addDrift(makePythonLogo, 0xc9a86a, -5.5, 1.8, -4, 1.1, 0.55, 0.5, -0.6);
  addDrift(makeTerminal,   0x4d8a6c,  5.5, -1.5, -5, 1.0, 0.6, 0.4, 0.7);
  addDrift(makeBrace,      0xc9a86a,  4.5,  2.8, -4.5, 1.2, 0.7, 0.6, 0.5);
  addDrift(makeDatabase,   0x4d8a6c, -4.8, -2.5, -5.5, 1.0, 0.5, 0.4, -0.4);
  addDrift(makeServer,     0xeccf94,  6.2,  1.2, -5, 1.3, 0.55, 0.5, 0.6);
  addDrift(makeBinaryPanel,0xc9a86a, -4.2, -0.5, -6, 1.0, 0.4, 0.35, -0.5);
  addDrift(makePythonLogo, 0x4d8a6c,  3.6, -3.2, -6, 0.9, 0.5, 0.4, 0.3);
  addDrift(makeTerminal,   0xc9a86a, -6, 3.4, -5.5, 0.9, 0.6, 0.5, -0.7);
  addDrift(makeBrace,      0x4d8a6c,  6.5, -2.8, -6, 0.85, 0.65, 0.5, 0.4);

  // ---- Mouse parallax ----
  var mx = 0, my = 0;
  window.addEventListener("pointermove", function (e) {
    mx = (e.clientX / window.innerWidth - 0.5);
    my = (e.clientY / window.innerHeight - 0.5);
  }, { passive: true });

  // ---- Scroll progress ----
  var sTarget = 0, sCurrent = 0;
  window.addEventListener("scroll", function () {
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    sTarget = max > 0 ? window.scrollY / max : 0;
  }, { passive: true });

  function onResize() {
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", onResize);

  var clock = new THREE.Clock();
  function animate() {
    requestAnimationFrame(animate);
    var t = clock.getElapsedTime();
    sCurrent += (sTarget - sCurrent) * 0.06;

    core.rotation.y = t * 0.1 + sCurrent * Math.PI * 2;
    core.rotation.x = Math.sin(t * 0.15) * 0.15;
    ring2.rotation.z = t * 0.2;
    ring3.rotation.y = -t * 0.15;

    points.rotation.y = -t * 0.05 + sCurrent * 1.1;

    var pulse = 0.5 + Math.sin(t * 1.1) * 0.08;
    outerRing.material.opacity = 0.4 + pulse * 0.2;
    glowSprite.material.opacity = 0.3 + pulse * 0.15;

    camera.position.z = 11 - sCurrent * 3;
    camera.position.x += (mx * 0.7 - camera.position.x) * 0.04;
    camera.position.y += (-my * 0.5 - camera.position.y) * 0.04;
    camera.lookAt(0, 0, 0);

    driftShapes.forEach(function (d) {
      d.mesh.rotation.x = t * 0.06 * d.speed + d.phase + sCurrent * 0.8 * d.speed;
      d.mesh.rotation.y = t * 0.1 * d.speed + sCurrent * 1.4;
      d.mesh.rotation.z = Math.sin(t * 0.2 * d.speed + d.phase) * 0.15;
      d.mesh.position.x = d.base.x + Math.sin(t * 0.25 * d.speed + d.phase) * d.swayAmp + sCurrent * d.side * 4;
      d.mesh.position.y = d.base.y - sCurrent * 5 * d.speed + Math.cos(t * 0.2 * d.speed + d.phase) * 0.35;
    });

    renderer.render(scene, camera);
  }
  animate();

  // ---- Custom cursor ----
  if (window.matchMedia("(pointer: fine)").matches && !reduce) {
    document.body.classList.add("has-cursor");
    var dot = document.getElementById("cdot"), ring = document.getElementById("cring");
    if (!dot || !ring) return;
    var cx = innerWidth/2, cy = innerHeight/2, rx = cx, ry = cy;
    window.addEventListener("pointermove", function (e) { cx = e.clientX; cy = e.clientY; }, { passive: true });

    document.querySelectorAll("a, button, .card, .chip, .point").forEach(function (el) {
      el.addEventListener("pointerenter", function () { ring.classList.add("big"); });
      el.addEventListener("pointerleave", function () { ring.classList.remove("big"); });
    });

    var trail = document.getElementById("trail"), tctx = trail.getContext("2d");
    function sizeTrail() { trail.width = innerWidth; trail.height = innerHeight; }
    sizeTrail();
    window.addEventListener("resize", sizeTrail);

    var particles = [], last = { x: cx, y: cy };
    window.addEventListener("pointermove", function (e) {
      var dx = e.clientX - last.x, dy = e.clientY - last.y;
      if (Math.sqrt(dx*dx + dy*dy) > 6) {
        particles.push({
          x: e.clientX, y: e.clientY, r: 2 + Math.random() * 2.4, life: 1,
          c: Math.random() > 0.65 ? "77,138,108" : "201,168,106",
        });
        last = { x: e.clientX, y: e.clientY };
        if (particles.length > 80) particles.shift();
      }
    }, { passive: true });

    function loop() {
      requestAnimationFrame(loop);
      rx += (cx - rx) * 0.16; ry += (cy - ry) * 0.16;
      dot.style.left = cx + "px"; dot.style.top = cy + "px";
      ring.style.left = rx + "px"; ring.style.top = ry + "px";

      tctx.clearRect(0, 0, trail.width, trail.height);
      tctx.globalCompositeOperation = "lighter";
      for (var i = particles.length - 1; i >= 0; i--) {
        var p = particles[i];
        p.life -= 0.035;
        if (p.life <= 0) { particles.splice(i, 1); continue; }
        tctx.beginPath();
        tctx.fillStyle = "rgba(" + p.c + "," + (p.life * 0.4) + ")";
        tctx.arc(p.x, p.y, p.r * p.life * 1.6, 0, Math.PI * 2);
        tctx.fill();
      }
    }
    loop();
  }
})();
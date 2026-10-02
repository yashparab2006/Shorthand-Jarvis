/**
 * J.A.R.V.I.S. 3D Spatial Holographic Cockpit Engine
 * Dual-Renderer architecture: WebGLRenderer (volumetric meshes/particles) + CSS3DRenderer (spatial DOM panels)
 * Shares unified PerspectiveCamera, cylindrical cockpit coordinates, and spatial micro-interactions.
 */
(function (window) {
  let scene, camera, webglRenderer, css3dRenderer;
  let masterGroup, reactorGroup, backgroundGroup;
  let coreMesh, wireMesh, ring1, ring2, ring3, cageMesh;
  let particleSystem, eqPillars = [];
  let coreLight, ambientLight, dirLight;
  let currentEnergyColor, targetColorHex = 0x00f2fe;

  // Spatial Panels
  let headerObj, leftWingObj, rightWingObj, lowerTrayObj, notesWingObj, centerReadoutObj;

  // Interaction State
  let targetRotX = 0;
  let targetRotY = 0;
  let currentRotX = 0;
  let currentRotY = 0;
  let mouseParallaxX = 0;
  let mouseParallaxY = 0;
  let isDragging = false;
  let prevMouseX = 0;
  let prevMouseY = 0;
  let rotSpeedMult = 1.0;
  let cameraTargetZ = 920;
  let cameraTargetX = 0;
  let cameraTargetY = 0;

  const JarvisSpatialHUD = {
    init(containerEl) {
      if (!containerEl || typeof THREE === 'undefined' || typeof THREE.CSS3DRenderer === 'undefined') {
        console.warn('[JarvisSpatialHUD] Dependencies not ready, retrying in 50ms...');
        setTimeout(() => JarvisSpatialHUD.init(containerEl), 50);
        return;
      }

      const width = window.innerWidth;
      const height = window.innerHeight;

      // 1. Shared Scene & Perspective Camera
      scene = new THREE.Scene();
      camera = new THREE.PerspectiveCamera(50, width / height, 1, 5000);
      camera.position.set(0, 0, cameraTargetZ);

      // 2. WebGL Renderer (Layer 1 - Bottom)
      webglRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
      webglRenderer.setSize(width, height);
      webglRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      webglRenderer.setClearColor(0x000000, 0);
      webglRenderer.domElement.style.position = 'absolute';
      webglRenderer.domElement.style.top = '0';
      webglRenderer.domElement.style.left = '0';
      webglRenderer.domElement.style.zIndex = '1';
      webglRenderer.domElement.style.pointerEvents = 'none';
      containerEl.appendChild(webglRenderer.domElement);

      // 3. CSS3D Renderer (Layer 2 - Top)
      css3dRenderer = new THREE.CSS3DRenderer();
      css3dRenderer.setSize(width, height);
      css3dRenderer.domElement.style.position = 'absolute';
      css3dRenderer.domElement.style.top = '0';
      css3dRenderer.domElement.style.left = '0';
      css3dRenderer.domElement.style.zIndex = '2';
      css3dRenderer.domElement.style.pointerEvents = 'none';
      containerEl.appendChild(css3dRenderer.domElement);

      // Master World Group (for universal pan/tilt)
      masterGroup = new THREE.Group();
      scene.add(masterGroup);

      // 4. Volumetric Background Environment (Stars & Grid)
      this.initBackgroundEnvironment();

      // 5. Central 3D Arc Reactor (WebGL)
      this.initArcReactor();

      // 6. Project DOM Components into 3D Spatial Cockpit (CSS3D)
      this.mountSpatialPanels();

      // 7. Interactive Drag & Pointer Events
      this.setupSpatialInteractions(containerEl);

      // 8. Event Bus Bindings
      this.bindStoreEvents();

      // 9. Window Resize
      window.addEventListener('resize', this.onWindowResize.bind(this));

      // 10. Start Animation Loop
      this.animate();
      console.log('[JarvisSpatialHUD] 3D Spatial Holographic Engine Active.');
    },

    initBackgroundEnvironment() {
      backgroundGroup = new THREE.Group();
      masterGroup.add(backgroundGroup);

      // Stardust Depth Particles
      const starCount = 1000;
      const starGeom = new THREE.BufferGeometry();
      const starPos = new Float32Array(starCount * 3);
      const starCols = new Float32Array(starCount * 3);
      const colCyan = new THREE.Color(0x00f2fe);
      const colBlue = new THREE.Color(0x1d4ed8);
      const colWhite = new THREE.Color(0xffffff);

      for (let i = 0; i < starCount; i++) {
        starPos[i * 3] = (Math.random() - 0.5) * 3200;
        starPos[i * 3 + 1] = (Math.random() - 0.5) * 2200;
        starPos[i * 3 + 2] = -400 - Math.random() * 1800;

        const p = Math.random();
        const c = p > 0.7 ? colWhite : (p > 0.3 ? colCyan : colBlue);
        starCols[i * 3] = c.r;
        starCols[i * 3 + 1] = c.g;
        starCols[i * 3 + 2] = c.b;
      }
      starGeom.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
      starGeom.setAttribute('color', new THREE.BufferAttribute(starCols, 3));

      const starMat = new THREE.PointsMaterial({
        size: 2.2,
        vertexColors: true,
        transparent: true,
        opacity: 0.65,
        blending: THREE.AdditiveBlending
      });
      const stars = new THREE.Points(starGeom, starMat);
      backgroundGroup.add(stars);

      // Cybernetic Ground Horizon Grid
      const gridHelper = new THREE.GridHelper(2600, 44, 0x00f2fe, 0x1e293b);
      gridHelper.position.set(0, -460, -400);
      gridHelper.material.opacity = 0.28;
      gridHelper.material.transparent = true;
      backgroundGroup.add(gridHelper);
    },

    initArcReactor() {
      reactorGroup = new THREE.Group();
      reactorGroup.position.set(0, 30, -50);
      masterGroup.add(reactorGroup);

      currentEnergyColor = new THREE.Color(0x00f2fe);

      // Core Crystalline Icosahedron
      const coreGeom = new THREE.IcosahedronGeometry(20, 2);
      const coreMat = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        emissive: 0x00f2fe,
        emissiveIntensity: 0.95,
        roughness: 0.15,
        metalness: 0.85
      });
      coreMesh = new THREE.Mesh(coreGeom, coreMat);
      reactorGroup.add(coreMesh);

      // Wireframe Holographic Shell
      const wireGeom = new THREE.IcosahedronGeometry(26, 1);
      const wireMat = new THREE.MeshBasicMaterial({
        color: 0x00f2fe,
        wireframe: true,
        transparent: true,
        opacity: 0.55
      });
      wireMesh = new THREE.Mesh(wireGeom, wireMat);
      reactorGroup.add(wireMesh);

      // Concentric Torus Gimbals
      const ring1Geom = new THREE.TorusGeometry(38, 1.2, 16, 90);
      const ring1Mat = new THREE.MeshStandardMaterial({ color: 0x00f2fe, emissive: 0x00a3ff, emissiveIntensity: 0.6, metalness: 0.9 });
      ring1 = new THREE.Mesh(ring1Geom, ring1Mat);
      reactorGroup.add(ring1);

      const ring2Geom = new THREE.TorusGeometry(54, 1.6, 16, 100);
      const ring2Mat = new THREE.MeshStandardMaterial({ color: 0x3b82f6, emissive: 0x1d4ed8, emissiveIntensity: 0.5, metalness: 0.85 });
      ring2 = new THREE.Mesh(ring2Geom, ring2Mat);
      ring2.rotation.x = Math.PI / 4;
      reactorGroup.add(ring2);

      const ring3Geom = new THREE.TorusGeometry(72, 2.0, 16, 120);
      const ring3Mat = new THREE.MeshStandardMaterial({ color: 0x00f2fe, emissive: 0x0284c7, emissiveIntensity: 0.45, metalness: 0.9 });
      ring3 = new THREE.Mesh(ring3Geom, ring3Mat);
      ring3.rotation.y = Math.PI / 3;
      reactorGroup.add(ring3);

      // Outer Hex Cage
      const cageGeom = new THREE.CylinderGeometry(80, 80, 12, 36, 1, true);
      const cageMat = new THREE.MeshBasicMaterial({ color: 0x00f2fe, wireframe: true, transparent: true, opacity: 0.35 });
      cageMesh = new THREE.Mesh(cageGeom, cageMat);
      reactorGroup.add(cageMesh);

      // Particle Accretion Vortex
      const particleCount = 1400;
      const particleGeom = new THREE.BufferGeometry();
      const particlePositions = new Float32Array(particleCount * 3);
      const particleColors = new Float32Array(particleCount * 3);
      const colCyan = new THREE.Color(0x00f2fe);
      const colBlue = new THREE.Color(0x3b82f6);
      const colWhite = new THREE.Color(0xffffff);

      for (let i = 0; i < particleCount; i++) {
        const rad = 30 + Math.random() * 90;
        const theta = Math.random() * Math.PI * 2;
        particlePositions[i * 3] = rad * Math.cos(theta);
        particlePositions[i * 3 + 1] = rad * Math.sin(theta);
        particlePositions[i * 3 + 2] = (Math.random() - 0.5) * 35;

        const pick = Math.random();
        const c = pick > 0.65 ? colWhite : (pick > 0.3 ? colCyan : colBlue);
        particleColors[i * 3] = c.r;
        particleColors[i * 3 + 1] = c.g;
        particleColors[i * 3 + 2] = c.b;
      }
      particleGeom.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
      particleGeom.setAttribute('color', new THREE.BufferAttribute(particleColors, 3));

      const particleMat = new THREE.PointsMaterial({
        size: 2.2,
        vertexColors: true,
        transparent: true,
        opacity: 0.85,
        blending: THREE.AdditiveBlending
      });
      particleSystem = new THREE.Points(particleGeom, particleMat);
      reactorGroup.add(particleSystem);

      // 32-Pillar 3D Audio-Reactive Equalizer Ring
      const eqCount = 32;
      const eqRadius = 96;
      eqPillars = [];
      const pillarGeom = new THREE.CylinderGeometry(1.2, 1.2, 1, 8);
      const pillarMat = new THREE.MeshStandardMaterial({
        color: 0x00f2fe,
        emissive: 0x00f2fe,
        emissiveIntensity: 0.7,
        metalness: 0.6,
        roughness: 0.2
      });

      for (let i = 0; i < eqCount; i++) {
        const angle = (i / eqCount) * Math.PI * 2;
        const pMesh = new THREE.Mesh(pillarGeom, pillarMat.clone());
        pMesh.position.x = Math.cos(angle) * eqRadius;
        pMesh.position.y = Math.sin(angle) * eqRadius;
        pMesh.position.z = 0;
        pMesh.rotation.z = angle + Math.PI / 2;
        reactorGroup.add(pMesh);
        eqPillars.push(pMesh);
      }

      // Lights
      coreLight = new THREE.PointLight(0x00f2fe, 4.0, 350);
      coreLight.position.set(0, 0, 0);
      reactorGroup.add(coreLight);

      ambientLight = new THREE.AmbientLight(0x051525, 1.8);
      scene.add(ambientLight);

      dirLight = new THREE.DirectionalLight(0x60a5fa, 1.2);
      dirLight.position.set(100, 150, 200);
      scene.add(dirLight);
    },

    mountSpatialPanels() {
      const appContainer = document.querySelector('.jarvis-app-container');
      if (appContainer) {
        appContainer.style.pointerEvents = 'none';
      }

      // 1. Top Visor Crown: Header
      const headerEl = document.querySelector('.hud-header');
      if (headerEl) {
        headerEl.classList.add('spatial-panel', 'visor-panel');
        headerObj = new THREE.CSS3DObject(headerEl);
        headerObj.position.set(0, 360, -100);
        headerObj.rotation.set(0, 0, 0);
        masterGroup.add(headerObj);
      }

      // 2. Left Flank Wing: Sidebar (Telemetry + Launchpad)
      const leftWingEl = document.querySelector('.hud-sidebar');
      if (leftWingEl) {
        leftWingEl.classList.add('spatial-panel', 'left-wing-panel');
        leftWingObj = new THREE.CSS3DObject(leftWingEl);
        leftWingObj.position.set(-470, 0, -60);
        leftWingObj.rotation.set(0, 0, 0);
        masterGroup.add(leftWingObj);
      }

      // 3. Right Flank Wing: Chat Stream Console
      const rightWingEl = document.querySelector('.hud-chat-section');
      if (rightWingEl) {
        rightWingEl.classList.add('spatial-panel', 'right-wing-panel');
        rightWingObj = new THREE.CSS3DObject(rightWingEl);
        rightWingObj.position.set(470, 0, -60);
        rightWingObj.rotation.set(0, 0, 0);
        masterGroup.add(rightWingObj);
      }

      // 4. Lower Cockpit Tray: Command Input Dock & Chips
      const lowerTrayEl = document.querySelector('.hud-lower-tray');
      if (lowerTrayEl) {
        lowerTrayEl.classList.add('spatial-panel', 'lower-tray-panel');
        lowerTrayObj = new THREE.CSS3DObject(lowerTrayEl);
        lowerTrayObj.position.set(0, -330, 0);
        lowerTrayObj.rotation.set(0, 0, 0);
        masterGroup.add(lowerTrayObj);
      }

      // 5. Spatial Notes Drawer Wing
      const notesEl = document.getElementById('notesDrawer');
      if (notesEl) {
        notesEl.classList.add('spatial-panel', 'notes-wing-panel');
        notesWingObj = new THREE.CSS3DObject(notesEl);
        notesWingObj.position.set(560, 0, 0);
        notesWingObj.rotation.set(0, 0, 0);
        notesWingObj.visible = false;
        masterGroup.add(notesWingObj);
      }
    },

    setupSpatialInteractions(containerEl) {
      // 3D Mesh Raycasting (Arc Reactor Hover & Click Flare)
      const raycaster = new THREE.Raycaster();
      const mouseVec = new THREE.Vector2();

      window.addEventListener('pointermove', (e) => {
        mouseVec.x = (e.clientX / window.innerWidth) * 2 - 1;
        mouseVec.y = -(e.clientY / window.innerHeight) * 2 + 1;

        if (camera && coreMesh) {
          raycaster.setFromCamera(mouseVec, camera);
          const intersects = raycaster.intersectObjects([coreMesh, wireMesh, ring1, ring2, ring3]);
          if (intersects.length > 0) {
            document.body.style.cursor = 'pointer';
            if (coreMesh.material && coreMesh.material.emissiveIntensity < 1.4) {
              coreMesh.material.emissiveIntensity = 1.6;
            }
          } else {
            if (coreMesh.material && coreMesh.material.emissiveIntensity > 1.0) {
              coreMesh.material.emissiveIntensity = 0.95;
            }
          }
        }
      });

      window.addEventListener('click', (e) => {
        if (e.target.closest('input, button, .chat-stream-box, .hud-card, a, .note-item, .launch-btn, .chip-btn, .hud-switch, .slider, .icon-btn, .btn-3d-tool')) {
          return;
        }
        if (camera && coreMesh) {
          raycaster.setFromCamera(mouseVec, camera);
          const intersects = raycaster.intersectObjects([coreMesh, wireMesh, ring1, ring2, ring3]);
          if (intersects.length > 0) {
            if (window.JarvisAudio) window.JarvisAudio.playSound('success');
            if (coreLight) {
              coreLight.intensity = 7.0;
              setTimeout(() => { if (coreLight) coreLight.intensity = 4.0; }, 350);
            }
            if (window.JarvisStore) {
              window.JarvisStore.emit('core:click');
            }
          }
        }
      });
    },

    resetCamera() {
      targetRotX = 0;
      targetRotY = 0;
      cameraTargetX = 0;
      cameraTargetY = 0;
      cameraTargetZ = 920;
      if (window.JarvisAudio) window.JarvisAudio.playSound('click');
    },

    focusWing(wing) {
      // Screen rotation disabled: keeps interface fixed and stable
      cameraTargetX = 0;
      cameraTargetY = 0;
    },

    bindStoreEvents() {
      if (!window.JarvisStore) return;

      // Color transitions matching system states
      window.JarvisStore.on('state:system', ({ state }) => {
        if (state === 'listening') {
          targetColorHex = 0xf59e0b; // Amber
          rotSpeedMult = 2.2;
        } else if (state === 'speaking') {
          targetColorHex = 0x10b981; // Emerald
          rotSpeedMult = 1.6;
        } else if (state === 'processing') {
          targetColorHex = 0x8b5cf6; // Violet
          rotSpeedMult = 3.0;
        } else {
          targetColorHex = 0x00f2fe; // Cyan (Idle)
          rotSpeedMult = 1.0;
        }
      });

      // Spatial Notes Drawer
      window.JarvisStore.on('notes:drawer', (isOpen) => {
        if (!notesWingObj) return;
        notesWingObj.visible = isOpen;
        notesWingObj.position.set(560, 0, 0);
        notesWingObj.rotation.set(0, 0, 0);
      });
    },

    onWindowResize() {
      const w = window.innerWidth;
      const h = window.innerHeight;
      if (w === 0 || h === 0) return;

      camera.aspect = w / h;
      camera.updateProjectionMatrix();

      webglRenderer.setSize(w, h);
      css3dRenderer.setSize(w, h);

      // Adaptive camera distance for smaller displays
      cameraTargetZ = w < 1200 ? 1100 : 920;
    },

    animate() {
      requestAnimationFrame(this.animate.bind(this));

      // Fixed orientation: No screen rotation or tilting
      masterGroup.rotation.set(0, 0, 0);

      // Fixed Camera View
      camera.position.set(0, 0, cameraTargetZ);
      camera.lookAt(0, 0, 0);

      // Organic background starfield drift
      if (backgroundGroup) {
        backgroundGroup.rotation.y += 0.0003;
      }

      // Color lerp toward state color
      if (currentEnergyColor && coreLight) {
        currentEnergyColor.lerp(new THREE.Color(targetColorHex), 0.08);
        coreLight.color.copy(currentEnergyColor);
        if (coreMesh) coreMesh.material.emissive.copy(currentEnergyColor);
        if (wireMesh) wireMesh.material.color.copy(currentEnergyColor);
        if (ring1) ring1.material.emissive.copy(currentEnergyColor);
        if (ring3) ring3.material.color.copy(currentEnergyColor);
      }

      // Volumetric Core Animations
      const baseSpeed = 0.015 * rotSpeedMult;
      if (coreMesh) {
        coreMesh.rotation.y += baseSpeed * 1.5;
        coreMesh.rotation.x += baseSpeed * 0.8;
      }
      if (wireMesh) {
        wireMesh.rotation.y -= baseSpeed * 1.2;
        wireMesh.rotation.z += baseSpeed * 0.5;
      }
      if (ring1) ring1.rotation.z += baseSpeed * 1.8;
      if (ring2) ring2.rotation.x += baseSpeed * 1.4;
      if (ring3) ring3.rotation.y -= baseSpeed * 1.1;
      if (cageMesh) cageMesh.rotation.z -= baseSpeed * 0.6;

      if (particleSystem) {
        particleSystem.rotation.z += baseSpeed * 2.0;
      }

      // Audio-Reactive Equalizer Pillars
      const curState = window.JarvisStore ? window.JarvisStore.get('systemState') : 'idle';
      const timeNow = Date.now();
      for (let i = 0; i < eqPillars.length; i++) {
        let pHeight = 2;
        if (curState === 'speaking') {
          pHeight = 4 + Math.sin(timeNow * 0.012 + i * 0.6) * 14 + Math.cos(timeNow * 0.018 + i * 0.3) * 8;
        } else if (curState === 'listening') {
          pHeight = 3 + Math.random() * 18;
        } else if (curState === 'processing') {
          pHeight = 4 + Math.sin(timeNow * 0.025 + i * 0.8) * 10;
        } else {
          pHeight = 2 + Math.sin(timeNow * 0.003 + i * 0.4) * 3;
        }
        const clampedH = Math.max(1.5, pHeight);
        eqPillars[i].scale.set(1, clampedH, 1);
        if (currentEnergyColor) eqPillars[i].material.emissive.copy(currentEnergyColor);
      }

      // Dual Render
      webglRenderer.render(scene, camera);
      css3dRenderer.render(scene, camera);
    }
  };

  window.JarvisSpatialHUD = JarvisSpatialHUD;
})(window);


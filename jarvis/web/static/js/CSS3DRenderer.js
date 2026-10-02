/**
 * Based on Three.js r128 CSS3DRenderer
 * Permits genuine DOM elements to be projected directly into 3D spatial space
 * sharing the exact same PerspectiveCamera and coordinate matrices as WebGL.
 */
(function () {
  if (typeof THREE === 'undefined') {
    console.error('[CSS3DRenderer] Three.js must be loaded before CSS3DRenderer.');
    return;
  }
  const _matrix = new THREE.Matrix4();

  class CSS3DObject extends THREE.Object3D {
    constructor(element = document.createElement('div')) {
      super();
      this.element = element;
      this.element.style.position = 'absolute';
      this.element.style.pointerEvents = 'auto';
      this.element.style.userSelect = 'none';

      this.addEventListener('removed', function () {
        this.traverse(function (object) {
          if (object.element instanceof Element && object.element.parentNode !== null) {
            object.element.parentNode.removeChild(object.element);
          }
        });
      });
    }

    copy(source, recursive) {
      super.copy(source, recursive);
      this.element = source.element.cloneNode(true);
      return this;
    }
  }

  class CSS3DSprite extends CSS3DObject {
    constructor(element) {
      super(element);
    }
  }

  class CSS3DRenderer {
    constructor() {
      let _width, _height;
      let _widthHalf, _heightHalf;

      const domElement = document.createElement('div');
      domElement.style.overflow = 'hidden';
      this.domElement = domElement;

      const cameraElement = document.createElement('div');
      cameraElement.style.transformStyle = 'preserve-3d';
      cameraElement.style.pointerEvents = 'none';
      domElement.appendChild(cameraElement);

      this.getSize = function () {
        return { width: _width, height: _height };
      };

      this.setSize = function (width, height) {
        _width = width;
        _height = height;
        _widthHalf = _width / 2;
        _heightHalf = _height / 2;

        domElement.style.width = width + 'px';
        domElement.style.height = height + 'px';

        cameraElement.style.width = width + 'px';
        cameraElement.style.height = height + 'px';
      };

      function epsilon(value) {
        return Math.abs(value) < 1e-10 ? 0 : value;
      }

      function getCameraCSSMatrix(matrix) {
        const elements = matrix.elements;
        return 'matrix3d(' +
          epsilon(elements[0]) + ',' +
          epsilon(-elements[1]) + ',' +
          epsilon(elements[2]) + ',' +
          epsilon(elements[3]) + ',' +
          epsilon(elements[4]) + ',' +
          epsilon(-elements[5]) + ',' +
          epsilon(elements[6]) + ',' +
          epsilon(elements[7]) + ',' +
          epsilon(elements[8]) + ',' +
          epsilon(-elements[9]) + ',' +
          epsilon(elements[10]) + ',' +
          epsilon(elements[11]) + ',' +
          epsilon(elements[12]) + ',' +
          epsilon(-elements[13]) + ',' +
          epsilon(elements[14]) + ',' +
          epsilon(elements[15]) +
        ')';
      }

      function getObjectCSSMatrix(matrix) {
        const elements = matrix.elements;
        return 'translate(-50%,-50%) matrix3d(' +
          epsilon(elements[0]) + ',' +
          epsilon(elements[1]) + ',' +
          epsilon(elements[2]) + ',' +
          epsilon(elements[3]) + ',' +
          epsilon(-elements[4]) + ',' +
          epsilon(-elements[5]) + ',' +
          epsilon(-elements[6]) + ',' +
          epsilon(-elements[7]) + ',' +
          epsilon(elements[8]) + ',' +
          epsilon(elements[9]) + ',' +
          epsilon(elements[10]) + ',' +
          epsilon(elements[11]) + ',' +
          epsilon(elements[12]) + ',' +
          epsilon(elements[13]) + ',' +
          epsilon(elements[14]) + ',' +
          epsilon(elements[15]) +
        ')';
      }

      const cache = {
        camera: { fov: 0, style: '' },
        objects: new WeakMap()
      };

      const _this = this;

      function renderObject(object, scene, camera) {
        if (object.isCSS3DObject) {
          let style;
          if (object.isCSS3DSprite) {
            _matrix.copy(camera.matrixWorldInverse);
            _matrix.transpose();
            _matrix.copyPosition(object.matrixWorld);
            _matrix.scale(object.scale);

            _matrix.elements[3] = 0;
            _matrix.elements[7] = 0;
            _matrix.elements[11] = 0;
            _matrix.elements[15] = 1;

            style = getObjectCSSMatrix(_matrix);
          } else {
            style = getObjectCSSMatrix(object.matrixWorld);
          }

          const element = object.element;
          const cachedObject = cache.objects.get(object);

          if (cachedObject === undefined || cachedObject.style !== style) {
            element.style.transform = style;
            cache.objects.set(object, { style });
          }

          element.style.display = object.visible ? '' : 'none';

          if (element.parentNode !== cameraElement) {
            cameraElement.appendChild(element);
          }
        }

        for (let i = 0, l = object.children.length; i < l; i++) {
          renderObject(object.children[i], scene, camera);
        }
      }

      this.render = function (scene, camera) {
        const fov = camera.projectionMatrix.elements[5] * _heightHalf;

        if (cache.camera.fov !== fov) {
          domElement.style.perspective = camera.isPerspectiveCamera ? fov + 'px' : '';
          cache.camera.fov = fov;
        }

        if (scene.autoUpdate === true) scene.updateMatrixWorld();
        if (camera.parent === null) camera.updateMatrixWorld();

        const cameraCSSMatrix = camera.isOrthographicCamera
          ? 'scale(' + fov + ')' + getCameraCSSMatrix(camera.matrixWorldInverse)
          : 'translateZ(' + fov + 'px)' + getCameraCSSMatrix(camera.matrixWorldInverse);

        const style = cameraCSSMatrix + 'translate(' + _widthHalf + 'px,' + _heightHalf + 'px)';

        if (cache.camera.style !== style) {
          cameraElement.style.transform = style;
          cache.camera.style = style;
        }

        renderObject(scene, scene, camera);
      };
    }
  }

  CSS3DObject.prototype.isCSS3DObject = true;
  CSS3DSprite.prototype.isCSS3DSprite = true;

  THREE.CSS3DObject = CSS3DObject;
  THREE.CSS3DSprite = CSS3DSprite;
  THREE.CSS3DRenderer = CSS3DRenderer;
})();


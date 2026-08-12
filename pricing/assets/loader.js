/**
 * loader.js — Smooth SVG clip-path animation for #cr-overlay
 * Include this script in every page AFTER the #cr-overlay markup.
 * Call window.hideLoader() when data is ready.
 */
(function () {
    const SVG_NS = 'http://www.w3.org/2000/svg';
    const overlay = document.getElementById('cr-overlay');
    const svg = overlay ? overlay.querySelector('.loader') : null;

    if (!svg) return;

    const defs = svg.querySelector('defs');

    const config = [
        { id: 'a2', fill: 'url(#lg1)', bb: { x: 1,  y: 68, width: 68,  height: 77  }, dir: 'up'    },
        { id: 'a3', fill: 'url(#lg2)', bb: { x: 13, y: 13, width: 135, height: 134 }, dir: 'right'  },
        { id: 'a1', fill: 'url(#lg)',  bb: { x: 90, y: 14, width: 69,  height: 77  }, dir: 'up'     },
    ];

    const clips = config.map(({ id, fill, bb, dir }, i) => {
        const cp   = document.createElementNS(SVG_NS, 'clipPath');
        cp.setAttribute('id', `clip${i}`);
        const rect = document.createElementNS(SVG_NS, 'rect');
        cp.appendChild(rect);
        defs.appendChild(cp);

        const el = document.getElementById(id);
        if (el) {
            el.setAttribute('fill', fill);
            el.style.opacity = 1;
            el.setAttribute('clip-path', `url(#clip${i})`);
        }

        return { rect, bb, dir };
    });

    const STEP    = 400;
    const OVERLAP = 150;
    const RESET   = 100;

    let loopTimer = null;
    let rafIds    = [];
    let running   = true;

    function resetClips() {
        clips.forEach(({ rect, bb, dir }) => {
            if (dir === 'up') {
                rect.setAttribute('x',      String(bb.x));
                rect.setAttribute('y',      String(bb.y + bb.height));
                rect.setAttribute('width',  String(bb.width));
                rect.setAttribute('height', '0');
            } else if (dir === 'right') {
                rect.setAttribute('x',      String(bb.x));
                rect.setAttribute('y',      String(bb.y));
                rect.setAttribute('width',  '0');
                rect.setAttribute('height', String(bb.height));
            } else {
                rect.setAttribute('x',      String(bb.x));
                rect.setAttribute('y',      String(bb.y));
                rect.setAttribute('width',  String(bb.width));
                rect.setAttribute('height', '0');
            }
        });
    }

    function runLoop() {
        if (!running) return;
        resetClips();

        clips.reduce((delay, { rect, bb, dir }) => {
            const timer = setTimeout(() => {
                if (!running) return;
                let startTime = null;
                function sweep(ts) {
                    if (!running) return;
                    if (!startTime) startTime = ts;
                    const t    = Math.min((ts - startTime) / STEP, 1);
                    const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;

                    if (dir === 'up') {
                        const h = ease * bb.height;
                        rect.setAttribute('y',      String(bb.y + bb.height - h));
                        rect.setAttribute('x',      String(bb.x));
                        rect.setAttribute('width',  String(bb.width));
                        rect.setAttribute('height', String(h));
                    } else if (dir === 'right') {
                        rect.setAttribute('x',      String(bb.x));
                        rect.setAttribute('y',      String(bb.y));
                        rect.setAttribute('width',  String(ease * bb.width));
                        rect.setAttribute('height', String(bb.height));
                    } else {
                        rect.setAttribute('x',      String(bb.x));
                        rect.setAttribute('y',      String(bb.y));
                        rect.setAttribute('width',  String(bb.width));
                        rect.setAttribute('height', String(ease * bb.height));
                    }
                    if (t < 1) rafIds.push(requestAnimationFrame(sweep));
                }
                rafIds.push(requestAnimationFrame(sweep));
            }, delay);
            loopTimer = timer;
            return delay + STEP - OVERLAP;
        }, 0);

        const totalDuration = (STEP - OVERLAP) * 2 + STEP + 100;
        loopTimer = setTimeout(() => {
            resetClips();
            loopTimer = setTimeout(runLoop, RESET);
        }, totalDuration);
    }

    runLoop();

    /* Public API — call from each page's JS when data is ready */
    window.hideLoader = function () {
        running = false;
        // Cancel pending rAF and timers
        rafIds.forEach(id => cancelAnimationFrame(id));
        clearTimeout(loopTimer);

        if (overlay) {
            overlay.style.transition = 'opacity 0.45s ease';
            overlay.style.opacity    = '0';
            setTimeout(() => { overlay.classList.add('hidden'); }, 450);
        }
    };
})();

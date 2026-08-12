// =====================================================================
// data-manager.js — Logic quản lý dữ liệu (Sources, Anomalies, Products, History)
// =====================================================================

const DM = (() => {
    // ── State ────────────────────────────────────────────────────────
    let _sources    = [];   // raw list từ Supabase
    let _products   = [];   // raw products
    let _latestPrices = []; // latest_prices_cache
    let _sourcesFiltered = [];
    let _productsFiltered = [];
    let _histSkuSelected = '';
    let _modalCallback = null;

    // ── Helpers ──────────────────────────────────────────────────────
    const $ = id => document.getElementById(id);
    const fmt = v => v != null ? new Intl.NumberFormat('vi-VN').format(v) + ' ₫' : '—';
    const timeAgo = iso => {
        if (!iso) return '—';
        const d = Math.floor((Date.now() - new Date(iso)) / 1000);
        if (d < 60)  return `${d}s trước`;
        if (d < 3600) return `${Math.floor(d/60)}p trước`;
        if (d < 86400) return `${Math.floor(d/3600)}h trước`;
        return `${Math.floor(d/86400)} ngày trước`;
    };
    const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

    // ── Toast ────────────────────────────────────────────────────────
    function toast(msg, type = 'success') {
        const wrap = $('dm-toast');
        const el = document.createElement('div');
        const icons = { success: 'bi-check-circle', error: 'bi-x-circle', warn: 'bi-exclamation-triangle' };
        el.className = `toast-item toast-${type}`;
        el.innerHTML = `<i class="bi ${icons[type]||'bi-info-circle'}"></i> ${esc(msg)}`;
        wrap.appendChild(el);
        setTimeout(() => el.remove(), 3500);
    }

    // ── Modal ────────────────────────────────────────────────────────
    function showModal({ title, body, warn, confirmText = 'Xóa', confirmClass = 'btn-modal-confirm', onConfirm }) {
        $('modal-title').innerHTML = title;
        $('modal-body').innerHTML = body;
        const warnEl = $('modal-warn');
        if (warn) { warnEl.style.display = ''; warnEl.textContent = warn; }
        else warnEl.style.display = 'none';
        const btn = $('modal-confirm-btn');
        btn.textContent = confirmText;
        btn.className = confirmClass;
        _modalCallback = onConfirm;
        btn.onclick = () => { closeModal(); if (_modalCallback) _modalCallback(); };
        $('dm-modal-backdrop').style.display = 'flex';
    }
    function closeModal() { $('dm-modal-backdrop').style.display = 'none'; }

    // ── Tab switching ────────────────────────────────────────────────
    function switchTab(name) {
        document.querySelectorAll('.dm-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.dm-panel').forEach(p => p.classList.remove('active'));
        document.getElementById(`tab-btn-${name}`).classList.add('active');
        document.getElementById(`panel-${name}`).classList.add('active');
    }

    // ── Supabase PATCH helper ────────────────────────────────────────
    async function sbPatch(table, match, data) {
        const params = Object.entries(match).map(([k,v]) => `${k}=eq.${encodeURIComponent(v)}`).join('&');
        const url = `${SUPABASE_URL}/rest/v1/${table}?${params}`;
        const res = await fetch(url, {
            method: 'PATCH',
            headers: { ...headers, 'Prefer': 'return=minimal' },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error(await res.text());
    }

    // ── Supabase DELETE helper ───────────────────────────────────────
    async function sbDelete(table, match) {
        const params = Object.entries(match).map(([k,v]) => `${k}=eq.${encodeURIComponent(v)}`).join('&');
        const url = `${SUPABASE_URL}/rest/v1/${table}?${params}`;
        const res = await fetch(url, { method: 'DELETE', headers: { ...headers, 'Prefer': 'return=minimal' } });
        if (!res.ok) throw new Error(await res.text());
    }

    // ====================================================================
    // TAB 1 — SOURCES
    // ====================================================================
    async function loadSources() {
        $('sources-tbody').innerHTML = '<tr class="loading-row"><td colspan="8"><span class="spinner"></span> Đang tải...</td></tr>';
        try {
            // Fetch sources joined with latest price
            const [srcData, lpData] = await Promise.all([
                supabaseFetch('sources', 'select=product_sku,competitor,url,active,products(name)&order=competitor,product_sku'),
                supabaseFetch('latest_prices_cache', 'select=sku,competitor,price,updated_at')
            ]);
            _sources = srcData;
            // Build price lookup
            const priceMap = {};
            lpData.forEach(r => { priceMap[`${r.sku}|||${r.competitor}`] = r; });
            _sources.forEach(s => { s._priceInfo = priceMap[`${s.product_sku}|||${s.competitor}`] || null; });

            // Fill store filter
            const stores = [...new Set(_sources.map(s => s.competitor))].sort();
            const sf = $('src-filter-store');
            sf.innerHTML = '<option value="">Tất cả cửa hàng</option>' + stores.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');

            $('tab-count-sources').textContent = _sources.length;
            $('sources-meta').textContent = `${_sources.length} nguồn tổng cộng`;
            filterSources();
        } catch(e) {
            $('sources-tbody').innerHTML = `<tr><td colspan="8" class="text-center" style="color:var(--red)"><i class="bi bi-x-circle"></i> Lỗi: ${esc(e.message)}</td></tr>`;
        }
    }

    function filterSources() {
        const q   = $('src-search').value.toLowerCase();
        const st  = $('src-filter-store').value;
        const sta = $('src-filter-status').value;
        _sourcesFiltered = _sources.filter(s => {
            const name = (s.products?.name || '').toLowerCase();
            const matchQ = !q || s.product_sku.toLowerCase().includes(q) || name.includes(q) || s.competitor.toLowerCase().includes(q) || s.url.toLowerCase().includes(q);
            const matchSt = !st || s.competitor === st;
            const matchSta = !sta || (sta === 'active' ? s.active : !s.active);
            return matchQ && matchSt && matchSta;
        });
        renderSources();
    }

    function renderSources() {
        const tbody = $('sources-tbody');
        if (!_sourcesFiltered.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center">Không tìm thấy nguồn nào</td></tr>'; return;
        }
        tbody.innerHTML = _sourcesFiltered.map(s => {
            const name = esc(s.products?.name || '—');
            const price = s._priceInfo ? fmt(s._priceInfo.price) : '—';
            const updAt = s._priceInfo ? timeAgo(s._priceInfo.updated_at) : '—';
            const shortUrl = s.url.length > 45 ? s.url.slice(0, 45) + '…' : s.url;
            return `<tr>
                <td><a href="product.php?sku=${esc(s.product_sku)}" class="btn-ghost" style="font-family:'Exo 2',monospace;font-size:0.8rem">${esc(s.product_sku)}</a></td>
                <td style="max-width:240px;font-size:0.85rem">${name}</td>
                <td><span class="badge badge-neutral">${esc(s.competitor)}</span></td>
                <td style="max-width:220px">
                    <div id="url-view-${esc(s.product_sku)}-${esc(s.competitor)}" style="display:flex;align-items:center;gap:0.4rem">
                        <a href="${esc(s.url)}" target="_blank" title="${esc(s.url)}" style="font-size:0.8rem;color:var(--accent);text-decoration:none;word-break:break-all">${esc(shortUrl)}</a>
                        <button class="icon-btn icon-btn-edit" onclick="DM.startEditUrl('${esc(s.product_sku)}','${esc(s.competitor)}','${esc(s.url)}')" title="Sửa URL"><i class="bi bi-pencil"></i></button>
                    </div>
                    <div id="url-edit-${esc(s.product_sku)}-${esc(s.competitor)}" style="display:none;gap:0.4rem;align-items:center">
                        <input class="inline-input" id="url-input-${esc(s.product_sku)}-${esc(s.competitor)}" value="${esc(s.url)}" style="min-width:260px">
                        <button class="icon-btn icon-btn-save" onclick="DM.saveUrl('${esc(s.product_sku)}','${esc(s.competitor)}')"><i class="bi bi-check-lg"></i></button>
                        <button class="icon-btn icon-btn-cancel" onclick="DM.cancelEditUrl('${esc(s.product_sku)}','${esc(s.competitor)}')"><i class="bi bi-x-lg"></i></button>
                    </div>
                </td>
                <td style="white-space:nowrap;font-weight:600">${price}</td>
                <td style="white-space:nowrap;color:var(--text-muted);font-size:0.82rem">${updAt}</td>
                <td style="text-align:center">
                    <input type="checkbox" class="toggle" ${s.active ? 'checked' : ''} onchange="DM.toggleActive('${esc(s.product_sku)}','${esc(s.competitor)}',this.checked)" title="${s.active ? 'Đang bật — click để tắt' : 'Đang tắt — click để bật'}">
                </td>
                <td>
                    <div class="action-cell">
                        <a href="${esc(s.url)}" target="_blank" class="btn-ghost"><i class="bi bi-box-arrow-up-right"></i> Mở web</a>
                        <button class="btn-danger" onclick="DM.deleteSource('${esc(s.product_sku)}','${esc(s.competitor)}','${esc(s.products?.name||s.product_sku)}')"><i class="bi bi-trash"></i> Xóa</button>
                    </div>
                </td>
            </tr>`;
        }).join('');
    }

    function startEditUrl(sku, competitor, currentUrl) {
        const k = `${sku}-${competitor}`;
        document.getElementById(`url-view-${k}`).style.display = 'none';
        const editDiv = document.getElementById(`url-edit-${k}`);
        editDiv.style.display = 'flex';
        document.getElementById(`url-input-${k}`).focus();
    }
    function cancelEditUrl(sku, competitor) {
        const k = `${sku}-${competitor}`;
        document.getElementById(`url-view-${k}`).style.display = 'flex';
        document.getElementById(`url-edit-${k}`).style.display = 'none';
    }
    async function saveUrl(sku, competitor) {
        const k = `${sku}-${competitor}`;
        const newUrl = document.getElementById(`url-input-${k}`).value.trim();
        if (!newUrl) { toast('URL không được để trống', 'error'); return; }
        try {
            await sbPatch('sources', { product_sku: sku, competitor }, { url: newUrl });
            // Update local state
            const src = _sources.find(s => s.product_sku === sku && s.competitor === competitor);
            if (src) src.url = newUrl;
            cancelEditUrl(sku, competitor);
            filterSources();
            toast(`Đã cập nhật URL cho ${competitor} — ${sku}`, 'success');
        } catch(e) { toast('Lỗi cập nhật: ' + e.message, 'error'); }
    }

    async function toggleActive(sku, competitor, active) {
        try {
            await sbPatch('sources', { product_sku: sku, competitor }, { active });
            const src = _sources.find(s => s.product_sku === sku && s.competitor === competitor);
            if (src) src.active = active;
            toast(`${active ? '✅ Đã bật' : '❌ Đã tắt'} nguồn ${competitor} — ${sku}`, active ? 'success' : 'warn');
        } catch(e) {
            toast('Lỗi cập nhật: ' + e.message, 'error');
            // Revert UI
            filterSources();
        }
    }

    function deleteSource(sku, competitor, productName) {
        showModal({
            title: '<i class="bi bi-trash"></i> Xóa nguồn cào giá',
            body: `Xóa hoàn toàn nguồn <strong>${esc(competitor)}</strong> cho sản phẩm:<br><em>${esc(productName)}</em> (SKU: <code>${esc(sku)}</code>)?<br><br>Toàn bộ lịch sử giá của cửa hàng này cho sản phẩm này sẽ bị xóa.`,
            warn: '⚠️ Hành động này không thể hoàn tác. Nếu scraper vẫn tìm thấy sản phẩm, nó có thể tự tạo lại nguồn này.',
            confirmText: 'Xóa nguồn',
            onConfirm: async () => {
                try {
                    await sbDelete('price_history', { product_sku: sku, competitor });
                    await sbDelete('sources', { product_sku: sku, competitor });
                    _sources = _sources.filter(s => !(s.product_sku === sku && s.competitor === competitor));
                    $('tab-count-sources').textContent = _sources.length;
                    filterSources();
                    toast(`Đã xóa nguồn ${competitor} — ${sku}`, 'success');
                } catch(e) { toast('Lỗi xóa: ' + e.message, 'error'); }
            }
        });
    }

    function exportSources() {
        const rows = [['SKU','Tên sản phẩm','Cửa hàng','URL','Giá gần nhất','Cập nhật cuối','Active']];
        _sourcesFiltered.forEach(s => rows.push([
            s.product_sku,
            s.products?.name || '',
            s.competitor,
            s.url,
            s._priceInfo?.price || '',
            s._priceInfo?.updated_at || '',
            s.active ? 'true' : 'false'
        ]));
        downloadCSV(rows, 'sources.csv');
    }

    // ====================================================================
    // TAB 2 — ANOMALIES
    // ====================================================================
    function detectAnomalies() {
        let totalIssues = 0;

        // 1. SKU nghi vấn
        const suspectSkus = _products.filter(p => {
            const s = String(p.sku || '');
            return s.length < 5 || /^\d+$/.test(s);
        });
        totalIssues += suspectSkus.length;
        const skuTbody = $('anomaly-sku-tbody');
        if (!suspectSkus.length) {
            skuTbody.innerHTML = '<tr><td colspan="6" class="text-center" style="color:var(--green)"><i class="bi bi-check-circle"></i> Không phát hiện SKU bất thường</td></tr>';
        } else {
            skuTbody.innerHTML = suspectSkus.map(p => {
                const reason = /^\d+$/.test(String(p.sku)) ? '⚠️ SKU chỉ là số' : '⚠️ SKU quá ngắn';
                return `<tr class="anomaly-row">
                    <td class="sku-suspect">${esc(p.sku)}</td>
                    <td style="font-size:0.88rem">${esc(p.name||'—')}</td>
                    <td>${esc(p.category||'—')}</td>
                    <td>${esc(p.brand||'—')}</td>
                    <td><span class="anomaly-badge"><i class="bi bi-exclamation-triangle"></i> ${reason}</span></td>
                    <td><a href="product.php?sku=${esc(p.sku)}" class="btn-ghost"><i class="bi bi-search"></i> Xem SP</a></td>
                </tr>`;
            }).join('');
        }

        // 2. Giá bất thường (từ latest_prices_cache)
        const badPrices = _latestPrices.filter(r => r.price === 0 || r.price < 0 || r.price > 200000000);
        totalIssues += badPrices.length;
        const priceTbody = $('anomaly-price-tbody');
        if (!badPrices.length) {
            priceTbody.innerHTML = '<tr><td colspan="6" class="text-center" style="color:var(--green)"><i class="bi bi-check-circle"></i> Không phát hiện giá bất thường</td></tr>';
        } else {
            const prodMap = {};
            _products.forEach(p => prodMap[p.sku] = p);
            priceTbody.innerHTML = badPrices.map(r => {
                const prod = prodMap[r.sku];
                const reason = r.price === 0 ? '🔴 Giá = 0đ' : r.price < 0 ? '🔴 Giá âm' : '🟡 Giá > 200 triệu';
                return `<tr class="anomaly-row">
                    <td><a href="product.php?sku=${esc(r.sku)}" class="btn-ghost" style="font-family:'Exo 2',monospace;font-size:0.8rem">${esc(r.sku)}</a></td>
                    <td style="font-size:0.85rem">${esc(prod?.name||'—')}</td>
                    <td><span class="badge badge-neutral">${esc(r.competitor)}</span></td>
                    <td style="font-weight:700;color:var(--red)">${fmt(r.price)}</td>
                    <td style="font-size:0.82rem;color:var(--text-muted)">${timeAgo(r.updated_at)}</td>
                    <td>
                        <div class="action-cell">
                            <button class="btn-danger" onclick="DM.deleteSource('${esc(r.sku)}','${esc(r.competitor)}','${esc(prod?.name||r.sku)}')">
                                <i class="bi bi-trash"></i> Xóa nguồn
                            </button>
                        </div>
                    </td>
                </tr>`;
            }).join('');
        }

        // 3. Sản phẩm không có nguồn
        const sourceSkus = new Set(_sources.map(s => s.product_sku));
        const noSrc = _products.filter(p => !sourceSkus.has(p.sku));
        totalIssues += noSrc.length;
        const nosrcTbody = $('anomaly-nosrc-tbody');
        if (!noSrc.length) {
            nosrcTbody.innerHTML = '<tr><td colspan="4" class="text-center" style="color:var(--green)"><i class="bi bi-check-circle"></i> Tất cả sản phẩm đều có nguồn cào</td></tr>';
        } else {
            nosrcTbody.innerHTML = noSrc.map(p => `<tr>
                <td><a href="product.php?sku=${esc(p.sku)}" class="btn-ghost" style="font-family:'Exo 2',monospace;font-size:0.8rem">${esc(p.sku)}</a></td>
                <td style="font-size:0.88rem">${esc(p.name||'—')}</td>
                <td>${esc(p.category||'—')}</td>
                <td>${esc(p.brand||'—')}</td>
            </tr>`).join('');
        }

        // Update badge
        $('tab-count-anomalies').textContent = totalIssues;
        if (totalIssues > 0) {
            $('anomaly-header-badge').style.display = '';
            $('anomaly-count-hdr').textContent = totalIssues;
        }
    }

    // ====================================================================
    // TAB 3 — PRODUCTS
    // ====================================================================
    async function loadProducts() {
        $('products-tbody').innerHTML = '<tr class="loading-row"><td colspan="7"><span class="spinner"></span> Đang tải...</td></tr>';
        try {
            const [prodData, lpData] = await Promise.all([
                supabaseFetch('products', 'select=sku,name,brand,category&order=name'),
                supabaseFetch('latest_prices_cache', 'select=sku,competitor,price,is_self')
            ]);
            _products = prodData;
            _latestPrices = lpData;

            // Build price & source count maps
            const selfPriceMap = {};
            const srcCountMap  = {};
            lpData.forEach(r => {
                if (r.is_self) selfPriceMap[r.sku] = r.price;
                srcCountMap[r.sku] = (srcCountMap[r.sku] || 0) + 1;
            });
            _products.forEach(p => {
                p._selfPrice  = selfPriceMap[p.sku] ?? null;
                p._srcCount   = srcCountMap[p.sku]  ?? 0;
            });

            // Fill filters
            const cats   = [...new Set(_products.map(p=>p.category).filter(Boolean))].sort();
            const brands = [...new Set(_products.map(p=>p.brand).filter(Boolean))].sort();
            $('prod-filter-cat').innerHTML   = '<option value="">Tất cả danh mục</option>' + cats.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
            $('prod-filter-brand').innerHTML = '<option value="">Tất cả thương hiệu</option>' + brands.map(b=>`<option value="${esc(b)}">${esc(b)}</option>`).join('');

            $('tab-count-products').textContent = _products.length;
            $('products-meta').textContent = `${_products.length} sản phẩm`;

            // Also fill history store dropdown from sources
            const histStores = [...new Set(_sources.map(s=>s.competitor))].sort();
            $('hist-store').innerHTML = '<option value="">Tất cả cửa hàng</option>' + histStores.map(s=>`<option value="${esc(s)}">${esc(s)}</option>`).join('');

            filterProducts();
            detectAnomalies();
        } catch(e) {
            $('products-tbody').innerHTML = `<tr><td colspan="7" class="text-center" style="color:var(--red)">Lỗi: ${esc(e.message)}</td></tr>`;
        }
    }

    function filterProducts() {
        const q  = $('prod-search').value.toLowerCase();
        const ca = $('prod-filter-cat').value;
        const br = $('prod-filter-brand').value;
        _productsFiltered = _products.filter(p => {
            const matchQ  = !q || (p.sku||'').toLowerCase().includes(q) || (p.name||'').toLowerCase().includes(q) || (p.category||'').toLowerCase().includes(q) || (p.brand||'').toLowerCase().includes(q);
            const matchCa = !ca || p.category === ca;
            const matchBr = !br || p.brand === br;
            return matchQ && matchCa && matchBr;
        });
        renderProducts();
    }

    function renderProducts() {
        const tbody = $('products-tbody');
        if (!_productsFiltered.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">Không tìm thấy sản phẩm</td></tr>'; return;
        }
        const isSuspect = p => String(p.sku||'').length < 5 || /^\d+$/.test(String(p.sku||''));
        tbody.innerHTML = _productsFiltered.map(p => {
            const skuClass = isSuspect(p) ? 'sku-suspect' : '';
            const suspect  = isSuspect(p) ? `<span class="anomaly-badge" style="margin-left:0.4rem"><i class="bi bi-exclamation-triangle"></i> SKU nghi vấn</span>` : '';
            const srcBadge = p._srcCount > 0
                ? `<span class="badge badge-green">${p._srcCount} nguồn</span>`
                : `<span class="badge badge-red">Không có nguồn</span>`;
            return `<tr>
                <td>
                    <div id="sku-view-${esc(p.sku)}" style="display:flex;align-items:center;gap:0.35rem">
                        <span class="${skuClass}" style="font-family:'Exo 2',monospace;font-size:0.85rem">${esc(p.sku)}</span>
                        ${suspect}
                    </div>
                </td>
                <td style="max-width:280px">
                    <div id="name-view-${esc(p.sku)}" style="display:flex;align-items:center;gap:0.35rem">
                        <span style="font-size:0.88rem">${esc(p.name||'—')}</span>
                        <button class="icon-btn icon-btn-edit" onclick="DM.startEditName('${esc(p.sku)}','${esc(p.name||'')}')" title="Sửa tên"><i class="bi bi-pencil"></i></button>
                    </div>
                    <div id="name-edit-${esc(p.sku)}" style="display:none;gap:0.4rem;align-items:center">
                        <input class="inline-input" id="name-input-${esc(p.sku)}" value="${esc(p.name||'')}">
                        <button class="icon-btn icon-btn-save" onclick="DM.saveName('${esc(p.sku)}')"><i class="bi bi-check-lg"></i></button>
                        <button class="icon-btn icon-btn-cancel" onclick="DM.cancelEditName('${esc(p.sku)}')"><i class="bi bi-x-lg"></i></button>
                    </div>
                </td>
                <td style="font-size:0.85rem">${esc(p.category||'—')}</td>
                <td style="font-size:0.85rem">${esc(p.brand||'—')}</td>
                <td style="white-space:nowrap;font-weight:600">${p._selfPrice ? fmt(p._selfPrice) : '<span style="color:var(--text-muted)">—</span>'}</td>
                <td>${srcBadge}</td>
                <td>
                    <div class="action-cell">
                        <a href="product.php?sku=${esc(p.sku)}" class="btn-ghost"><i class="bi bi-search"></i> Xem</a>
                        <button class="btn-danger" onclick="DM.deleteProduct('${esc(p.sku)}','${esc(p.name||p.sku)}')"><i class="bi bi-trash"></i></button>
                    </div>
                </td>
            </tr>`;
        }).join('');
    }

    function startEditName(sku, currentName) {
        document.getElementById(`name-view-${sku}`).style.display = 'none';
        const ed = document.getElementById(`name-edit-${sku}`);
        ed.style.display = 'flex';
        document.getElementById(`name-input-${sku}`).focus();
    }
    function cancelEditName(sku) {
        document.getElementById(`name-view-${sku}`).style.display = 'flex';
        document.getElementById(`name-edit-${sku}`).style.display = 'none';
    }
    async function saveName(sku) {
        const newName = document.getElementById(`name-input-${sku}`).value.trim();
        if (!newName) { toast('Tên không được để trống', 'error'); return; }
        try {
            await sbPatch('products', { sku }, { name: newName });
            const prod = _products.find(p => p.sku === sku);
            if (prod) prod.name = newName;
            cancelEditName(sku);
            filterProducts();
            toast(`Đã cập nhật tên sản phẩm ${sku}`, 'success');
        } catch(e) { toast('Lỗi cập nhật: ' + e.message, 'error'); }
    }

    function deleteProduct(sku, name) {
        showModal({
            title: '<i class="bi bi-trash"></i> Xóa sản phẩm',
            body: `Xóa hoàn toàn sản phẩm:<br><strong>${esc(name)}</strong> (SKU: <code>${esc(sku)}</code>)?`,
            warn: '⚠️ Xóa sản phẩm sẽ đồng thời xóa toàn bộ nguồn cào và lịch sử giá liên quan. Không thể hoàn tác.',
            confirmText: 'Xóa sản phẩm',
            onConfirm: async () => {
                try {
                    await sbDelete('price_history', { product_sku: sku });
                    await sbDelete('sources', { product_sku: sku });
                    await sbDelete('products', { sku });
                    _products = _products.filter(p => p.sku !== sku);
                    _sources  = _sources.filter(s => s.product_sku !== sku);
                    $('tab-count-products').textContent = _products.length;
                    $('tab-count-sources').textContent  = _sources.length;
                    filterProducts();
                    filterSources();
                    detectAnomalies();
                    toast(`Đã xóa sản phẩm ${sku}`, 'success');
                } catch(e) { toast('Lỗi xóa: ' + e.message, 'error'); }
            }
        });
    }

    function exportProducts() {
        const rows = [['SKU','Tên','Danh mục','Thương hiệu','Giá TNC','Số nguồn']];
        _productsFiltered.forEach(p => rows.push([p.sku, p.name||'', p.category||'', p.brand||'', p._selfPrice||'', p._srcCount]));
        downloadCSV(rows, 'products.csv');
    }

    // ====================================================================
    // TAB 4 — HISTORY
    // ====================================================================
    let _histSuggestList = [];
    function histSuggest(q) {
        const box = $('hist-suggest-box');
        if (!q || q.length < 2) { box.style.display = 'none'; return; }
        const matches = _products.filter(p =>
            p.sku.toLowerCase().includes(q.toLowerCase()) ||
            (p.name||'').toLowerCase().includes(q.toLowerCase())
        ).slice(0, 10);
        if (!matches.length) { box.style.display = 'none'; return; }
        box.style.display = '';
        box.innerHTML = matches.map(p => `
            <div style="padding:0.6rem 1rem;cursor:pointer;font-size:0.85rem;border-bottom:1px solid rgba(0,0,0,0.04)"
                 onmousedown="DM.selectHistSku('${esc(p.sku)}','${esc(p.name||p.sku)}')"
                 onmouseover="this.style.background='var(--accent-light)'" onmouseout="this.style.background=''">
                <div style="font-weight:700;color:var(--accent)">${esc(p.sku)}</div>
                <div style="color:var(--text-muted);font-size:0.8rem">${esc(p.name||'')}</div>
            </div>`).join('');
    }
    function selectHistSku(sku, name) {
        _histSkuSelected = sku;
        $('hist-sku-input').value = `${sku} — ${name}`;
        $('hist-suggest-box').style.display = 'none';
        loadHistory();
    }

    async function loadHistory() {
        if (!_histSkuSelected) { toast('Hãy chọn một sản phẩm từ gợi ý', 'warn'); return; }
        const store = $('hist-store').value;
        const days  = parseInt($('hist-days').value) || 30;
        const since = new Date(Date.now() - days * 86400000).toISOString();
        const tbody = $('history-tbody');
        tbody.innerHTML = '<tr class="loading-row"><td colspan="5"><span class="spinner"></span> Đang tải...</td></tr>';
        try {
            let q = `product_sku=eq.${encodeURIComponent(_histSkuSelected)}&scraped_at=gte.${encodeURIComponent(since)}&order=scraped_at.desc&select=competitor,price,in_stock,scraped_at,id`;
            if (store) q += `&competitor=eq.${encodeURIComponent(store)}`;
            const data = await supabaseFetch('price_history', q);
            if (!data.length) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center">Không có dữ liệu trong khoảng thời gian này</td></tr>';
                $('history-meta').textContent = ''; return;
            }
            $('history-meta').textContent = `${data.length} bản ghi trong ${days} ngày`;
            tbody.innerHTML = data.map(r => `<tr>
                <td><span class="badge badge-neutral">${esc(r.competitor)}</span></td>
                <td style="font-weight:700">${fmt(r.price)}</td>
                <td>${r.in_stock ? '<span class="badge badge-green">Còn hàng</span>' : '<span class="badge badge-red">Hết hàng</span>'}</td>
                <td style="font-size:0.82rem;color:var(--text-muted)">${new Date(r.scraped_at).toLocaleString('vi-VN')}</td>
                <td>
                    <button class="btn-danger" onclick="DM.deleteHistoryRow('${esc(r.id)}')"><i class="bi bi-trash"></i></button>
                </td>
            </tr>`).join('');
        } catch(e) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center" style="color:var(--red)">Lỗi: ${esc(e.message)}</td></tr>`;
        }
    }

    function deleteHistoryRow(id) {
        showModal({
            title: '<i class="bi bi-trash"></i> Xóa bản ghi lịch sử',
            body: 'Xóa bản ghi giá này khỏi lịch sử?',
            confirmText: 'Xóa',
            onConfirm: async () => {
                try {
                    const url = `${SUPABASE_URL}/rest/v1/price_history?id=eq.${encodeURIComponent(id)}`;
                    const res = await fetch(url, { method: 'DELETE', headers: { ...headers, 'Prefer': 'return=minimal' } });
                    if (!res.ok) throw new Error(await res.text());
                    loadHistory();
                    toast('Đã xóa bản ghi', 'success');
                } catch(e) { toast('Lỗi: ' + e.message, 'error'); }
            }
        });
    }

    // ====================================================================
    // EXPORT CSV
    // ====================================================================
    function downloadCSV(rows, filename) {
        const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g,'""')}"`).join(',')).join('\n');
        const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
    }

    // ====================================================================
    // INIT
    // ====================================================================
    async function refreshAll() {
        await loadSources();
        await loadProducts();
    }

    async function init() {
        await refreshAll();
        window.hideLoader();
    }

    // Public API
    return {
        switchTab, closeModal, refreshAll, init,
        filterSources, filterProducts,
        startEditUrl, cancelEditUrl, saveUrl,
        toggleActive, deleteSource, exportSources,
        startEditName, cancelEditName, saveName,
        deleteProduct, exportProducts,
        histSuggest, selectHistSku, loadHistory, deleteHistoryRow
    };
})();

document.addEventListener('DOMContentLoaded', () => DM.init());

// =====================================================================
// data-manager.js — Logic quản lý dữ liệu (Sources, Anomalies, Products, History)
// Action Dropdown Menu (3 Dots) + Form Modal Popup + Phân Trang Tối Ưu
// =====================================================================

const DM = (() => {
    // ── State ────────────────────────────────────────────────────────
    let _sources    = [];   // raw list từ Supabase
    let _products   = [];   // raw products
    let _latestPrices = []; // latest_prices_cache
    let _sourcesFiltered = [];
    let _productsFiltered = [];
    let _historyFiltered  = [];
    let _histSkuSelected = '';
    let _modalCallback = null;
    let _editSaveCallback = null;

    // ── Pagination State ─────────────────────────────────────────────
    const _pageState = {
        sources: { current: 1, pageSize: 25 },
        products: { current: 1, pageSize: 25 },
        history:  { current: 1, pageSize: 25 }
    };

    // ── Helpers ──────────────────────────────────────────────────────
    const $ = id => document.getElementById(id);
    const fmt = v => v != null ? new Intl.NumberFormat('vi-VN').format(v) + ' ₫' : '—';
    const timeAgo = iso => {
        if (!iso) return '—';
        const d = Math.floor((Date.now() - new Date(iso)) / 1000);
        if (d < 60)  return `${d}s trước`;
        if (d < 60*60) return `${Math.floor(d/60)}p trước`;
        if (d < 86400) return `${Math.floor(d/3600)}h trước`;
        return `${Math.floor(d/86400)} ngày trước`;
    };
    const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

    // ── Action Menu Dropdown Toggle ──────────────────────────────────
    function closeAllActionMenus() {
        document.querySelectorAll('.action-dropdown-menu').forEach(m => m.style.display = 'none');
    }

    function toggleActionMenu(event, menuId) {
        event.stopPropagation();
        const menu = $(menuId);
        if (!menu) return;
        const isOpen = menu.style.display === 'flex';
        closeAllActionMenus();
        if (!isOpen) {
            menu.style.display = 'flex';
        }
    }

    // Auto close menus when clicking outside
    document.addEventListener('click', () => closeAllActionMenus());

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

    // ── Confirm Modal ────────────────────────────────────────────────
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

    // ── Form Edit Modal Popup ────────────────────────────────────────
    function openEditModal(titleHtml, bodyHtml, onSave) {
        closeAllActionMenus();
        $('edit-modal-title').innerHTML = titleHtml;
        $('edit-modal-body').innerHTML = bodyHtml;
        _editSaveCallback = onSave;
        $('edit-modal-save-btn').onclick = async () => {
            if (_editSaveCallback) {
                const ok = await _editSaveCallback();
                if (ok !== false) closeEditModal();
            }
        };
        $('dm-edit-modal-backdrop').style.display = 'flex';
    }
    function closeEditModal() { $('dm-edit-modal-backdrop').style.display = 'none'; }

    // ── Tab switching ────────────────────────────────────────────────
    function switchTab(name) {
        closeAllActionMenus();
        document.querySelectorAll('.dm-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.dm-panel').forEach(p => p.classList.remove('active'));
        document.getElementById(`tab-btn-${name}`).classList.add('active');
        document.getElementById(`panel-${name}`).classList.add('active');
    }

    // ── Supabase Write Proxy (PHP + service role key → bypass RLS) ─────────────
    async function _sbProxy(method, table, match, data) {
        const res = await fetch('api/supabase-proxy.php', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ method, table, match: match || {}, data: data || {} })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!json.success) throw new Error(json.error || 'Unknown proxy error');
        return json;
    }

    // ── Supabase PATCH helper ─────────────────────────────────────────
    async function sbPatch(table, match, data) {
        return _sbProxy('PATCH', table, match, data);
    }

    // ── Supabase DELETE helper ───────────────────────────────────────
    async function sbDelete(table, match) {
        return _sbProxy('DELETE', table, match, null);
    }

    // ── Supabase POST helper ─────────────────────────────────────────
    async function sbPost(table, data) {
        return _sbProxy('POST', table, null, data);
    }


    // ── Pagination Renderer Helper ───────────────────────────────────
    function renderPaginationUI(containerId, stateKey, totalItems) {
        const container = $(containerId);
        if (!container) return;
        if (totalItems <= 0) {
            container.innerHTML = '';
            return;
        }

        const state = _pageState[stateKey];
        const totalPages = Math.ceil(totalItems / state.pageSize);
        if (state.current > totalPages) state.current = Math.max(1, totalPages);

        const startItem = (state.current - 1) * state.pageSize + 1;
        const endItem   = Math.min(totalItems, state.current * state.pageSize);

        let pageBtns = '';
        let startP = Math.max(1, state.current - 2);
        let endP   = Math.min(totalPages, state.current + 2);

        if (startP > 1) {
            pageBtns += `<button class="page-btn" onclick="DM.setPage('${stateKey}', 1)">1</button>`;
            if (startP > 2) pageBtns += `<span style="color:var(--text-muted)">…</span>`;
        }
        for (let p = startP; p <= endP; p++) {
            pageBtns += `<button class="page-btn ${p === state.current ? 'active' : ''}" onclick="DM.setPage('${stateKey}', ${p})">${p}</button>`;
        }
        if (endP < totalPages) {
            if (endP < totalPages - 1) pageBtns += `<span style="color:var(--text-muted)">…</span>`;
            pageBtns += `<button class="page-btn" onclick="DM.setPage('${stateKey}', ${totalPages})">${totalPages}</button>`;
        }

        container.innerHTML = `
            <div class="page-info">
                Hiển thị <strong>${startItem} - ${endItem}</strong> / tổng <strong>${totalItems}</strong> dòng
            </div>
            <div class="pagination-controls">
                <select class="page-size-select" onchange="DM.setPageSize('${stateKey}', this.value)">
                    <option value="10" ${state.pageSize === 10 ? 'selected' : ''}>10 / trang</option>
                    <option value="25" ${state.pageSize === 25 ? 'selected' : ''}>25 / trang</option>
                    <option value="50" ${state.pageSize === 50 ? 'selected' : ''}>50 / trang</option>
                    <option value="100" ${state.pageSize === 100 ? 'selected' : ''}>100 / trang</option>
                </select>
                <button class="page-btn" ${state.current <= 1 ? 'disabled' : ''} onclick="DM.setPage('${stateKey}', ${state.current - 1})">
                    <i class="bi bi-chevron-left"></i> Trước
                </button>
                ${pageBtns}
                <button class="page-btn" ${state.current >= totalPages ? 'disabled' : ''} onclick="DM.setPage('${stateKey}', ${state.current + 1})">
                    Sau <i class="bi bi-chevron-right"></i>
                </button>
            </div>
        `;
    }

    function setPage(stateKey, pageNum) {
        closeAllActionMenus();
        _pageState[stateKey].current = pageNum;
        if (stateKey === 'sources') renderSources();
        else if (stateKey === 'products') renderProducts();
        else if (stateKey === 'history') renderHistoryUI();
    }

    function setPageSize(stateKey, newSize) {
        closeAllActionMenus();
        _pageState[stateKey].pageSize = parseInt(newSize) || 25;
        _pageState[stateKey].current = 1;
        if (stateKey === 'sources') renderSources();
        else if (stateKey === 'products') renderProducts();
        else if (stateKey === 'history') renderHistoryUI();
    }

    // ====================================================================
    // TAB 1 — SOURCES
    // ====================================================================
    async function loadSources() {
        $('sources-tbody').innerHTML = '<tr class="loading-row"><td colspan="8"><span class="spinner"></span> Đang tải...</td></tr>';
        try {
            const [srcData, lpData] = await Promise.all([
                supabaseFetch('sources', 'select=product_sku,competitor,url,active,products(name)&order=competitor,product_sku'),
                supabaseFetch('latest_prices_cache', 'select=sku,competitor,price,scraped_at')
            ]);
            _sources = srcData;

            const priceMap = {};
            lpData.forEach(r => { priceMap[`${r.sku}|||${r.competitor}`] = r; });
            _sources.forEach(s => { s._priceInfo = priceMap[`${s.product_sku}|||${s.competitor}`] || null; });

            const stores = [...new Set(_sources.map(s => s.competitor))].sort();
            const sf = $('src-filter-store');
            sf.innerHTML = '<option value="">Tất cả cửa hàng</option>' + stores.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');

            $('tab-count-sources').textContent = _sources.length;
            $('sources-meta').textContent = `${_sources.length} nguồn tổng cộng`;
            _pageState.sources.current = 1;
            filterSources();
        } catch(e) {
            $('sources-tbody').innerHTML = `<tr><td colspan="8" class="text-center" style="color:var(--red)"><i class="bi bi-x-circle"></i> Lỗi: ${esc(e.message)}</td></tr>`;
        }
    }

    function filterSources() {
        closeAllActionMenus();
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
        _pageState.sources.current = 1;
        renderSources();
    }

    function renderSources() {
        const tbody = $('sources-tbody');
        const total = _sourcesFiltered.length;
        if (!total) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center">Không tìm thấy nguồn nào</td></tr>';
            renderPaginationUI('sources-pagination', 'sources', 0);
            return;
        }

        const state = _pageState.sources;
        const start = (state.current - 1) * state.pageSize;
        const pageItems = _sourcesFiltered.slice(start, start + state.pageSize);

        tbody.innerHTML = pageItems.map(s => {
            const name = esc(s.products?.name || '—');
            const price = s._priceInfo ? fmt(s._priceInfo.price) : '—';
            const updAt = s._priceInfo ? timeAgo(s._priceInfo.scraped_at) : '—';
            const skuKey = `${s.product_sku}_${s.competitor}`.replace(/[^a-zA-Z0-9]/g, '_');

            return `<tr>
                <td><a href="product.php?sku=${esc(s.product_sku)}" class="btn-ghost" style="font-family:'Exo 2',monospace;font-size:0.8rem">${esc(s.product_sku)}</a></td>
                <td style="max-width:220px;font-size:0.85rem">${name}</td>
                <td><span class="badge badge-neutral">${esc(s.competitor)}</span></td>
                <td class="url-cell">
                    <a href="${esc(s.url)}" target="_blank" title="${esc(s.url)}">${esc(s.url)}</a>
                </td>
                <td style="white-space:nowrap;font-weight:700">${price}</td>
                <td style="white-space:nowrap;color:var(--text-muted);font-size:0.82rem">${updAt}</td>
                <td style="text-align:center">
                    <input type="checkbox" class="toggle" ${s.active ? 'checked' : ''} onchange="DM.toggleActive('${esc(s.product_sku)}','${esc(s.competitor)}',this.checked)" title="${s.active ? 'Đang bật — click để tắt' : 'Đang tắt — click để bật'}">
                </td>
                <td style="text-align:center">
                    <div class="action-dropdown-wrap">
                        <button class="action-menu-btn" onclick="DM.toggleActionMenu(event, 'act_src_${skuKey}')" title="Tùy chọn">
                            <i class="bi bi-three-dots-vertical"></i>
                        </button>
                        <div id="act_src_${skuKey}" class="action-dropdown-menu" style="display:none">
                            <button onclick="DM.openEditSourceModal('${esc(s.product_sku)}','${esc(s.competitor)}')">
                                <i class="bi bi-pencil" style="color:var(--accent)"></i> Chỉnh sửa
                            </button>
                            <a href="${esc(s.url)}" target="_blank">
                                <i class="bi bi-box-arrow-up-right" style="color:var(--gold)"></i> Mở website
                            </a>
                            <button onclick="DM.deleteSource('${esc(s.product_sku)}','${esc(s.competitor)}','${esc(s.products?.name||s.product_sku)}')" style="color:var(--red)">
                                <i class="bi bi-trash"></i> Xóa nguồn
                            </button>
                        </div>
                    </div>
                </td>
            </tr>`;
        }).join('');

        renderPaginationUI('sources-pagination', 'sources', total);
    }

    // Modal Popup chỉnh sửa Nguồn cào giá
    function openEditSourceModal(sku, competitor) {
        const src = _sources.find(s => s.product_sku === sku && s.competitor === competitor);
        if (!src) return;

        const titleHtml = `<i class="bi bi-link-45deg"></i> Chỉnh Sửa Nguồn Cào Giá`;
        const bodyHtml = `
            <div class="modal-form-group">
                <label>Sản phẩm (SKU & Tên)</label>
                <input class="modal-form-input" value="[${esc(sku)}] ${esc(src.products?.name || '')}" readonly>
            </div>
            <div class="modal-form-group">
                <label>Cửa hàng đối thủ</label>
                <input class="modal-form-input" value="${esc(competitor)}" readonly>
            </div>
            <div class="modal-form-group">
                <label>Đường dẫn URL cào giá (*)</label>
                <div style="display:flex;gap:0.5rem;align-items:flex-start">
                    <textarea class="modal-form-input" id="edit-src-url" rows="3" style="font-family:monospace;font-size:0.83rem;flex:1">${esc(src.url)}</textarea>
                    <button type="button" class="btn-primary" onclick="DM.crawlSingleUrl('${esc(sku)}', '${esc(competitor)}')" style="padding:0.6rem 0.8rem;white-space:nowrap">
                        <i class="bi bi-cloud-download"></i> Lấy giá ngay
                    </button>
                </div>
            </div>
            <div class="modal-form-group">
                <label style="display:flex;align-items:center;gap:0.6rem;cursor:pointer;margin-top:0.2rem">
                    <input type="checkbox" class="toggle" id="edit-src-active" ${src.active ? 'checked' : ''}>
                    <span>Kích hoạt cào giá (Active)</span>
                </label>
            </div>
        `;

        openEditModal(titleHtml, bodyHtml, async () => {
            const newUrl = $('edit-src-url').value.trim();
            const isActive = $('edit-src-active').checked;
            if (!newUrl) { toast('URL không được để trống', 'error'); return false; }
            try {
                await sbPatch('sources', { product_sku: sku, competitor }, { url: newUrl, active: isActive });
                src.url = newUrl;
                src.active = isActive;
                renderSources();
                toast(`Đã cập nhật nguồn ${competitor} cho SKU ${sku}`, 'success');
                return true;
            } catch(e) {
                toast('Lỗi cập nhật: ' + e.message, 'error');
                return false;
            }
        });
    }

    async function crawlSingleUrl(sku, competitor) {
        const url = $('edit-src-url').value.trim();
        if (!url) { toast('URL không được để trống', 'error'); return; }

        toast('Đang cào dữ liệu từ URL...', 'info');
        try {
            // Gọi API PHP (PHP sẽ cào giá và cập nhật thẳng vào Supabase bằng Service Role Key để qua mặt RLS)
            const apiUrl = `api/crawl-url.php?url=${encodeURIComponent(url)}&sku=${encodeURIComponent(sku)}&competitor=${encodeURIComponent(competitor)}`;
            const res = await fetch(apiUrl);
            if (!res.ok) throw new Error('API request failed');
            const data = await res.json();
            
            if (!data.success) {
                toast(data.error || 'Lỗi không xác định khi cào giá', 'error');
                return;
            }

            const price = data.price;
            
            // Cập nhật URL mới vào sources nếu có thay đổi (Dùng anon key update bảng sources, vì RLS của sources cho phép UPDATE)
            await sbPatch('sources', { product_sku: sku, competitor: competitor }, { url: url });
            
            // Cập nhật lại cache (chỉ trên giao diện)
            const src = _sources.find(s => s.product_sku === sku && s.competitor === competitor);
            if (src) {
                src._priceInfo = { price: price, scraped_at: new Date().toISOString() };
                src.url = url;
            }
            renderSources();

            toast(`✅ Đã lấy được giá: ${fmt(price)} đ`, 'success');
        } catch (e) {
            toast('Lỗi khi cào dữ liệu: ' + e.message, 'error');
        }
    }

    async function toggleActive(sku, competitor, active) {
        try {
            await sbPatch('sources', { product_sku: sku, competitor }, { active });
            const src = _sources.find(s => s.product_sku === sku && s.competitor === competitor);
            if (src) src.active = active;
            toast(`${active ? '✅ Đã bật' : '❌ Đã tắt'} nguồn ${competitor} — ${sku}`, active ? 'success' : 'warn');
        } catch(e) {
            toast('Lỗi cập nhật: ' + e.message, 'error');
            renderSources();
        }
    }

    function deleteSource(sku, competitor, productName) {
        closeAllActionMenus();
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
            s._priceInfo?.scraped_at || '',
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

        // 2. Giá bất thường
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
                    <td style="font-size:0.82rem;color:var(--text-muted)">${timeAgo(r.scraped_at)}</td>
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
                supabaseFetch('latest_prices_cache', 'select=sku,competitor,price,is_self,scraped_at')
            ]);
            _products = prodData;
            _latestPrices = lpData;

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

            const cats   = [...new Set(_products.map(p=>p.category).filter(Boolean))].sort();
            const brands = [...new Set(_products.map(p=>p.brand).filter(Boolean))].sort();
            $('prod-filter-cat').innerHTML   = '<option value="">Tất cả danh mục</option>' + cats.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
            $('prod-filter-brand').innerHTML = '<option value="">Tất cả thương hiệu</option>' + brands.map(b=>`<option value="${esc(b)}">${esc(b)}</option>`).join('');

            $('tab-count-products').textContent = _products.length;
            $('products-meta').textContent = `${_products.length} sản phẩm`;

            const histStores = [...new Set(_sources.map(s=>s.competitor))].sort();
            $('hist-store').innerHTML = '<option value="">Tất cả cửa hàng</option>' + histStores.map(s=>`<option value="${esc(s)}">${esc(s)}</option>`).join('');

            _pageState.products.current = 1;
            filterProducts();
            detectAnomalies();
        } catch(e) {
            $('products-tbody').innerHTML = `<tr><td colspan="7" class="text-center" style="color:var(--red)">Lỗi: ${esc(e.message)}</td></tr>`;
        }
    }

    function filterProducts() {
        closeAllActionMenus();
        const q  = $('prod-search').value.toLowerCase();
        const ca = $('prod-filter-cat').value;
        const br = $('prod-filter-brand').value;
        _productsFiltered = _products.filter(p => {
            const matchQ  = !q || (p.sku||'').toLowerCase().includes(q) || (p.name||'').toLowerCase().includes(q) || (p.category||'').toLowerCase().includes(q) || (p.brand||'').toLowerCase().includes(q);
            const matchCa = !ca || p.category === ca;
            const matchBr = !br || p.brand === br;
            return matchQ && matchCa && matchBr;
        });
        _pageState.products.current = 1;
        renderProducts();
    }

    function renderProducts() {
        const tbody = $('products-tbody');
        const total = _productsFiltered.length;
        if (!total) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">Không tìm thấy sản phẩm</td></tr>';
            renderPaginationUI('products-pagination', 'products', 0);
            return;
        }

        const state = _pageState.products;
        const start = (state.current - 1) * state.pageSize;
        const pageItems = _productsFiltered.slice(start, start + state.pageSize);

        const isSuspect = p => String(p.sku||'').length < 5 || /^\d+$/.test(String(p.sku||''));
        tbody.innerHTML = pageItems.map(p => {
            const skuClass = isSuspect(p) ? 'sku-suspect' : '';
            const suspect  = isSuspect(p) ? `<span class="anomaly-badge" style="margin-left:0.4rem"><i class="bi bi-exclamation-triangle"></i> SKU nghi vấn</span>` : '';
            const srcBadge = p._srcCount > 0
                ? `<span class="badge badge-green">${p._srcCount} nguồn</span>`
                : `<span class="badge badge-red">Không có nguồn</span>`;
            const skuKey   = p.sku.replace(/[^a-zA-Z0-9]/g, '_');

            return `<tr>
                <td>
                    <div style="display:flex;align-items:center;gap:0.35rem">
                        <span class="${skuClass}" style="font-family:'Exo 2',monospace;font-size:0.85rem">${esc(p.sku)}</span>
                        ${suspect}
                    </div>
                </td>
                <td style="max-width:280px;font-size:0.88rem">${esc(p.name||'—')}</td>
                <td style="font-size:0.85rem">${esc(p.category||'—')}</td>
                <td style="font-size:0.85rem">${esc(p.brand||'—')}</td>
                <td style="white-space:nowrap;font-weight:700">${p._selfPrice ? fmt(p._selfPrice) : '<span style="color:var(--text-muted)">—</span>'}</td>
                <td>${srcBadge}</td>
                <td style="text-align:center">
                    <div class="action-dropdown-wrap">
                        <button class="action-menu-btn" onclick="DM.toggleActionMenu(event, 'act_prod_${skuKey}')" title="Tùy chọn">
                            <i class="bi bi-three-dots-vertical"></i>
                        </button>
                        <div id="act_prod_${skuKey}" class="action-dropdown-menu" style="display:none">
                            <button onclick="DM.openEditProductModal('${esc(p.sku)}')">
                                <i class="bi bi-pencil" style="color:var(--accent)"></i> Chỉnh sửa
                            </button>
                            <a href="product.php?sku=${esc(p.sku)}">
                                <i class="bi bi-search" style="color:var(--gold)"></i> Xem chi tiết
                            </a>
                            <button onclick="DM.deleteProduct('${esc(p.sku)}','${esc(p.name||p.sku)}')" style="color:var(--red)">
                                <i class="bi bi-trash"></i> Xóa sản phẩm
                            </button>
                        </div>
                    </div>
                </td>
            </tr>`;
        }).join('');

        renderPaginationUI('products-pagination', 'products', total);
    }

    // Modal Popup chỉnh sửa Sản phẩm
    function openEditProductModal(sku) {
        const prod = _products.find(p => p.sku === sku);
        if (!prod) return;

        const titleHtml = `<i class="bi bi-box-seam"></i> Chỉnh Sửa Sản Phẩm`;
        const bodyHtml = `
            <div class="modal-form-group">
                <label>Mã SKU</label>
                <input class="modal-form-input" value="${esc(sku)}" readonly>
            </div>
            <div class="modal-form-group">
                <label>Tên sản phẩm (*)</label>
                <input class="modal-form-input" id="edit-prod-name" value="${esc(prod.name || '')}">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
                <div class="modal-form-group">
                    <label>Danh mục</label>
                    <input class="modal-form-input" id="edit-prod-cat" value="${esc(prod.category || '')}">
                </div>
                <div class="modal-form-group">
                    <label>Thương hiệu</label>
                    <input class="modal-form-input" id="edit-prod-brand" value="${esc(prod.brand || '')}">
                </div>
            </div>
        `;

        openEditModal(titleHtml, bodyHtml, async () => {
            const newName  = $('edit-prod-name').value.trim();
            const newCat   = $('edit-prod-cat').value.trim();
            const newBrand = $('edit-prod-brand').value.trim();
            if (!newName) { toast('Tên sản phẩm không được để trống', 'error'); return false; }
            try {
                await sbPatch('products', { sku }, { name: newName, category: newCat, brand: newBrand });
                prod.name = newName;
                prod.category = newCat;
                prod.brand = newBrand;
                renderProducts();
                toast(`Đã cập nhật sản phẩm SKU ${sku}`, 'success');
                return true;
            } catch(e) {
                toast('Lỗi cập nhật: ' + e.message, 'error');
                return false;
            }
        });
    }

    function deleteProduct(sku, name) {
        closeAllActionMenus();
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
            _historyFiltered = await supabaseFetch('price_history', q);
            _pageState.history.current = 1;
            renderHistoryUI();
        } catch(e) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center" style="color:var(--red)">Lỗi: ${esc(e.message)}</td></tr>`;
            renderPaginationUI('history-pagination', 'history', 0);
        }
    }

    function renderHistoryUI() {
        const tbody = $('history-tbody');
        const total = _historyFiltered.length;
        if (!total) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">Không có dữ liệu trong khoảng thời gian này</td></tr>';
            renderPaginationUI('history-pagination', 'history', 0);
            return;
        }

        const state = _pageState.history;
        const start = (state.current - 1) * state.pageSize;
        const pageItems = _historyFiltered.slice(start, start + state.pageSize);

        tbody.innerHTML = pageItems.map(r => `<tr>
            <td><span class="badge badge-neutral">${esc(r.competitor)}</span></td>
            <td style="font-weight:700">${fmt(r.price)}</td>
            <td>${r.in_stock ? '<span class="badge badge-green">Còn hàng</span>' : '<span class="badge badge-red">Hết hàng</span>'}</td>
            <td style="font-size:0.82rem;color:var(--text-muted)">${new Date(r.scraped_at).toLocaleString('vi-VN')}</td>
            <td>
                <button class="btn-danger" onclick="DM.deleteHistoryRow('${esc(r.id)}')"><i class="bi bi-trash"></i> Xóa</button>
            </td>
        </tr>`).join('');

        renderPaginationUI('history-pagination', 'history', total);
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
                    _historyFiltered = _historyFiltered.filter(r => String(r.id) !== String(id));
                    renderHistoryUI();
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
        switchTab, closeModal, closeEditModal, refreshAll, init,
        filterSources, filterProducts,
        openEditSourceModal, openEditProductModal, crawlSingleUrl,
        toggleActive, deleteSource, exportSources,
        deleteProduct, exportProducts,
        histSuggest, selectHistSku, loadHistory, deleteHistoryRow,
        setPage, setPageSize, toggleActionMenu
    };
})();

document.addEventListener('DOMContentLoaded', () => DM.init());

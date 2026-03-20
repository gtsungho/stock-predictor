// === Stock Predictor Frontend ===
const API_BASE = window.location.origin;
let allResults = [];
let ws = null;

document.addEventListener('DOMContentLoaded', () => {
    loadResults();
    connectWebSocket();
});

function connectWebSocket() {
    const wsUrl = API_BASE.replace('http', 'ws') + '/ws';
    try {
        ws = new WebSocket(wsUrl);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'progress') updateProgress(data);
        };
        ws.onclose = () => setTimeout(connectWebSocket, 3000);
    } catch (e) {}
}

// === 분석 시작 ===
async function startAnalysis() {
    const btn = document.getElementById('btn-analyze');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading-spinner"></span>스캔 중...';
    showProgress();

    try {
        const resp = await fetch(`${API_BASE}/api/analyze`, { method: 'POST' });
        if (resp.status === 401) return;
        const data = await resp.json();
        if (data.status === 'running') pollProgress();
    } catch (e) {
        alert('서버 연결 실패');
        btn.disabled = false;
        btn.textContent = '종목 스캔 시작';
    }
}

async function pollProgress() {
    const interval = setInterval(async () => {
        try {
            const resp = await fetch(`${API_BASE}/api/status`);
            if (resp.status === 401) return;
            const data = await resp.json();
            updateProgress(data);
            if (data.status === 'done' || data.status === 'error') {
                clearInterval(interval);
                if (data.status === 'done') await loadResults();
                const btn = document.getElementById('btn-analyze');
                btn.disabled = false;
                btn.textContent = '종목 스캔 시작';
                setTimeout(() => hideProgress(), 2000);
            }
        } catch (e) {}
    }, 2000);
}

function updateProgress(data) {
    document.getElementById('progress-fill').style.width = `${data.progress || 0}%`;
    document.getElementById('progress-text').textContent = data.message || '진행 중...';
}

function showProgress() { document.getElementById('progress-section').classList.remove('hidden'); }
function hideProgress() { document.getElementById('progress-section').classList.add('hidden'); }

// === 결과 로드 ===
async function loadResults() {
    try {
        const resp = await fetch(`${API_BASE}/api/results`);
        if (resp.status === 401) return;
        if (!resp.ok) return;
        const data = await resp.json();
        allResults = data.top_picks || [];

        document.getElementById('summary-section').classList.remove('hidden');
        document.getElementById('filter-section').classList.remove('hidden');
        document.getElementById('total-analyzed').textContent = data.analyzed_count || '-';
        document.getElementById('total-qualified').textContent = data.qualified_count || '-';
        document.getElementById('elapsed-time').textContent = data.elapsed_seconds ? `${data.elapsed_seconds}초` : '-';
        if (data.timestamp) {
            const d = new Date(data.timestamp);
            document.getElementById('last-update').textContent =
                `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`;
        }
        renderStockList(allResults);
        const btn = document.getElementById('btn-analyze');
        btn.disabled = false;
        btn.textContent = '종목 스캔 시작';
    } catch (e) {}
}

// === 종목 카드 렌더링 ===
function renderStockList(stocks) {
    const container = document.getElementById('stock-list');
    if (!stocks || stocks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>아직 분석 결과가 없습니다.</p>
                <p>"종목 스캔 시작" 버튼을 누르면</p>
                <p>AI가 자동으로 매수할 종목을 찾아줍니다.</p>
            </div>`;
        return;
    }
    container.innerHTML = stocks.map((s, i) => createStockCard(s, i)).join('');
}

function createStockCard(stock, index) {
    const info = stock.stock_info || {};
    const price = stock.price_info || {};
    const trade = stock.trade_plan || {};
    const scores = stock.scores || {};

    const changeClass = (price.change_pct || 0) >= 0 ? 'up' : 'down';
    const changeSign = (price.change_pct || 0) >= 0 ? '+' : '';

    return `
    <div class="stock-card grade-${stock.grade}" onclick="showDetail('${stock.ticker}')">
        <div class="card-rank">${stock.rank || index + 1}</div>

        <!-- 상단: 종목명 + 등급 -->
        <div class="card-top">
            <div>
                <div class="card-ticker">${stock.ticker}</div>
                <div class="card-name">${info.name || ''}</div>
            </div>
            <div>
                <div class="card-grade ${stock.grade}">${stock.grade}</div>
            </div>
        </div>

        <!-- 핵심: 매매 전략 -->
        <div class="trade-box">
            <div class="trade-row">
                <div class="trade-item">
                    <span class="trade-label">현재가</span>
                    <span class="trade-value">$${(price.current_price || 0).toFixed(2)}</span>
                    <span class="price-change ${changeClass}">${changeSign}${(price.change_pct || 0).toFixed(2)}%</span>
                </div>
                <div class="trade-item target">
                    <span class="trade-label">목표가 (5일)</span>
                    <span class="trade-value green">$${(trade.target_price_5d || 0).toFixed(2)}</span>
                    <span class="trade-pct green">+${(trade.target_pct_5d || 0).toFixed(1)}%</span>
                </div>
                <div class="trade-item stop">
                    <span class="trade-label">손절가</span>
                    <span class="trade-value red">$${(trade.stop_loss_price || 0).toFixed(2)}</span>
                    <span class="trade-pct red">-${(trade.stop_loss_pct || 0).toFixed(1)}%</span>
                </div>
            </div>
        </div>

        <!-- 전략 요약 -->
        <div class="strategy-row">
            <span class="strategy-badge">${trade.strategy || '-'}</span>
            <span class="strategy-badge">${trade.hold_period || '-'}</span>
            <span class="strategy-badge timing">${trade.timing || '-'}</span>
            <span class="strategy-badge rr">R/R ${(trade.rr_ratio || 0).toFixed(1)}</span>
        </div>

        <!-- 상승 확률 바 -->
        <div class="prob-row">
            <div class="prob-bar-group">
                <span class="prob-label">1일 상승</span>
                <div class="prob-bar-bg">
                    <div class="prob-bar-fill" style="width:${stock.rise_probability_1d}%;background:${probColor(stock.rise_probability_1d)}"></div>
                </div>
                <span class="prob-pct">${stock.rise_probability_1d.toFixed(0)}%</span>
            </div>
            <div class="prob-bar-group">
                <span class="prob-label">5일 상승</span>
                <div class="prob-bar-bg">
                    <div class="prob-bar-fill" style="width:${stock.rise_probability_5d}%;background:${probColor(stock.rise_probability_5d)}"></div>
                </div>
                <span class="prob-pct">${stock.rise_probability_5d.toFixed(0)}%</span>
            </div>
        </div>

        <!-- 추천 문구 -->
        <div class="card-recommendation">${stock.recommendation || ''}</div>
    </div>`;
}

function probColor(pct) {
    if (pct >= 65) return '#00e676';
    if (pct >= 50) return '#ffd740';
    return '#78909c';
}

// === 상세 모달 ===
async function showDetail(ticker) {
    const modal = document.getElementById('modal');
    const modalTicker = document.getElementById('modal-ticker');
    const modalBody = document.getElementById('modal-body');

    modalTicker.textContent = ticker;
    modalBody.innerHTML = '<div style="text-align:center;padding:40px"><span class="loading-spinner"></span> 분석 중...</div>';
    modal.classList.remove('hidden');

    let stock = allResults.find(s => s.ticker === ticker);
    if (!stock) {
        try {
            const resp = await fetch(`${API_BASE}/api/stock/${ticker}`);
            if (resp.ok) stock = await resp.json();
        } catch (e) {}
    }
    if (!stock) {
        modalBody.innerHTML = '<p>종목 정보를 찾을 수 없습니다.</p>';
        return;
    }

    modalTicker.textContent = `${ticker} - ${stock.stock_info?.name || ''}`;
    modalBody.innerHTML = renderDetail(stock);
}

function renderDetail(stock) {
    const scores = stock.scores || {};
    const details = stock.details || {};
    const price = stock.price_info || {};
    const trade = stock.trade_plan || {};

    const riskClass = stock.risk_level === '낮음' ? 'low' : stock.risk_level === '보통' ? 'medium' : 'high';
    const barColor = (s) => s >= 70 ? 'var(--green)' : s >= 50 ? 'var(--yellow)' : s >= 30 ? 'var(--orange)' : 'var(--red)';

    return `
    <!-- 종합 점수 + 등급 -->
    <div class="detail-section" style="text-align:center">
        <div class="card-grade ${stock.grade}" style="width:64px;height:64px;font-size:28px;margin:0 auto 8px">${stock.grade}</div>
        <div style="font-size:32px;font-weight:800;color:var(--accent)">${stock.final_score.toFixed(1)}점</div>
        <span class="risk-badge ${riskClass}">리스크: ${stock.risk_level}</span>
    </div>

    <!-- 매매 전략 (핵심) -->
    <div class="detail-section">
        <h3>매매 전략</h3>
        <div class="trade-detail-box">
            <div class="trade-detail-row main-row">
                <div class="td-item">
                    <div class="td-label">매수가 (진입)</div>
                    <div class="td-value">$${trade.entry_price || '-'}</div>
                </div>
                <div class="td-item">
                    <div class="td-label">지정가 매수</div>
                    <div class="td-value dim">$${trade.limit_price || '-'}</div>
                </div>
            </div>
            <div class="trade-detail-row">
                <div class="td-item green-bg">
                    <div class="td-label">목표가 (당일)</div>
                    <div class="td-value green">$${trade.target_price_1d || '-'}</div>
                    <div class="td-sub green">+${(trade.target_pct_1d || 0).toFixed(1)}% 도달시 매도</div>
                </div>
                <div class="td-item green-bg">
                    <div class="td-label">목표가 (5일)</div>
                    <div class="td-value green">$${trade.target_price_5d || '-'}</div>
                    <div class="td-sub green">+${(trade.target_pct_5d || 0).toFixed(1)}% 도달시 매도</div>
                </div>
            </div>
            <div class="trade-detail-row">
                <div class="td-item red-bg">
                    <div class="td-label">손절가</div>
                    <div class="td-value red">$${trade.stop_loss_price || '-'}</div>
                    <div class="td-sub red">-${(trade.stop_loss_pct || 0).toFixed(1)}% 하락시 매도</div>
                </div>
                <div class="td-item">
                    <div class="td-label">리워드/리스크</div>
                    <div class="td-value">${(trade.rr_ratio || 0).toFixed(1)}배</div>
                    <div class="td-sub">${(trade.rr_ratio || 0) >= 2 ? '양호' : (trade.rr_ratio || 0) >= 1.5 ? '보통' : '주의'}</div>
                </div>
            </div>
        </div>
    </div>

    <!-- 매매 가이드 -->
    <div class="detail-section">
        <h3>매매 가이드</h3>
        <div class="guide-box">
            <div class="guide-item"><span class="guide-label">전략</span><span class="guide-value">${trade.strategy || '-'}</span></div>
            <div class="guide-item"><span class="guide-label">보유 기간</span><span class="guide-value">${trade.hold_period || '-'}</span></div>
            <div class="guide-item"><span class="guide-label">매수 타이밍</span><span class="guide-value accent">${trade.timing || '-'}</span></div>
            <div class="guide-item"><span class="guide-label">일일 변동성</span><span class="guide-value">${(trade.daily_volatility || 0).toFixed(2)}%</span></div>
            <div class="guide-item"><span class="guide-label">지지선</span><span class="guide-value">$${trade.support || '-'}</span></div>
            <div class="guide-item"><span class="guide-label">저항선</span><span class="guide-value">$${trade.resistance || '-'}</span></div>
            ${trade.analyst_target ? `<div class="guide-item"><span class="guide-label">애널리스트 목표가</span><span class="guide-value green">$${trade.analyst_target}</span></div>` : ''}
        </div>
    </div>

    <!-- 상승 확률 -->
    <div class="detail-section">
        <h3>상승 확률</h3>
        <div class="detail-grid">
            <div class="detail-item">
                <div class="label">당일 (1일)</div>
                <div class="value" style="color:${probColor(stock.rise_probability_1d)}">${stock.rise_probability_1d.toFixed(1)}%</div>
            </div>
            <div class="detail-item">
                <div class="label">일주일 (5일)</div>
                <div class="value" style="color:${probColor(stock.rise_probability_5d)}">${stock.rise_probability_5d.toFixed(1)}%</div>
            </div>
        </div>
    </div>

    <!-- 분석 점수 -->
    <div class="detail-section">
        <h3>분석 점수</h3>
        ${Object.entries({'기술적 분석': scores.technical || 0, '모멘텀': scores.momentum || 0, '펀더멘털': scores.fundamental || 0, '머신러닝': scores.ml || 0}).map(([label, score]) => `
            <div class="score-bar-container">
                <div class="score-bar-label"><span>${label}</span><span>${score.toFixed(1)}</span></div>
                <div class="score-bar-bg"><div class="score-bar-fill" style="width:${score}%;background:${barColor(score)}"></div></div>
            </div>
        `).join('')}
    </div>

    <!-- 주요 지표 -->
    <div class="detail-section">
        <h3>주요 지표</h3>
        <div class="detail-grid">
            ${Object.entries(details).filter(([k]) =>
                ['RSI','MACD','ADX','Volume_Ratio_20D','Forward_PE','PEG','ROE',
                 'Revenue_Growth','ML_1d_prob','ML_5d_prob','Return_1D','Return_5D'].includes(k)
            ).map(([k, v]) => `
                <div class="detail-item"><div class="label">${formatLabel(k)}</div><div class="value">${typeof v === 'number' ? v.toFixed(2) : v}</div></div>
            `).join('')}
        </div>
    </div>

    <!-- 시그널 -->
    <div class="detail-section">
        <h3>분석 시그널</h3>
        <ul class="signal-list">${(stock.top_signals || []).map(s => `<li>${s}</li>`).join('')}</ul>
    </div>

    <!-- 추천 -->
    <div class="detail-section" style="text-align:center;padding:16px;background:rgba(0,212,255,0.1);border-radius:var(--radius)">
        <div style="font-size:14px;font-weight:700;color:var(--accent)">${stock.recommendation}</div>
    </div>

    <p style="text-align:center;font-size:10px;color:var(--text-secondary);margin-top:16px">
        * 이 분석은 참고용이며, 투자 결정의 책임은 본인에게 있습니다.
    </p>`;
}

function closeModal() { document.getElementById('modal').classList.add('hidden'); }

// === 필터/정렬 ===
function filterResults() {
    const grade = document.getElementById('filter-grade').value;
    const strategy = document.getElementById('filter-strategy').value;
    let filtered = [...allResults];
    if (grade !== 'all') filtered = filtered.filter(s => s.grade === grade);
    if (strategy !== 'all') filtered = filtered.filter(s => (s.trade_plan?.strategy || '') === strategy);
    renderStockList(filtered);
}

function sortResults() {
    const sortBy = document.getElementById('sort-by').value;
    let sorted = [...allResults];
    switch (sortBy) {
        case 'score': sorted.sort((a, b) => b.final_score - a.final_score); break;
        case 'target5d': sorted.sort((a, b) => (b.trade_plan?.target_pct_5d || 0) - (a.trade_plan?.target_pct_5d || 0)); break;
        case 'rr': sorted.sort((a, b) => (b.trade_plan?.rr_ratio || 0) - (a.trade_plan?.rr_ratio || 0)); break;
    }
    renderStockList(sorted);
}

// === 유틸 ===
function formatNumber(num) {
    if (!num) return '-';
    if (num >= 1e9) return (num / 1e9).toFixed(1) + 'B';
    if (num >= 1e6) return (num / 1e6).toFixed(1) + 'M';
    if (num >= 1e3) return (num / 1e3).toFixed(1) + 'K';
    return num.toLocaleString();
}

function formatLabel(key) {
    const labels = {
        'RSI': 'RSI', 'MACD': 'MACD', 'ADX': 'ADX', 'Volume_Ratio_20D': '거래량비율',
        'Forward_PE': 'Forward P/E', 'PEG': 'PEG', 'ROE': 'ROE',
        'Revenue_Growth': '매출성장률', 'ML_1d_prob': 'ML 1일확률', 'ML_5d_prob': 'ML 5일확률',
        'Return_1D': '1일수익률', 'Return_5D': '5일수익률',
    };
    return labels[key] || key;
}

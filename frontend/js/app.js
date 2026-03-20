// === Stock Predictor Frontend ===
const API_BASE = window.location.origin;
let tabData = {};
let currentTab = 'top20';
let ws = null;
let usdKrw = 0; // USD/KRW 환율

function krw(usd) {
    if (!usdKrw || !usd) return '';
    return `(₩${Math.round(usd * usdKrw).toLocaleString()})`;
}

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

        // 환율 저장
        if (data.usd_krw) usdKrw = data.usd_krw;

        // 탭 데이터 저장
        if (data.tabs) {
            tabData = data.tabs;
        } else {
            // 하위 호환
            tabData = { top20: { label: '종합 TOP', stocks: data.top_picks || [] } };
        }

        // 요약
        document.getElementById('summary-section').classList.remove('hidden');
        document.getElementById('tab-section').classList.remove('hidden');
        document.getElementById('total-analyzed').textContent = data.analyzed_count || '-';
        document.getElementById('elapsed-time').textContent = data.elapsed_seconds ? `${data.elapsed_seconds}초` : '-';
        if (data.timestamp) {
            const d = new Date(data.timestamp);
            document.getElementById('last-update').textContent =
                `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
        }

        // 탭 카운트 업데이트
        document.querySelectorAll('.tab').forEach(tab => {
            const key = tab.dataset.tab;
            if (tabData[key]) {
                const count = tabData[key].stocks ? tabData[key].stocks.length : 0;
                tab.textContent = `${tabData[key].label} (${count})`;
            }
        });

        switchTab(currentTab);

        const btn = document.getElementById('btn-analyze');
        btn.disabled = false;
        btn.textContent = '종목 스캔 시작';
    } catch (e) {}
}

// === 탭 전환 ===
function switchTab(tab) {
    currentTab = tab;

    // 탭 버튼 활성화
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab[data-tab="${tab}"]`).classList.add('active');

    // 해당 탭 데이터 렌더링
    const stocks = tabData[tab]?.stocks || [];
    renderStockList(stocks);
}

// === 종목 카드 렌더링 ===
function renderStockList(stocks) {
    const container = document.getElementById('stock-list');
    if (!stocks || stocks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>해당 카테고리에 종목이 없습니다.</p>
            </div>`;
        return;
    }
    container.innerHTML = stocks.map((s, i) => createStockCard(s, i)).join('');
}

function createStockCard(stock, index) {
    const info = stock.stock_info || {};
    const price = stock.price_info || {};
    const trade = stock.trade_plan || {};

    const changeClass = (price.change_pct || 0) >= 0 ? 'up' : 'down';
    const changeSign = (price.change_pct || 0) >= 0 ? '+' : '';

    return `
    <div class="stock-card grade-${stock.grade}" onclick="showDetail('${stock.ticker}')">
        <div class="card-rank">${stock.rank || index + 1}</div>

        <div class="card-top">
            <div>
                <div class="card-ticker">${stock.ticker}</div>
                <div class="card-name">${info.name || ''}</div>
            </div>
            <div class="card-grade ${stock.grade}">${stock.grade}</div>
        </div>

        <div class="trade-box">
            <div class="trade-row">
                <div class="trade-item">
                    <span class="trade-label">현재가</span>
                    <span class="trade-value">$${(price.current_price || 0).toFixed(2)}</span>
                    <span class="trade-krw">${krw(price.current_price)}</span>
                    <span class="price-change ${changeClass}">${changeSign}${(price.change_pct || 0).toFixed(2)}%</span>
                </div>
                <div class="trade-item target">
                    <span class="trade-label">목표가 (5일)</span>
                    <span class="trade-value green">$${(trade.target_price_5d || 0).toFixed(2)}</span>
                    <span class="trade-krw">${krw(trade.target_price_5d)}</span>
                    <span class="trade-pct green">+${(trade.target_pct_5d || 0).toFixed(1)}%</span>
                </div>
                <div class="trade-item stop">
                    <span class="trade-label">손절가</span>
                    <span class="trade-value red">$${(trade.stop_loss_price || 0).toFixed(2)}</span>
                    <span class="trade-krw">${krw(trade.stop_loss_price)}</span>
                    <span class="trade-pct red">-${(trade.stop_loss_pct || 0).toFixed(1)}%</span>
                </div>
            </div>
        </div>

        <div class="strategy-row">
            <span class="strategy-badge">${trade.strategy || '-'}</span>
            <span class="strategy-badge">${trade.hold_period || '-'}</span>
            <span class="strategy-badge timing">${trade.timing || '-'}</span>
            <span class="strategy-badge rr">R/R ${(trade.rr_ratio || 0).toFixed(1)}</span>
        </div>

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

    // 모든 탭에서 찾기
    let stock = null;
    for (const key in tabData) {
        const found = (tabData[key].stocks || []).find(s => s.ticker === ticker);
        if (found) { stock = found; break; }
    }

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
    if (stock.usd_krw) usdKrw = stock.usd_krw;

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
    <div class="detail-section" style="text-align:center">
        <div class="card-grade ${stock.grade}" style="width:64px;height:64px;font-size:28px;margin:0 auto 8px">${stock.grade}</div>
        <div style="font-size:32px;font-weight:800;color:var(--accent)">${stock.final_score.toFixed(1)}점</div>
        <span class="risk-badge ${riskClass}">리스크: ${stock.risk_level}</span>
    </div>

    <div class="detail-section">
        <h3>매매 전략</h3>
        <div class="trade-detail-box">
            <div class="trade-detail-row main-row">
                <div class="td-item">
                    <div class="td-label">매수가 (진입)</div>
                    <div class="td-value">$${trade.entry_price || '-'}</div>
                    <div class="td-sub">${krw(trade.entry_price)}</div>
                </div>
                <div class="td-item">
                    <div class="td-label">지정가 매수</div>
                    <div class="td-value dim">$${trade.limit_price || '-'}</div>
                    <div class="td-sub">${krw(trade.limit_price)}</div>
                </div>
            </div>
            <div class="trade-detail-row">
                <div class="td-item green-bg">
                    <div class="td-label">목표가 (당일)</div>
                    <div class="td-value green">$${trade.target_price_1d || '-'}</div>
                    <div class="td-sub green">${krw(trade.target_price_1d)}</div>
                    <div class="td-sub green">+${(trade.target_pct_1d || 0).toFixed(1)}% 도달시 매도</div>
                </div>
                <div class="td-item green-bg">
                    <div class="td-label">목표가 (5일)</div>
                    <div class="td-value green">$${trade.target_price_5d || '-'}</div>
                    <div class="td-sub green">${krw(trade.target_price_5d)}</div>
                    <div class="td-sub green">+${(trade.target_pct_5d || 0).toFixed(1)}% 도달시 매도</div>
                </div>
            </div>
            <div class="trade-detail-row">
                <div class="td-item red-bg">
                    <div class="td-label">손절가</div>
                    <div class="td-value red">$${trade.stop_loss_price || '-'}</div>
                    <div class="td-sub red">${krw(trade.stop_loss_price)}</div>
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

    <div class="detail-section">
        <h3>매매 가이드</h3>
        <div class="guide-box">
            <div class="guide-item"><span class="guide-label">전략</span><span class="guide-value">${trade.strategy || '-'}</span></div>
            <div class="guide-item"><span class="guide-label">보유 기간</span><span class="guide-value">${trade.hold_period || '-'}</span></div>
            <div class="guide-item"><span class="guide-label">매수 타이밍</span><span class="guide-value accent">${trade.timing || '-'}</span></div>
            <div class="guide-item"><span class="guide-label">일일 변동성</span><span class="guide-value">${(trade.daily_volatility || 0).toFixed(2)}%</span></div>
            <div class="guide-item"><span class="guide-label">지지선</span><span class="guide-value">$${trade.support || '-'}</span></div>
            <div class="guide-item"><span class="guide-label">저항선</span><span class="guide-value">$${trade.resistance || '-'}</span></div>
            ${trade.analyst_target ? `<div class="guide-item"><span class="guide-label">애널리스트 목표가</span><span class="guide-value green">$${trade.analyst_target} ${krw(trade.analyst_target)}</span></div>` : ''}
            ${renderMarketEvents(stock)}
        </div>
    </div>

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

    <div class="detail-section">
        <h3>분석 점수</h3>
        ${Object.entries({'기술적 분석': scores.technical || 0, '모멘텀': scores.momentum || 0, '펀더멘털': scores.fundamental || 0, '머신러닝': scores.ml || 0}).map(([label, score]) => `
            <div class="score-bar-container">
                <div class="score-bar-label"><span>${label}</span><span>${score.toFixed(1)}</span></div>
                <div class="score-bar-bg"><div class="score-bar-fill" style="width:${score}%;background:${barColor(score)}"></div></div>
            </div>
        `).join('')}
    </div>

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

    <div class="detail-section">
        <h3>분석 시그널</h3>
        <ul class="signal-list">${(stock.top_signals || []).map(s => `<li>${s}</li>`).join('')}</ul>
    </div>

    <div class="detail-section" style="text-align:center;padding:16px;background:rgba(0,212,255,0.1);border-radius:var(--radius)">
        <div style="font-size:14px;font-weight:700;color:var(--accent)">${stock.recommendation}</div>
    </div>

    <p style="text-align:center;font-size:10px;color:var(--text-secondary);margin-top:16px">
        * 이 분석은 참고용이며, 투자 결정의 책임은 본인에게 있습니다.
    </p>`;
}

function closeModal() { document.getElementById('modal').classList.add('hidden'); }

function renderMarketEvents(stock) {
    const events = stock.market_events || {};
    let html = '';

    // 마녀의 날
    const w = events.witching || {};
    if (w.is_witching_day) {
        html += `<div class="guide-item"><span class="guide-label">마녀의 날</span><span class="guide-value red">오늘 (변동성 극대화)</span></div>`;
    } else if (w.is_witching_week) {
        html += `<div class="guide-item"><span class="guide-label">마녀의 날</span><span class="guide-value" style="color:var(--orange)">D-${w.days_until} (${w.witching_date})</span></div>`;
    } else if (w.days_until_next && w.days_until_next <= 14) {
        html += `<div class="guide-item"><span class="guide-label">다음 마녀의 날</span><span class="guide-value">${w.next_witching_date} (D-${w.days_until_next})</span></div>`;
    }

    // 실적 발표일
    const e = events.earnings || {};
    if (e.date) {
        const d = e.days_until;
        if (d >= 0 && d <= 3) {
            html += `<div class="guide-item"><span class="guide-label">실적 발표</span><span class="guide-value red">D-${d} (${e.date}) 큰 변동 예상</span></div>`;
        } else if (d >= 0 && d <= 7) {
            html += `<div class="guide-item"><span class="guide-label">실적 발표</span><span class="guide-value" style="color:var(--orange)">D-${d} (${e.date})</span></div>`;
        } else if (d < 0 && d >= -3) {
            html += `<div class="guide-item"><span class="guide-label">실적 발표</span><span class="guide-value">발표 직후 - 결과 확인</span></div>`;
        } else if (d > 7) {
            html += `<div class="guide-item"><span class="guide-label">실적 발표</span><span class="guide-value">${e.date} (D-${d})</span></div>`;
        }
    }

    return html;
}

// === 종목 검색 ===
async function searchStock() {
    const input = document.getElementById('search-ticker');
    const ticker = input.value.trim().toUpperCase();
    if (!ticker) return;

    // 모달로 바로 표시
    const modal = document.getElementById('modal');
    const modalTicker = document.getElementById('modal-ticker');
    const modalBody = document.getElementById('modal-body');

    modalTicker.textContent = ticker;
    modalBody.innerHTML = '<div style="text-align:center;padding:40px"><span class="loading-spinner"></span> ' + ticker + ' 분석 중...</div>';
    modal.classList.remove('hidden');

    try {
        const resp = await fetch(`${API_BASE}/api/stock/${ticker}`);
        if (resp.status === 401) return;
        if (!resp.ok) {
            modalBody.innerHTML = '<div style="text-align:center;padding:40px;color:var(--red)">종목을 찾을 수 없습니다.<br>티커를 확인해주세요.</div>';
            return;
        }
        const stock = await resp.json();
        modalTicker.textContent = `${ticker} - ${stock.stock_info?.name || ''}`;
        modalBody.innerHTML = renderDetail(stock);
    } catch (e) {
        modalBody.innerHTML = '<div style="text-align:center;padding:40px;color:var(--red)">서버 연결 실패</div>';
    }

    input.value = '';
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

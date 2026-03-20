// === Stock Predictor Frontend ===
const API_BASE = window.location.origin;
let allResults = [];
let ws = null;

// === 초기화 ===
document.addEventListener('DOMContentLoaded', () => {
    loadResults();
    connectWebSocket();
});

// === WebSocket 연결 ===
function connectWebSocket() {
    const wsUrl = API_BASE.replace('http', 'ws') + '/ws';
    try {
        ws = new WebSocket(wsUrl);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'progress') {
                updateProgress(data);
            }
        };
        ws.onclose = () => {
            setTimeout(connectWebSocket, 3000);
        };
    } catch (e) {
        console.log('WebSocket 연결 실패, 폴링 모드');
    }
}

// === 분석 시작 ===
async function startAnalysis() {
    const btn = document.getElementById('btn-analyze');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading-spinner"></span>분석 중...';

    showProgress();

    try {
        const resp = await fetch(`${API_BASE}/api/analyze`, { method: 'POST' });
        const data = await resp.json();

        if (data.status === 'running') {
            pollProgress();
        }
    } catch (e) {
        alert('서버 연결 실패. 서버가 실행 중인지 확인하세요.');
        btn.disabled = false;
        btn.textContent = '분석 시작';
    }
}

// === 진행 상태 폴링 ===
async function pollProgress() {
    const interval = setInterval(async () => {
        try {
            const resp = await fetch(`${API_BASE}/api/status`);
            const data = await resp.json();
            updateProgress(data);

            if (data.status === 'done' || data.status === 'error') {
                clearInterval(interval);
                if (data.status === 'done') {
                    await loadResults();
                }
                const btn = document.getElementById('btn-analyze');
                btn.disabled = false;
                btn.textContent = '분석 시작';

                setTimeout(() => hideProgress(), 2000);
            }
        } catch (e) {
            console.error('폴링 오류:', e);
        }
    }, 2000);
}

// === 진행 상태 업데이트 ===
function updateProgress(data) {
    const fill = document.getElementById('progress-fill');
    const text = document.getElementById('progress-text');

    fill.style.width = `${data.progress || 0}%`;
    text.textContent = data.message || '진행 중...';
}

function showProgress() {
    document.getElementById('progress-section').classList.remove('hidden');
}

function hideProgress() {
    document.getElementById('progress-section').classList.add('hidden');
}

// === 결과 로드 ===
async function loadResults() {
    try {
        const resp = await fetch(`${API_BASE}/api/results`);
        if (!resp.ok) return;

        const data = await resp.json();
        allResults = data.top_picks || [];

        // 요약 업데이트
        document.getElementById('summary-section').classList.remove('hidden');
        document.getElementById('filter-section').classList.remove('hidden');
        document.getElementById('total-analyzed').textContent = data.analyzed_count || '-';
        document.getElementById('total-qualified').textContent = data.qualified_count || '-';
        document.getElementById('elapsed-time').textContent =
            data.elapsed_seconds ? `${data.elapsed_seconds}초` : '-';

        if (data.timestamp) {
            const d = new Date(data.timestamp);
            document.getElementById('last-update').textContent =
                `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`;
        }

        renderStockList(allResults);

        // 분석 버튼 복원
        const btn = document.getElementById('btn-analyze');
        btn.disabled = false;
        btn.textContent = '분석 시작';
    } catch (e) {
        console.log('결과 로드 실패:', e);
    }
}

// === 종목 리스트 렌더링 ===
function renderStockList(stocks) {
    const container = document.getElementById('stock-list');

    if (!stocks || stocks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>분석 결과가 없습니다.</p>
                <p>상단의 "분석 시작" 버튼을 눌러주세요.</p>
            </div>`;
        return;
    }

    container.innerHTML = stocks.map((s, i) => createStockCard(s, i)).join('');
}

function createStockCard(stock, index) {
    const info = stock.stock_info || {};
    const price = stock.price_info || {};
    const scores = stock.scores || {};

    const changeClass = (price.change_pct || 0) >= 0 ? 'up' : 'down';
    const changeSign = (price.change_pct || 0) >= 0 ? '+' : '';

    const prob1dClass = stock.rise_probability_1d >= 65 ? 'high' :
                        stock.rise_probability_1d >= 50 ? 'medium' : 'low';
    const prob5dClass = stock.rise_probability_5d >= 65 ? 'high' :
                        stock.rise_probability_5d >= 50 ? 'medium' : 'low';

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

        <div class="card-scores">
            <div class="score-chip">
                <span class="label">기술</span>
                <span class="value">${(scores.technical || 0).toFixed(0)}</span>
            </div>
            <div class="score-chip">
                <span class="label">모멘텀</span>
                <span class="value">${(scores.momentum || 0).toFixed(0)}</span>
            </div>
            <div class="score-chip">
                <span class="label">펀더멘털</span>
                <span class="value">${(scores.fundamental || 0).toFixed(0)}</span>
            </div>
            <div class="score-chip">
                <span class="label">ML</span>
                <span class="value">${(scores.ml || 0).toFixed(0)}</span>
            </div>
            <div class="score-chip" style="background:rgba(0,212,255,0.15)">
                <span class="label">종합</span>
                <span class="value" style="color:var(--accent)">${stock.final_score.toFixed(0)}</span>
            </div>
        </div>

        <div class="card-bottom">
            <div class="card-probs">
                <div class="prob-item">
                    <div class="prob-label">1일 상승</div>
                    <div class="prob-value ${prob1dClass}">${stock.rise_probability_1d.toFixed(0)}%</div>
                </div>
                <div class="prob-item">
                    <div class="prob-label">5일 상승</div>
                    <div class="prob-value ${prob5dClass}">${stock.rise_probability_5d.toFixed(0)}%</div>
                </div>
            </div>
            <div class="card-price">
                <div class="price-value">$${(price.current_price || 0).toFixed(2)}</div>
                <div class="price-change ${changeClass}">
                    ${changeSign}${(price.change_pct || 0).toFixed(2)}%
                </div>
            </div>
        </div>

        <div class="card-recommendation">${stock.recommendation || ''}</div>
    </div>`;
}

// === 종목 상세 ===
async function showDetail(ticker) {
    const modal = document.getElementById('modal');
    const modalTicker = document.getElementById('modal-ticker');
    const modalBody = document.getElementById('modal-body');

    modalTicker.textContent = ticker;
    modalBody.innerHTML = '<div style="text-align:center;padding:40px"><span class="loading-spinner"></span> 상세 분석 중...</div>';
    modal.classList.remove('hidden');

    // 캐시된 결과에서 먼저 찾기
    let stock = allResults.find(s => s.ticker === ticker);

    if (!stock) {
        try {
            const resp = await fetch(`${API_BASE}/api/stock/${ticker}`);
            if (resp.ok) {
                stock = await resp.json();
            }
        } catch (e) {
            modalBody.innerHTML = '<p>데이터를 불러올 수 없습니다.</p>';
            return;
        }
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
    const info = stock.stock_info || {};
    const price = stock.price_info || {};

    const riskClass = stock.risk_level === '낮음' ? 'low' :
                      stock.risk_level === '보통' ? 'medium' : 'high';

    // 점수 바 색상
    const barColor = (score) => {
        if (score >= 70) return 'var(--green)';
        if (score >= 50) return 'var(--yellow)';
        if (score >= 30) return 'var(--orange)';
        return 'var(--red)';
    };

    return `
    <!-- 종합 점수 -->
    <div class="detail-section">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <div>
                <div style="font-size:36px;font-weight:800;color:var(--accent)">${stock.final_score.toFixed(1)}</div>
                <div style="font-size:12px;color:var(--text-secondary)">종합 점수</div>
            </div>
            <div style="text-align:center">
                <div class="card-grade ${stock.grade}" style="width:56px;height:56px;font-size:24px">${stock.grade}</div>
            </div>
            <div style="text-align:right">
                <span class="risk-badge ${riskClass}">리스크: ${stock.risk_level}</span>
            </div>
        </div>
    </div>

    <!-- 상승 확률 -->
    <div class="detail-section">
        <h3>상승 확률</h3>
        <div class="detail-grid">
            <div class="detail-item">
                <div class="label">당일 (1일)</div>
                <div class="value" style="color:${stock.rise_probability_1d >= 60 ? 'var(--green)' : 'var(--text-primary)'}">
                    ${stock.rise_probability_1d.toFixed(1)}%
                </div>
            </div>
            <div class="detail-item">
                <div class="label">일주일 (5일)</div>
                <div class="value" style="color:${stock.rise_probability_5d >= 60 ? 'var(--green)' : 'var(--text-primary)'}">
                    ${stock.rise_probability_5d.toFixed(1)}%
                </div>
            </div>
        </div>
    </div>

    <!-- 분석별 점수 -->
    <div class="detail-section">
        <h3>분석 점수</h3>
        ${Object.entries({
            '기술적 분석': scores.technical || 0,
            '모멘텀': scores.momentum || 0,
            '펀더멘털': scores.fundamental || 0,
            '머신러닝': scores.ml || 0,
        }).map(([label, score]) => `
            <div class="score-bar-container">
                <div class="score-bar-label">
                    <span>${label}</span>
                    <span>${score.toFixed(1)}/100</span>
                </div>
                <div class="score-bar-bg">
                    <div class="score-bar-fill" style="width:${score}%;background:${barColor(score)}"></div>
                </div>
            </div>
        `).join('')}
    </div>

    <!-- 가격 정보 -->
    ${price.current_price ? `
    <div class="detail-section">
        <h3>가격 정보</h3>
        <div class="detail-grid">
            <div class="detail-item">
                <div class="label">현재가</div>
                <div class="value">$${price.current_price}</div>
            </div>
            <div class="detail-item">
                <div class="label">전일 대비</div>
                <div class="value" style="color:${price.change_pct >= 0 ? 'var(--green)' : 'var(--red)'}">
                    ${price.change_pct >= 0 ? '+' : ''}${price.change_pct}%
                </div>
            </div>
            <div class="detail-item">
                <div class="label">거래량</div>
                <div class="value">${formatNumber(price.volume)}</div>
            </div>
            <div class="detail-item">
                <div class="label">섹터</div>
                <div class="value" style="font-size:11px">${info.sector || '-'}</div>
            </div>
        </div>
    </div>
    ` : ''}

    <!-- 상세 지표 -->
    <div class="detail-section">
        <h3>주요 지표</h3>
        <div class="detail-grid">
            ${Object.entries(details).filter(([k]) =>
                ['RSI', 'MACD', 'ADX', 'CCI', 'MFI', 'Volume_Ratio_20D',
                 'Forward_PE', 'PEG', 'ROE', 'Revenue_Growth', 'Earnings_Growth',
                 'ML_1d_prob', 'ML_5d_prob', 'Return_1D', 'Return_5D', 'Return_20D',
                 'Debt_to_Equity', 'Profit_Margin', 'BB_Width'
                ].includes(k)
            ).map(([k, v]) => `
                <div class="detail-item">
                    <div class="label">${formatLabel(k)}</div>
                    <div class="value">${typeof v === 'number' ? v.toFixed(2) : v}</div>
                </div>
            `).join('')}
        </div>
    </div>

    <!-- 시그널 -->
    <div class="detail-section">
        <h3>분석 시그널</h3>
        <ul class="signal-list">
            ${(stock.top_signals || []).map(s => `<li>${s}</li>`).join('')}
        </ul>
    </div>

    <!-- 추천 -->
    <div class="detail-section" style="text-align:center;padding:16px;background:rgba(0,212,255,0.1);border-radius:var(--radius)">
        <div style="font-size:14px;font-weight:700;color:var(--accent)">${stock.recommendation}</div>
    </div>

    <p style="text-align:center;font-size:10px;color:var(--text-secondary);margin-top:16px">
        * 이 분석은 참고용이며, 투자 결정의 책임은 본인에게 있습니다.
    </p>
    `;
}

function closeModal() {
    document.getElementById('modal').classList.add('hidden');
}

// === 종목 검색 ===
async function searchStock() {
    const input = document.getElementById('search-ticker');
    const ticker = input.value.trim().toUpperCase();
    if (!ticker) return;

    input.value = '';
    await showDetail(ticker);
}

// === 필터링 ===
function filterResults() {
    const grade = document.getElementById('filter-grade').value;
    const risk = document.getElementById('filter-risk').value;

    let filtered = [...allResults];

    if (grade !== 'all') {
        filtered = filtered.filter(s => s.grade === grade);
    }
    if (risk !== 'all') {
        filtered = filtered.filter(s => s.risk_level === risk);
    }

    renderStockList(filtered);
}

// === 정렬 ===
function sortResults() {
    const sortBy = document.getElementById('sort-by').value;
    let sorted = [...allResults];

    switch (sortBy) {
        case 'score':
            sorted.sort((a, b) => b.final_score - a.final_score);
            break;
        case 'prob1d':
            sorted.sort((a, b) => b.rise_probability_1d - a.rise_probability_1d);
            break;
        case 'prob5d':
            sorted.sort((a, b) => b.rise_probability_5d - a.rise_probability_5d);
            break;
    }

    renderStockList(sorted);
}

// === 유틸리티 ===
function formatNumber(num) {
    if (!num) return '-';
    if (num >= 1e9) return (num / 1e9).toFixed(1) + 'B';
    if (num >= 1e6) return (num / 1e6).toFixed(1) + 'M';
    if (num >= 1e3) return (num / 1e3).toFixed(1) + 'K';
    return num.toLocaleString();
}

function formatLabel(key) {
    const labels = {
        'RSI': 'RSI (14)',
        'MACD': 'MACD',
        'ADX': 'ADX',
        'CCI': 'CCI',
        'MFI': 'MFI',
        'Volume_Ratio_20D': '거래량비율(20일)',
        'Forward_PE': 'Forward P/E',
        'PEG': 'PEG Ratio',
        'ROE': 'ROE',
        'Revenue_Growth': '매출성장률',
        'Earnings_Growth': '이익성장률',
        'ML_1d_prob': 'ML 1일 확률',
        'ML_5d_prob': 'ML 5일 확률',
        'Return_1D': '1일 수익률',
        'Return_5D': '5일 수익률',
        'Return_20D': '20일 수익률',
        'Debt_to_Equity': '부채비율',
        'Profit_Margin': '순이익률',
        'BB_Width': '볼린저밴드 폭',
    };
    return labels[key] || key;
}

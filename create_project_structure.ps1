# 개선된 프로젝트 구조 생성 스크립트

# 1. 새로운 디렉토리 구조 생성
Write-Host "프론트엔드 구조 생성 중..." -ForegroundColor Yellow

New-Item -ItemType Directory -Path "static" -Force | Out-Null
New-Item -ItemType Directory -Path "static\css" -Force | Out-Null
New-Item -ItemType Directory -Path "static\js" -Force | Out-Null
New-Item -ItemType Directory -Path "static\images" -Force | Out-Null
New-Item -ItemType Directory -Path "templates" -Force | Out-Null

Write-Host "디렉토리 구조:" -ForegroundColor Cyan
Write-Host "charging_station_predictor/" -ForegroundColor White
Write-Host "├── static/" -ForegroundColor White
Write-Host "│   ├── css/" -ForegroundColor White
Write-Host "│   ├── js/" -ForegroundColor White
Write-Host "│   └── images/" -ForegroundColor White
Write-Host "├── templates/" -ForegroundColor White
Write-Host "└── main.py (깔끔해짐)" -ForegroundColor White

# 2. CSS 파일 생성
$cssContent = @'
/* static/css/dashboard.css */
* { 
    margin: 0; 
    padding: 0; 
    box-sizing: border-box; 
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    color: #333;
}

.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
}

.header {
    text-align: center;
    color: white;
    margin-bottom: 30px;
}

.header h1 {
    font-size: 2.5em;
    margin-bottom: 10px;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

.station-info {
    background: rgba(255,255,255,0.95);
    border-radius: 15px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.1);
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.metric-card {
    background: white;
    border-radius: 15px;
    padding: 25px;
    text-align: center;
    box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.metric-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.15);
}

.metric-card h3 {
    color: #666;
    font-size: 0.9em;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.metric-value {
    font-size: 2.5em;
    font-weight: bold;
    margin-bottom: 5px;
}

.metric-value.power { color: #ff6b6b; }
.metric-value.contract { color: #4ecdc4; }
.metric-value.utilization { color: #45b7d1; }
.metric-value.sessions { color: #96ceb4; }

.metric-unit {
    color: #999;
    font-size: 0.9em;
}

.charts-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 30px;
}

.chart-card {
    background: white;
    border-radius: 15px;
    padding: 25px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.1);
}

.chart-card h3 {
    margin-bottom: 20px;
    color: #333;
    font-size: 1.3em;
}

.control-panel {
    background: white;
    border-radius: 15px;
    padding: 25px;
    margin-bottom: 20px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.1);
}

.button-group {
    display: flex;
    gap: 15px;
    flex-wrap: wrap;
    margin-bottom: 20px;
}

.btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 25px;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
}

.btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.3);
}

.btn:active {
    transform: translateY(0);
}

.results-panel {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 20px;
    margin-top: 15px;
    border-left: 4px solid #667eea;
}

.results-panel pre {
    background: #fff;
    padding: 15px;
    border-radius: 8px;
    overflow-x: auto;
    font-size: 0.9em;
    line-height: 1.4;
}

.status-indicator {
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-right: 8px;
}

.status-online { background: #4caf50; }
.status-warning { background: #ff9800; }
.status-offline { background: #f44336; }

.loading {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 3px solid #f3f3f3;
    border-top: 3px solid #667eea;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.alert {
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
}

.alert-info {
    background: #d1ecf1;
    border: 1px solid #bee5eb;
    color: #0c5460;
}

.alert-warning {
    background: #fff3cd;
    border: 1px solid #ffeaa7;
    color: #856404;
}

@media (max-width: 768px) {
    .charts-grid {
        grid-template-columns: 1fr;
    }
    
    .button-group {
        justify-content: center;
    }
    
    .metric-card {
        padding: 20px;
    }
}
'@

Set-Content -Path "static\css\dashboard.css" -Value $cssContent -Encoding UTF8

# 3. JavaScript 파일 생성
$jsContent = @'
// static/js/dashboard.js
// 전역 변수
let hourlyChart, distributionChart, monthlyChart, socChart;
let currentData = {};

// 차트 초기화
function initCharts() {
    // 시간대별 전력 패턴 차트
    const hourlyCtx = document.getElementById('hourlyChart').getContext('2d');
    hourlyChart = new Chart(hourlyCtx, {
        type: 'line',
        data: {
            labels: Array.from({length: 24}, (_, i) => `${i}시`),
            datasets: [{
                label: '평균 전력 (kW)',
                data: [],
                borderColor: '#ff6b6b',
                backgroundColor: 'rgba(255, 107, 107, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: '전력 (kW)'
                    }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
    
    // 전력 분포 차트
    const distributionCtx = document.getElementById('distributionChart').getContext('2d');
    distributionChart = new Chart(distributionCtx, {
        type: 'doughnut',
        data: {
            labels: ['낮은 전력 (0-30kW)', '중간 전력 (30-60kW)', '높은 전력 (60-100kW)'],
            datasets: [{
                data: [30, 50, 20],
                backgroundColor: ['#96ceb4', '#45b7d1', '#ff6b6b'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });
    
    // 월별 예측 트렌드 차트
    const monthlyCtx = document.getElementById('monthlyChart').getContext('2d');
    monthlyChart = new Chart(monthlyCtx, {
        type: 'bar',
        data: {
            labels: ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'],
            datasets: [{
                label: '예상 최고전력 (kW)',
                data: [],
                backgroundColor: '#4ecdc4',
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: '전력 (kW)'
                    }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
    
    // SOC vs 전력 관계 차트
    const socCtx = document.getElementById('socChart').getContext('2d');
    socChart = new Chart(socCtx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'SOC vs 전력',
                data: [],
                backgroundColor: '#667eea',
                borderColor: '#667eea'
            }]
        },
        options: {
            responsive: true,
            scales: {
                x: {
                    title: { display: true, text: '시작 SOC (%)' },
                    min: 0, max: 100
                },
                y: {
                    title: { display: true, text: '순간최고전력 (kW)' },
                    min: 0, max: 100
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

// API 호출 함수들
async function testRealtime() {
    showLoading('refresh-icon');
    try {
        const response = await fetch('/predict/BNS0791');
        const data = await response.json();
        
        updateMetrics(data);
        updateResults(data, '실시간 예측 결과');
        
    } catch (error) {
        showError('실시간 예측 오류: ' + error.message);
    } finally {
        hideLoading('refresh-icon');
    }
}

async function testMonthly() {
    try {
        const response = await fetch('/api/monthly-contract/BNS0791?year=2025&month=6');
        const data = await response.json();
        
        document.getElementById('contract-power').textContent = data.recommended_contract_kw;
        updateResults(data, '월별 계약 권고 결과');
        
    } catch (error) {
        showError('월별 예측 오류: ' + error.message);
    }
}

async function testAnalysis() {
    try {
        const response = await fetch('/api/station-analysis/BNS0791');
        const data = await response.json();
        
        updateCharts(data);
        updateResults(data, '상세 분석 결과');
        
    } catch (error) {
        showError('상세 분석 오류: ' + error.message);
    }
}

async function refreshDashboard() {
    showLoading('refresh-icon');
    try {
        await Promise.all([testRealtime(), testAnalysis()]);
        showSuccess('대시보드가 성공적으로 새로고침되었습니다.');
    } catch (error) {
        showError('대시보드 새로고침 실패: ' + error.message);
    } finally {
        hideLoading('refresh-icon');
    }
}

function exportData() {
    const exportData = {
        timestamp: new Date().toISOString(),
        station_id: 'BNS0791',
        current_data: currentData,
        charts_data: {
            hourly: hourlyChart.data,
            distribution: distributionChart.data,
            monthly: monthlyChart.data
        }
    };
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `BNS0791_analysis_${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    
    showSuccess('데이터가 성공적으로 내보내졌습니다.');
}

// UI 업데이트 함수들
function updateMetrics(data) {
    currentData = data;
    
    document.getElementById('current-power').textContent = data.predicted_peak || '-';
    
    // 100kW 급속충전기 기준 이용률 계산
    const utilization = data.predicted_peak ? (data.predicted_peak / 100 * 100).toFixed(1) : '-';
    document.getElementById('utilization-rate').textContent = utilization;
    document.getElementById('station-utilization').textContent = utilization;
    
    const sessionCount = data.data_quality?.sessions_analyzed || '-';
    document.getElementById('session-count').textContent = sessionCount;
}

function updateCharts(analysisData) {
    if (analysisData.charts_data?.hourly_pattern) {
        hourlyChart.data.datasets[0].data = analysisData.charts_data.hourly_pattern;
        hourlyChart.update();
    }
    
    if (analysisData.monthly_predictions?.data) {
        monthlyChart.data.datasets[0].data = analysisData.monthly_predictions.data;
        monthlyChart.update();
    }
    
    if (analysisData.charts_data?.soc_power_relationship) {
        socChart.data.datasets[0].data = analysisData.charts_data.soc_power_relationship;
        socChart.update();
    }
}

function updateResults(data, title) {
    const resultsDiv = document.getElementById('results');
    const resultsContent = document.getElementById('results-content');
    
    resultsContent.textContent = JSON.stringify(data, null, 2);
    resultsDiv.style.display = 'block';
    
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

function showLoading(iconId) {
    const icon = document.getElementById(iconId);
    if (icon) {
        icon.innerHTML = '<div class="loading"></div>';
    }
}

function hideLoading(iconId) {
    const icon = document.getElementById(iconId);
    if (icon) {
        icon.textContent = '🔄';
    }
}

function showSuccess(message) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-info';
    alert.innerHTML = `<strong>✅ 성공:</strong> ${message}`;
    document.querySelector('.control-panel').appendChild(alert);
    
    setTimeout(() => alert.remove(), 3000);
}

function showError(message) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-warning';
    alert.innerHTML = `<strong>❌ 오류:</strong> ${message}`;
    document.querySelector('.control-panel').appendChild(alert);
    
    setTimeout(() => alert.remove(), 5000);
}

// 초기화
window.onload = function() {
    initCharts();
    refreshDashboard();
};

// 5분마다 자동 새로고침
setInterval(refreshDashboard, 5 * 60 * 1000);
'@

Set-Content -Path "static\js\dashboard.js" -Value $jsContent -Encoding UTF8

Write-Host "✅ 프론트엔드 파일 생성 완료!" -ForegroundColor Green
Write-Host "📁 static/css/dashboard.css" -ForegroundColor White
Write-Host "📁 static/js/dashboard.js" -ForegroundColor White
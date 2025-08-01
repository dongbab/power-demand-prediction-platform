// static/js/dashboard.js - 완전 개선된 버전
'use strict';

// === 전역 변수 ===
let hourlyChart, distributionChart, monthlyChart, socChart;
let currentData = {};
let currentStationId = '';
let stationInfo = {};
let autoRefreshInterval = null;
let isResizing = false;
let connectionStatus = true;
let lastUpdateTime = null;

// === 초기화 함수 ===
function initializeDashboard() {
    console.log('🚀 대시보드 초기화 시작');
    
    // 1. 충전소 정보 로드
    loadStationData();
    
    // 2. 차트 초기화
    initializeCharts();
    
    // 3. 이벤트 리스너 등록
    setupEventListeners();
    
    // 4. 초기 데이터 로드
    setTimeout(() => {
        loadInitialData();
    }, 1000);
    
    // 5. 자동 새로고침 시작
    startAutoRefresh();
    
    // 6. 네트워크 상태 모니터링
    setupNetworkMonitoring();
    
    console.log('✅ 대시보드 초기화 완료');
}

// === 충전소 데이터 로드 ===
function loadStationData() {
    try {
        // 1순위: window 전역 변수
        if (window.CURRENT_STATION_ID && window.STATION_INFO) {
            currentStationId = window.CURRENT_STATION_ID;
            stationInfo = window.STATION_INFO;
            console.log('✅ 전역 변수에서 충전소 정보 로드:', stationInfo.name);
            return;
        }
        
        // 2순위: 메타 태그
        const stationIdMeta = document.querySelector('meta[name="station-id"]');
        if (stationIdMeta) {
            currentStationId = stationIdMeta.content;
            
            stationInfo = {
                id: currentStationId,
                name: document.querySelector('meta[name="station-name"]')?.content || '충전소',
                location: document.querySelector('meta[name="station-location"]')?.content || '위치 정보 없음',
                charger_type: document.querySelector('meta[name="station-charger-type"]')?.content || '100kW 급속충전기',
                connector_type: document.querySelector('meta[name="station-connector-type"]')?.content || 'DC콤보'
            };
            
            console.log('✅ 메타 태그에서 충전소 정보 로드:', stationInfo.name);
            return;
        }
        
        // 3순위: URL 파싱
        const pathParts = window.location.pathname.split('/');
        const dashboardIndex = pathParts.indexOf('dashboard');
        
        if (dashboardIndex !== -1 && pathParts[dashboardIndex + 1]) {
            currentStationId = pathParts[dashboardIndex + 1];
            stationInfo = {
                id: currentStationId,
                name: `충전소 ${currentStationId}`,
                location: '위치 정보 로딩 중...'
            };
            console.log('✅ URL에서 충전소 ID 추출:', currentStationId);
            return;
        }
        
        // 기본값
        currentStationId = 'BNS0791';
        stationInfo = {
            id: currentStationId,
            name: '기본 충전소',
            location: '위치 정보 없음'
        };
        
        console.warn('⚠️ 기본 충전소 정보 사용');
        
    } catch (error) {
        console.error('충전소 데이터 로드 실패:', error);
        currentStationId = 'BNS0791';
        stationInfo = { id: currentStationId, name: '오류 발생' };
    }
}

// === 차트 초기화 ===
function initializeCharts() {
    console.log('📊 차트 초기화 시작');
    
    // Chart.js 전역 설정
    Chart.defaults.responsive = true;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.plugins.legend.display = false;
    Chart.defaults.animation = {
        duration: 1000,
        easing: 'easeOutQuart'
    };
    
    try {
        initHourlyChart();
        initDistributionChart();
        initMonthlyChart();
        initSocChart();
        
        console.log('✅ 모든 차트 초기화 완료');
    } catch (error) {
        console.error('❌ 차트 초기화 실패:', error);
        showMessage('차트 초기화에 실패했습니다.', 'error');
    }
}

// 시간대별 전력 패턴 차트
function initHourlyChart() {
    const canvas = document.getElementById('hourlyChart');
    if (!canvas) {
        console.warn('hourlyChart 캔버스를 찾을 수 없습니다');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    hourlyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array.from({length: 24}, (_, i) => `${i}시`),
            datasets: [{
                label: '평균 전력 (kW)',
                data: new Array(24).fill(0),
                borderColor: '#ff6b6b',
                backgroundColor: 'rgba(255, 107, 107, 0.1)',
                borderWidth: 3,
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#ff6b6b',
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: '#ff6b6b',
                    borderWidth: 1,
                    callbacks: {
                        label: function(context) {
                            return `${context.parsed.x}시: ${context.parsed.y.toFixed(1)}kW`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: '전력 (kW)',
                        color: '#666',
                        font: { size: 12, weight: 'bold' }
                    },
                    grid: { 
                        color: 'rgba(0,0,0,0.1)',
                        drawBorder: false
                    },
                    ticks: { 
                        color: '#666',
                        callback: function(value) {
                            return value + 'kW';
                        }
                    }
                },
                x: {
                    grid: { 
                        color: 'rgba(0,0,0,0.05)',
                        drawBorder: false
                    },
                    ticks: { color: '#666' }
                }
            }
        }
    });
}

// 전력 분포 차트
function initDistributionChart() {
    const canvas = document.getElementById('distributionChart');
    if (!canvas) {
        console.warn('distributionChart 캔버스를 찾을 수 없습니다');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    distributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['낮은 전력 (0-30kW)', '중간 전력 (30-60kW)', '높은 전력 (60-100kW)'],
            datasets: [{
                data: [30, 50, 20],
                backgroundColor: [
                    'rgba(150, 206, 180, 0.8)',
                    'rgba(69, 183, 209, 0.8)',
                    'rgba(255, 107, 107, 0.8)'
                ],
                borderColor: [
                    '#96ceb4',
                    '#45b7d1',
                    '#ff6b6b'
                ],
                borderWidth: 3,
                hoverOffset: 15
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        font: { size: 11 },
                        color: '#666'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((context.parsed / total) * 100).toFixed(1);
                            return `${context.label}: ${percentage}%`;
                        }
                    }
                }
            }
        }
    });
}

// 월별 예측 트렌드 차트
function initMonthlyChart() {
    const canvas = document.getElementById('monthlyChart');
    if (!canvas) {
        console.warn('monthlyChart 캔버스를 찾을 수 없습니다');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    monthlyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'],
            datasets: [{
                label: '예상 최고전력 (kW)',
                data: new Array(12).fill(0),
                backgroundColor: 'rgba(78, 205, 196, 0.8)',
                borderColor: '#4ecdc4',
                borderWidth: 2,
                borderRadius: 8,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: '#4ecdc4',
                    borderWidth: 1,
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.parsed.y.toFixed(1)}kW`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: '전력 (kW)',
                        color: '#666',
                        font: { size: 12, weight: 'bold' }
                    },
                    grid: { 
                        color: 'rgba(0,0,0,0.1)',
                        drawBorder: false
                    },
                    ticks: { 
                        color: '#666',
                        callback: function(value) {
                            return value + 'kW';
                        }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#666' }
                }
            }
        }
    });
}

// SOC vs 전력 관계 차트
function initSocChart() {
    const canvas = document.getElementById('socChart');
    if (!canvas) {
        console.warn('socChart 캔버스를 찾을 수 없습니다');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    socChart = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'SOC vs 전력',
                data: [],
                backgroundColor: 'rgba(102, 126, 234, 0.7)',
                borderColor: '#667eea',
                pointRadius: 6,
                pointHoverRadius: 10,
                pointBorderWidth: 2,
                pointBorderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: '#667eea',
                    borderWidth: 1,
                    callbacks: {
                        title: () => 'SOC vs 전력 관계',
                        label: function(context) {
                            return `SOC: ${context.parsed.x}%, 전력: ${context.parsed.y.toFixed(1)}kW`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: '시작 SOC (%)',
                        color: '#666',
                        font: { size: 12, weight: 'bold' }
                    },
                    min: 0,
                    max: 100,
                    grid: { 
                        color: 'rgba(0,0,0,0.1)',
                        drawBorder: false
                    },
                    ticks: { 
                        color: '#666',
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: '순간최고전력 (kW)',
                        color: '#666',
                        font: { size: 12, weight: 'bold' }
                    },
                    min: 0,
                    max: 100,
                    grid: { 
                        color: 'rgba(0,0,0,0.1)',
                        drawBorder: false
                    },
                    ticks: { 
                        color: '#666',
                        callback: function(value) {
                            return value + 'kW';
                        }
                    }
                }
            }
        }
    });
}

// === 네트워크 상태 모니터링 ===
function setupNetworkMonitoring() {
    // 온라인/오프라인 상태 감지
    window.addEventListener('online', () => {
        connectionStatus = true;
        updateConnectionStatus(true);
        showMessage('인터넷 연결이 복구되었습니다', 'success');
        setTimeout(refreshDashboard, 1000);
    });
    
    window.addEventListener('offline', () => {
        connectionStatus = false;
        updateConnectionStatus(false);
        showMessage('인터넷 연결이 끊어졌습니다', 'warning');
        stopAutoRefresh();
    });
    
    console.log('🌐 네트워크 상태 모니터링 설정 완료');
}

// === 실시간 상태 표시 개선 ===
function updateConnectionStatus(isOnline = true) {
    const statusIndicators = document.querySelectorAll('.status-indicator');
    statusIndicators.forEach(indicator => {
        indicator.className = 'status-indicator ' + (isOnline ? 'status-online' : 'status-offline');
    });
}

// === 차트 애니메이션 효과 개선 ===
function animateMetricUpdate(elementId, newValue, suffix = '') {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const currentValue = parseFloat(element.textContent) || 0;
    const targetValue = parseFloat(newValue) || 0;
    const duration = 1000; // 1초
    const startTime = performance.now();
    
    function animate(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // easeOutCubic 이징 함수
        const easeProgress = 1 - Math.pow(1 - progress, 3);
        const currentDisplay = currentValue + (targetValue - currentValue) * easeProgress;
        
        element.textContent = currentDisplay.toFixed(1) + suffix;
        
        if (progress < 1) {
            requestAnimationFrame(animate);
        } else {
            element.textContent = targetValue.toFixed(1) + suffix;
        }
    }
    
    requestAnimationFrame(animate);
}

// === 차트 데이터 검증 및 안전 업데이트 ===
function safeUpdateChart(chart, newData, chartType = 'line') {
    if (!chart || !chart.data) {
        console.warn('차트가 초기화되지 않았습니다');
        return false;
    }
    
    try {
        if (chartType === 'line' || chartType === 'bar') {
            if (Array.isArray(newData) && newData.length > 0) {
                chart.data.datasets[0].data = newData.map(val => Number(val) || 0);
                chart.update('active');
                return true;
            }
        } else if (chartType === 'scatter') {
            if (Array.isArray(newData) && newData.length > 0) {
                const validData = newData.filter(point => 
                    point && typeof point.x === 'number' && typeof point.y === 'number'
                );
                if (validData.length > 0) {
                    chart.data.datasets[0].data = validData;
                    chart.update('active');
                    return true;
                }
            }
        } else if (chartType === 'doughnut') {
            if (Array.isArray(newData) && newData.length > 0) {
                chart.data.datasets[0].data = newData.map(val => Number(val) || 0);
                chart.update('active');
                return true;
            }
        }
    } catch (error) {
        console.error('차트 업데이트 오류:', error);
    }
    
    return false;
}

// === API 호출 함수들 (향상된 버전) ===
async function testRealtime() {
    const startTime = performance.now();
    const iconId = 'refresh-icon';
    
    showLoading(iconId);
    showMessage('실시간 예측 중...', 'info');
    
    try {
        console.log(`🔮 실시간 예측 시작: ${currentStationId}`);
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10초 타임아웃
        
        const response = await fetch(`/predict/${currentStationId}`, {
            signal: controller.signal,
            headers: {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache'
            }
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('✅ 실시간 예측 완료:', data);
        
        validateApiResponse(data, 'predict');
        updateMetricsWithAnimation(data);
        updateResults(data, '실시간 예측 결과');
        showMessage('✅ 실시간 예측이 완료되었습니다', 'success');
        
        lastUpdateTime = new Date();
        updateConnectionStatus(true);
        
    } catch (error) {
        console.error('❌ 실시간 예측 실패:', error);
        handleApiError(error, '실시간 예측');
        updateConnectionStatus(false);
    } finally {
        hideLoading(iconId);
        logPerformance('실시간 예측', startTime);
    }
}

async function testMonthly() {
    showMessage('월별 계약 권고 분석 중...', 'info');
    
    try {
        const now = new Date();
        const year = now.getFullYear();
        const month = now.getMonth() + 1;
        
        console.log(`📅 월별 계약 권고 시작: ${currentStationId} (${year}-${month})`);
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);
        
        const response = await fetch(`/api/monthly-contract/${currentStationId}?year=${year}&month=${month}`, {
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('✅ 월별 계약 권고 완료:', data);
        
        validateApiResponse(data, 'monthly-contract');
        
        // 권고 계약 전력 애니메이션 업데이트
        if (data.recommended_contract_kw) {
            animateMetricUpdate('contract-power', data.recommended_contract_kw);
        }
        
        updateResults(data, '월별 계약 권고 결과');
        showMessage('✅ 월별 계약 권고가 완료되었습니다', 'success');
        
    } catch (error) {
        console.error('❌ 월별 계약 권고 실패:', error);
        handleApiError(error, '월별 계약 권고');
    }
}

async function testAnalysis() {
    showMessage('상세 분석 중...', 'info');
    
    try {
        console.log(`📊 상세 분석 시작: ${currentStationId}`);
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 20000);
        
        const response = await fetch(`/api/station-analysis/${currentStationId}`, {
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('✅ 상세 분석 완료:', data);
        
        validateApiResponse(data, 'station-analysis');
        updateChartsWithValidation(data);
        updateDetailedMetricsWithAnimation(data);
        updateResults(data, '상세 분석 결과');
        showMessage('✅ 상세 분석이 완료되었습니다', 'success');
        
    } catch (error) {
        console.error('❌ 상세 분석 실패:', error);
        handleApiError(error, '상세 분석');
    }
}

// === 향상된 메트릭 업데이트 ===
function updateMetricsWithAnimation(data) {
    console.log('📈 애니메이션과 함께 메트릭 업데이트:', data);
    
    currentData = { ...currentData, ...data };
    
    // 애니메이션과 함께 값 업데이트
    if (data.predicted_peak !== undefined) {
        animateMetricUpdate('current-power', data.predicted_peak);
        
        const utilization = (data.predicted_peak / 100) * 100;
        animateMetricUpdate('utilization-rate', utilization, '%');
        animateMetricUpdate('station-utilization', utilization, '%');
    }
    
    // 권고 계약 전력
    if (data.recommended_contract_kw !== undefined) {
        animateMetricUpdate('contract-power', data.recommended_contract_kw);
    }
    
    // 세션 수 (애니메이션 없이)
    const sessionCountEl = document.getElementById('session-count');
    if (sessionCountEl) {
        const sessionCount = data.data_quality?.sessions_analyzed || 
                           data.historical_data?.data_sessions || 
                           data.sessions_analyzed || '-';
        sessionCountEl.textContent = sessionCount;
        
        // 세션 수 카드에 펄스 효과 추가
        const sessionCard = sessionCountEl.closest('.metric-card');
        if (sessionCard) {
            sessionCard.style.animation = 'pulse 0.5s ease-in-out';
            setTimeout(() => {
                sessionCard.style.animation = '';
            }, 500);
        }
    }
}

function updateDetailedMetricsWithAnimation(analysisData) {
    console.log('📊 상세 메트릭 애니메이션 업데이트');
    
    if (!analysisData.performance_analysis) {
        console.warn('성능 분석 데이터 없음');
        return;
    }
    
    const perf = analysisData.performance_analysis;
    
    // 평균 전력 애니메이션 업데이트
    if (perf.average_session_power !== undefined) {
        animateMetricUpdate('avg-power', perf.average_session_power);
    }
    
    // 최대 전력 애니메이션 업데이트
    if (perf.maximum_recorded_power !== undefined) {
        animateMetricUpdate('max-power', perf.maximum_recorded_power);
    }
    
    // 현재 이용률 애니메이션 업데이트
    if (perf.utilization_rate !== undefined) {
        animateMetricUpdate('current-utilization', perf.utilization_rate, '%');
    }
}

function updateChartsWithValidation(analysisData) {
    console.log('📊 검증과 함께 차트 업데이트 시작:', analysisData);
    
    if (!analysisData.charts_data) {
        console.warn('차트 데이터 없음');
        return;
    }
    
    const chartsData = analysisData.charts_data;
    let updateCount = 0;
    
    try {
        // 1. 시간대별 패턴 차트
        if (chartsData.hourly_pattern && hourlyChart) {
            if (safeUpdateChart(hourlyChart, chartsData.hourly_pattern, 'line')) {
                console.log('✅ 시간대별 차트 업데이트 완료');
                updateCount++;
            }
        }
        
        // 2. 월별 예측 차트
        if (chartsData.monthly_predictions?.data && monthlyChart) {
            if (safeUpdateChart(monthlyChart, chartsData.monthly_predictions.data, 'bar')) {
                console.log('✅ 월별 예측 차트 업데이트 완료');
                updateCount++;
            }
        }
        
        // 3. SOC vs 전력 차트
        if (chartsData.soc_power_relationship && socChart) {
            if (safeUpdateChart(socChart, chartsData.soc_power_relationship, 'scatter')) {
                console.log('✅ SOC vs 전력 차트 업데이트 완료');
                updateCount++;
            }
        }
        
        // 4. 전력 분포 차트 (통계 기반)
        if (analysisData.patterns?.power_statistics && distributionChart) {
            const stats = analysisData.patterns.power_statistics;
            
            if (stats.mean !== undefined) {
                const avgPower = Number(stats.mean);
                let distribution = calculatePowerDistribution(avgPower);
                
                if (safeUpdateChart(distributionChart, distribution, 'doughnut')) {
                    console.log('✅ 전력 분포 차트 업데이트 완료:', distribution);
                    updateCount++;
                }
            }
        }
        
        console.log(`✅ 총 ${updateCount}개 차트 업데이트 완료`);
        
        if (updateCount > 0) {
            showMessage(`${updateCount}개 차트가 업데이트되었습니다`, 'info');
        }
        
    } catch (error) {
        console.error('❌ 차트 업데이트 실패:', error);
        showMessage('차트 업데이트 중 오류가 발생했습니다', 'error');
    }
}

// === 전력 분포 계산 함수 ===
function calculatePowerDistribution(avgPower) {
    let lowPower, mediumPower, highPower;
    
    if (avgPower <= 30) {
        lowPower = 70;
        mediumPower = 25;
        highPower = 5;
    } else if (avgPower <= 60) {
        lowPower = 30;
        mediumPower = 50;
        highPower = 20;
    } else {
        lowPower = 15;
        mediumPower = 35;
        highPower = 50;
    }
    
    return [lowPower, mediumPower, highPower];
}

// === 통합 대시보드 새로고침 (향상된 버전) ===
async function refreshDashboard() {
    const iconId = 'refresh-icon';
    showLoading(iconId);
    showMessage('대시보드 새로고침 중...', 'info');
    
    const startTime = performance.now();
    let successCount = 0;
    const totalTasks = 3;
    
    try {
        console.log('🔄 대시보드 새로고침 시작');
        
        // 병렬 실행으로 성능 개선 (안정성을 위해 순차 실행 유지)
        const tasks = [
            { name: '실시간 예측', func: testRealtime },
            { name: '상세 분석', func: testAnalysis },
            { name: '월별 계약 권고', func: testMonthly }
        ];
        
        for (const task of tasks) {
            try {
                await task.func();
                successCount++;
                await delay(500); // 서버 부하 방지
            } catch (error) {
                console.error(`${task.name} 실패:`, error);
                // 개별 작업 실패는 전체 새로고침을 중단하지 않음
            }
        }
        
        if (successCount === totalTasks) {
            showMessage('✅ 대시보드가 성공적으로 새로고침되었습니다', 'success');
        } else if (successCount > 0) {
            showMessage(`⚠️ ${successCount}/${totalTasks}개 작업이 완료되었습니다`, 'warning');
        } else {
            showMessage('❌ 새로고침에 실패했습니다', 'error');
        }
        
        console.log(`✅ 대시보드 새로고침 완료 (${successCount}/${totalTasks})`);
        
    } catch (error) {
        console.error('❌ 대시보드 새로고침 실패:', error);
        showMessage('대시보드 새로고침 중 오류가 발생했습니다', 'error');
    } finally {
        hideLoading(iconId);
        logPerformance('대시보드 새로고침', startTime);
        updateLastRefreshTime();
    }
}

// === 마지막 새로고침 시간 표시 ===
function updateLastRefreshTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('ko-KR');
    
    // 기존 시간 표시 요소가 있다면 업데이트
    let timeDisplay = document.getElementById('last-refresh-time');
    if (!timeDisplay) {
        // 없다면 새로 생성
        timeDisplay = document.createElement('div');
        timeDisplay.id = 'last-refresh-time';
        timeDisplay.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            z-index: 1000;
            backdrop-filter: blur(10px);
        `;
        document.body.appendChild(timeDisplay);
    }
    
    timeDisplay.textContent = `마지막 업데이트: ${timeString}`;
    
    // 3초 후 페이드 아웃
    setTimeout(() => {
        timeDisplay.style.opacity = '0.5';
    }, 3000);
}

// === 유틸리티 함수들 ===
function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function updateResults(data, title) {
    const resultsDiv = document.getElementById('results');
    const resultsContent = document.getElementById('results-content');
    
    if (resultsDiv && resultsContent) {
        // JSON을 예쁘게 포맷팅
        const formattedData = JSON.stringify(data, null, 2);
        resultsContent.textContent = formattedData;
        
        // 결과 패널 표시
        resultsDiv.style.display = 'block';
        resultsDiv.classList.remove('hidden');
        
        // 부드러운 스크롤
        setTimeout(() => {
            resultsDiv.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'start',
                inline: 'nearest'
            });
        }, 100);
        
        // 결과 패널에 애니메이션 효과
        resultsDiv.style.animation = 'slideInUp 0.5s ease-out';
    }
}

function exportData() {
    try {
        const exportData = {
            timestamp: new Date().toISOString(),
            station_id: currentStationId,
            station_info: stationInfo,
            current_data: currentData,
            last_update: lastUpdateTime,
            connection_status: connectionStatus,
            charts_data: {
                hourly: hourlyChart?.data,
                distribution: distributionChart?.data,
                monthly: monthlyChart?.data,
                soc: socChart?.data
            },
            system_info: {
                user_agent: navigator.userAgent,
                screen_resolution: `${screen.width}x${screen.height}`,
                viewport: `${window.innerWidth}x${window.innerHeight}`,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
            }
        };
        
        const blob = new Blob([JSON.stringify(exportData, null, 2)], {
            type: 'application/json'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentStationId}_dashboard_${new Date().toISOString().split('T')[0]}.json`;
        
        // 다운로드 시작
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showMessage('✅ 데이터 내보내기 완료', 'success');
        
        // 사용자 분석용 이벤트 로깅
        console.log('📥 데이터 내보내기 완료:', {
            station_id: currentStationId,
            data_size: JSON.stringify(exportData).length,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('데이터 내보내기 실패:', error);
        showMessage('데이터 내보내기에 실패했습니다', 'error');
    }
}

// === 향상된 UI 헬퍼 함수들 ===
function showLoading(iconId) {
    const icon = document.getElementById(iconId);
    if (icon) {
        icon.innerHTML = '<div class="loading-spinner"></div>';
    }
    
    // 버튼들 비활성화
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(btn => {
        btn.disabled = true;
        btn.style.opacity = '0.6';
        btn.style.cursor = 'not-allowed';
    });
}

function hideLoading(iconId) {
    const icon = document.getElementById(iconId);
    if (icon) {
        icon.textContent = '🔄';
    }
    
    // 버튼들 다시 활성화
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(btn => {
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.style.cursor = 'pointer';
    });
}

function showMessage(message, type = 'info') {
    // 기존 메시지 제거
    const existingAlert = document.querySelector('.status-alert');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} status-alert`;
    alert.style.cssText = `
        margin-top: 15px;
        animation: slideInDown 0.5s ease;
        position: relative;
        overflow: hidden;
    `;
    
    const icons = {
        'info': 'ℹ️',
        'success': '✅',
        'warning': '⚠️',
        'error': '❌'
    };
    
    alert.innerHTML = `
        <span style="margin-right: 8px;">${icons[type] || 'ℹ️'}</span>
        ${message}
        <button onclick="this.parentElement.remove()" style="
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            background: none;
            border: none;
            font-size: 1.2em;
            cursor: pointer;
            opacity: 0.7;
        ">×</button>
    `;
    
    const controlPanel = document.querySelector('.control-panel');
    if (controlPanel) {
        controlPanel.appendChild(alert);
        
        // 자동 제거 (성공/정보 메시지만)
        if (type === 'success' || type === 'info') {
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.style.animation = 'slideOutUp 0.5s ease';
                    setTimeout(() => {
                        if (alert.parentNode) {
                            alert.remove();
                        }
                    }, 500);
                }
            }, 4000);
        }
        
        // 진동 효과 (지원되는 경우)
        if (navigator.vibrate && type === 'error') {
            navigator.vibrate([200, 100, 200]);
        }
    }
}

// === 이벤트 리스너 설정 ===
function setupEventListeners() {
    // 윈도우 리사이즈 최적화
    let resizeTimeout;
    
    window.addEventListener('resize', function() {
        if (resizeTimeout) {
            clearTimeout(resizeTimeout);
        }
        
        resizeTimeout = setTimeout(() => {
            if (!isResizing) {
                isResizing = true;
                console.log('🔄 윈도우 리사이즈 - 차트 업데이트');
                
                try {
                    // 모든 차트 리사이즈
                    const charts = [hourlyChart, distributionChart, monthlyChart, socChart];
                    charts.forEach(chart => {
                        if (chart) {
                            chart.resize();
                        }
                    });
                } catch (error) {
                    console.error('차트 리사이즈 오류:', error);
                } finally {
                    isResizing = false;
                }
            }
        }, 250);
    });
    
    // 스크롤 이벤트 최적화 (차트 가시성 감지)
    let scrollTimeout;
    window.addEventListener('scroll', function() {
        if (scrollTimeout) {
            clearTimeout(scrollTimeout);
        }
        
        scrollTimeout = setTimeout(() => {
            checkChartVisibility();
        }, 100);
    });
    
    // 버튼 이벤트 리스너 (이벤트 위임 사용)
    document.addEventListener('click', function(e) {
        const target = e.target;
        
        if (target.matches('[onclick*="refreshDashboard"]')) {
            e.preventDefault();
            refreshDashboard();
        } else if (target.matches('[onclick*="testRealtime"]')) {
            e.preventDefault();
            testRealtime();
        } else if (target.matches('[onclick*="testMonthly"]')) {
            e.preventDefault();
            testMonthly();
        } else if (target.matches('[onclick*="testAnalysis"]')) {
            e.preventDefault();
            testAnalysis();
        } else if (target.matches('[onclick*="exportData"]')) {
            e.preventDefault();
            exportData();
        }
    });
    
    // 키보드 단축키 개선
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd 키와 함께 사용
        if (e.ctrlKey || e.metaKey) {
            switch(e.key.toLowerCase()) {
                case 'r':
                    e.preventDefault();
                    refreshDashboard();
                    showMessage('키보드 단축키로 새로고침 실행', 'info');
                    break;
                case 'e':
                    e.preventDefault();
                    exportData();
                    break;
                case '1':
                    e.preventDefault();
                    testRealtime();
                    break;
                case '2':
                    e.preventDefault();
                    testAnalysis();
                    break;
                case '3':
                    e.preventDefault();
                    testMonthly();
                    break;
                case 'h':
                    e.preventDefault();
                    showKeyboardShortcuts();
                    break;
            }
        }
        
        // ESC 키로 결과 패널 닫기
        if (e.key === 'Escape') {
            const resultsPanel = document.getElementById('results');
            if (resultsPanel && resultsPanel.style.display !== 'none') {
                resultsPanel.style.display = 'none';
                showMessage('결과 패널이 닫혔습니다', 'info');
            }
        }
    });
    
    // 페이지 가시성 변경 감지 개선
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            console.log('⏸️ 페이지 숨김 - 자동 새로고침 중지');
            stopAutoRefresh();
        } else {
            console.log('▶️ 페이지 활성화 - 자동 새로고침 재시작');
            startAutoRefresh();
            
            // 페이지가 5분 이상 숨겨져 있었다면 즉시 새로고침
            if (lastUpdateTime && (Date.now() - lastUpdateTime.getTime()) > 5 * 60 * 1000) {
                setTimeout(refreshDashboard, 1000);
            }
        }
    });
    
    console.log('✅ 이벤트 리스너 설정 완료');
}

// === 키보드 단축키 도움말 ===
function showKeyboardShortcuts() {
    const shortcuts = `
    ⌨️ 키보드 단축키:
    
    Ctrl/Cmd + R : 대시보드 새로고침
    Ctrl/Cmd + E : 데이터 내보내기
    Ctrl/Cmd + 1 : 실시간 예측
    Ctrl/Cmd + 2 : 상세 분석
    Ctrl/Cmd + 3 : 월별 계약 권고
    Ctrl/Cmd + H : 이 도움말 보기
    ESC         : 결과 패널 닫기
    `;
    
    alert(shortcuts);
}

// === 차트 가시성 감지 ===
function checkChartVisibility() {
    const charts = [
        { element: document.getElementById('hourlyChart'), chart: hourlyChart },
        { element: document.getElementById('distributionChart'), chart: distributionChart },
        { element: document.getElementById('monthlyChart'), chart: monthlyChart },
        { element: document.getElementById('socChart'), chart: socChart }
    ];
    
    charts.forEach(({element, chart}) => {
        if (element && chart) {
            const rect = element.getBoundingClientRect();
            const isVisible = rect.top < window.innerHeight && rect.bottom > 0;
            
            if (isVisible && chart.options.animation) {
                // 차트가 보이면 애니메이션 활성화
                chart.options.animation.duration = 1000;
            }
        }
    });
}

// === 자동 새로고침 관련 함수들 ===
function startAutoRefresh() {
    // 기존 인터벌 제거
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    // 5분마다 자동 새로고침 (네트워크 상태 확인)
    autoRefreshInterval = setInterval(() => {
        if (!document.hidden && connectionStatus) {
            console.log('🔄 자동 새로고침 실행');
            refreshDashboard();
        } else {
            console.log('⏸️ 자동 새로고침 건너뜀 (페이지 숨김 또는 연결 끊어짐)');
        }
    }, 5 * 60 * 1000); // 5분
    
    console.log('✅ 자동 새로고침 시작 (5분 간격)');
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
        console.log('⏹️ 자동 새로고침 중지');
    }
}

// === 초기 데이터 로드 ===
async function loadInitialData() {
    console.log('📥 초기 데이터 로드 시작');
    
    try {
        // 충전소 정보 표시
        updateStationInfo();
        
        // 초기 차트 데이터 설정 (샘플 데이터)
        loadSampleData();
        
        // 잠시 대기 후 실제 데이터 로드 시도
        await delay(2000);
        await refreshDashboard();
        
    } catch (error) {
        console.error('❌ 초기 데이터 로드 실패:', error);
        showMessage('초기 데이터 로드에 실패했습니다. 샘플 데이터를 표시합니다.', 'warning');
        loadSampleData();
    }
}

function updateStationInfo() {
    console.log('🏢 충전소 정보 업데이트:', stationInfo);
    
    // 충전소 이름
    const stationNameElements = document.querySelectorAll('.station-name, #station-name, h2:contains("충전소")');
    stationNameElements.forEach(el => {
        if (el && el.textContent.includes('충전소')) {
            el.textContent = `🏢 ${stationInfo.name || '충전소'}`;
        }
    });
    
    // 다른 정보들도 안전하게 업데이트
    const infoMap = {
        '.station-id, #station-id': stationInfo.id || currentStationId,
        '.station-location, #station-location': stationInfo.location || '위치 정보 없음',
        '.charger-type, #charger-type': stationInfo.charger_type || '100kW 급속충전기',
        '.connector-type, #connector-type': stationInfo.connector_type || 'DC콤보'
    };
    
    Object.entries(infoMap).forEach(([selector, value]) => {
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => {
            if (el) el.textContent = value;
        });
    });
}

function loadSampleData() {
    console.log('📊 샘플 데이터 로드');
    
    try {
        // 시간대별 패턴 (더 현실적인 EV 충전 패턴)
        const hourlyPattern = [
            5, 8, 12, 18, 25, 35, 45, 55, 65, 70,  // 0-9시: 새벽/오전
            75, 80, 75, 70, 65, 60, 55, 50, 45, 40, // 10-19시: 낮/오후
            35, 25, 15, 8  // 20-23시: 저녁/밤
        ];
        
        if (hourlyChart) {
            safeUpdateChart(hourlyChart, hourlyPattern, 'line');
        }
        
        // 월별 예측 (계절성과 연휴 반영)
        const monthlyPredictions = [65, 70, 75, 80, 85, 90, 95, 90, 85, 80, 75, 70];
        if (monthlyChart) {
            safeUpdateChart(monthlyChart, monthlyPredictions, 'bar');
        }
        
        // SOC vs 전력 관계 (더 현실적인 분포)
        const socPowerData = [];
        for (let i = 0; i < 100; i++) {
            const soc = Math.random() * 100;
            // SOC가 낮을수록 높은 전력으로 충전
            const basePower = Math.max(20, 95 - (soc * 0.7));
            const noise = (Math.random() - 0.5) * 20;
            const power = Math.max(10, Math.min(100, basePower + noise));
            socPowerData.push({ x: parseFloat(soc.toFixed(1)), y: parseFloat(power.toFixed(1)) });
        }
        
        if (socChart) {
            safeUpdateChart(socChart, socPowerData, 'scatter');
        }
        
        // 전력 분포 (중간 전력 비중이 높은 현실적 분포)
        const powerDistribution = [25, 55, 20]; // 낮음, 중간, 높음
        if (distributionChart) {
            safeUpdateChart(distributionChart, powerDistribution, 'doughnut');
        }
        
        // 샘플 메트릭 업데이트 (애니메이션 포함)
        const sampleMetrics = {
            predicted_peak: 78.5,
            sessions_analyzed: 156,
            recommended_contract_kw: 85.0
        };
        
        updateMetricsWithAnimation(sampleMetrics);
        
        const sampleAnalysis = {
            performance_analysis: {
                average_session_power: 65.2,
                maximum_recorded_power: 98.7,
                utilization_rate: 78.5
            }
        };
        
        updateDetailedMetricsWithAnimation(sampleAnalysis);
        
        console.log('✅ 샘플 데이터 로드 완료');
        showMessage('샘플 데이터가 로드되었습니다', 'info');
        
    } catch (error) {
        console.error('❌ 샘플 데이터 로드 실패:', error);
        showMessage('샘플 데이터 로드에 실패했습니다', 'error');
    }
}

// === 데이터 검증 함수들 ===
function validateApiResponse(data, endpoint) {
    console.log(`🔍 API 응답 검증: ${endpoint}`, data);
    
    if (!data) {
        throw new Error('응답 데이터가 없습니다');
    }
    
    if (data.error) {
        throw new Error(data.error);
    }
    
    // 엔드포인트별 특별 검증
    const validations = {
        'predict': () => {
            if (data.predicted_peak === undefined) {
                console.warn('⚠️ 예측 전력 데이터 누락');
                return false;
            }
            if (data.predicted_peak < 0 || data.predicted_peak > 150) {
                console.warn('⚠️ 예측 전력 값이 비정상적입니다:', data.predicted_peak);
            }
            return true;
        },
        'station-analysis': () => {
            if (!data.charts_data) {
                console.warn('⚠️ 차트 데이터 누락');
                return false;
            }
            return true;
        },
        'monthly-contract': () => {
            if (!data.recommended_contract_kw) {
                console.warn('⚠️ 권고 계약 전력 데이터 누락');
                return false;
            }
            return true;
        }
    };
    
    const validator = Object.keys(validations).find(key => endpoint.includes(key));
    if (validator && validations[validator]) {
        validations[validator]();
    }
    
    console.log('✅ API 응답 유효성 확인 완료');
    return data;
}

// === 에러 처리 함수들 ===
function handleApiError(error, context) {
    console.error(`❌ ${context} 오류:`, error);
    
    let userMessage = '';
    let errorType = 'error';
    
    if (error.name === 'AbortError') {
        userMessage = '요청 시간이 초과되었습니다';
        errorType = 'warning';
    } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
        userMessage = '네트워크 연결을 확인해주세요';
        connectionStatus = false;
        updateConnectionStatus(false);
    } else if (error.message.includes('404')) {
        userMessage = '요청한 리소스를 찾을 수 없습니다';
    } else if (error.message.includes('500')) {
        userMessage = '서버 내부 오류가 발생했습니다';
    } else if (error.message.includes('503')) {
        userMessage = '서버가 일시적으로 사용할 수 없습니다';
        errorType = 'warning';
    } else {
        userMessage = error.message || '알 수 없는 오류가 발생했습니다';
    }
    
    showMessage(`${context}: ${userMessage}`, errorType);
}

// === 성능 모니터링 ===
function logPerformance(label, startTime) {
    const endTime = performance.now();
    const duration = (endTime - startTime).toFixed(2);
    console.log(`⏱️ ${label}: ${duration}ms`);
    
    // 성능이 느린 경우 경고
    if (duration > 5000) {
        console.warn(`⚠️ ${label} 성능 경고: ${duration}ms (5초 초과)`);
        showMessage(`${label}이 오래 걸렸습니다 (${(duration/1000).toFixed(1)}초)`, 'warning');
    }
}

// === 페이지 정리 함수 ===
function cleanup() {
    console.log('🧹 대시보드 정리 시작');
    
    // 자동 새로고침 중지
    stopAutoRefresh();
    
    // 차트 정리
    const charts = [
        { name: 'hourlyChart', instance: hourlyChart },
        { name: 'distributionChart', instance: distributionChart },
        { name: 'monthlyChart', instance: monthlyChart },
        { name: 'socChart', instance: socChart }
    ];
    
    charts.forEach(({name, instance}) => {
        try {
            if (instance) {
                instance.destroy();
                console.log(`✅ ${name} 정리 완료`);
            }
        } catch (error) {
            console.error(`❌ ${name} 정리 오류:`, error);
        }
    });
    
    // 전역 변수 초기화
    hourlyChart = null;
    distributionChart = null;
    monthlyChart = null;
    socChart = null;
    
    // 타이머 정리
    const timers = ['resizeTimeout', 'scrollTimeout'];
    timers.forEach(timer => {
        if (window[timer]) {
            clearTimeout(window[timer]);
            window[timer] = null;
        }
    });
    
    // 마지막 업데이트 시간 표시 제거
    const timeDisplay = document.getElementById('last-refresh-time');
    if (timeDisplay) {
        timeDisplay.remove();
    }
    
    console.log('✅ 대시보드 정리 완료');
}

// === 글로벌 이벤트 리스너 ===
window.addEventListener('beforeunload', cleanup);
window.addEventListener('unload', cleanup);

// 페이지 언로드 전 사용자에게 확인 (개발 중에만)
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.addEventListener('beforeunload', function(e) {
        if (autoRefreshInterval) {
            e.preventDefault();
            e.returnValue = '대시보드를 닫으시겠습니까?';
            return e.returnValue;
        }
    });
}

// === DOM 준비 완료 시 초기화 ===
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboard);
} else {
    // DOM이 이미 로드된 경우
    setTimeout(initializeDashboard, 100);
}

// === 전역 함수 노출 (콘솔에서 디버깅 용도) ===
window.dashboardDebug = {
    // 기본 함수들
    refreshDashboard,
    testRealtime,
    testMonthly,
    testAnalysis,
    exportData,
    
    // 상태 확인 함수들
    currentData: () => currentData,
    stationInfo: () => stationInfo,
    connectionStatus: () => connectionStatus,
    lastUpdateTime: () => lastUpdateTime,
    
    // 차트 인스턴스들
    charts: () => ({
        hourly: hourlyChart,
        distribution: distributionChart,
        monthly: monthlyChart,
        soc: socChart
    }),
    
    // 유틸리티 함수들
    showMessage,
    updateConnectionStatus,
    loadSampleData,
    cleanup,
    
    // 개발자 도구
    forceRefresh: () => {
        stopAutoRefresh();
        return refreshDashboard().then(() => startAutoRefresh());
    },
    
        simulateError: (type = 'network') => {
        const errors = {
            'network': new TypeError('Failed to fetch'),
            'timeout': new DOMException('Request timed out', 'TimeoutError'),
            'server': new Error('HTTP 500: Internal Server Error'),
            'data': { error: 'Invalid station ID' }
        };
        
        const error = errors[type] || errors['network'];
        handleApiError(error, '시뮬레이션 테스트');
    },
    
    // 성능 테스트
    performanceTest: async () => {
        console.log('🚀 성능 테스트 시작');
        const startTime = performance.now();
        
        try {
            await Promise.all([
                testRealtime(),
                testAnalysis(),
                testMonthly()
            ]);
            
            const endTime = performance.now();
            console.log(`✅ 성능 테스트 완료: ${(endTime - startTime).toFixed(2)}ms`);
            
        } catch (error) {
            console.error('❌ 성능 테스트 실패:', error);
        }
    }
};

console.log('🎯 완전히 개선된 Dashboard.js 로드 완료');
console.log('🔧 디버그 함수 사용법: window.dashboardDebug');
console.log('⌨️ 키보드 단축키: Ctrl+H로 도움말 확인');

document.head.appendChild(enhancedStyle);

setTimeout(() => {
    if (window.dashboardDebug) {
        console.log(`
🎉 EV 충전소 대시보드가 준비되었습니다!
📊 충전소: ${stationInfo.name} (${currentStationId})
🔄 자동 새로고침: 5분 간격
⌨️  키보드 단축키 지원
🌐 네트워크 상태 모니터링 활성화
🐛 디버그 모드: window.dashboardDebug 사용 가능

시작하려면 '대시보드 새로고침' 버튼을 클릭하거나 Ctrl+R을 누르세요.
        `);
        
        if (!sessionStorage.getItem('dashboard_welcomed')) {
            showMessage('대시보드가 준비되었습니다! Ctrl+H로 단축키를 확인하세요.', 'success');
            sessionStorage.setItem('dashboard_welcomed', 'true');
        }
    }
}, 3000);
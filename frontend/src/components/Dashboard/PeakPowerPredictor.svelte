<script>
    import { onMount, onDestroy } from 'svelte';
    import { Chart, registerables } from 'chart.js';
    import 'chartjs-adapter-date-fns';
    import MetricCard from './MetricCard.svelte';
    import LoadingSpinner from '../LoadingSpinner.svelte';

    // Chart.js 등록
    Chart.register(...registerables);

    export let stationId;
    export let prediction = null;
    export let analysis = null;
    export let monthlyContract = null;

    let isLoading = false;
    let lastUpdated = null;

    // 차트 관련 변수
    let chartCanvas;
    let chartInstance = null;

    // UI 상태 변수 - 백엔드에서 전처리된 데이터만 저장
    let chartData = [];
    let metrics = {
        lastMonthPeak: 0,
        nextMonthRecommended: 0,
        confidence: 0
    };
    let dataInfo = {
        startDate: null,
        endDate: null,
        recordCount: 0
    };
    
    // 고급 모델 예측 결과
    let advancedPrediction = null;
    let visualizationData = null;
    let modelComparisons = [];
    let showModelComparison = false;

    onMount(() => {
        loadAll();
    });

    onDestroy(() => {
        if (chartInstance) {
            chartInstance.destroy();
        }
    });

    async function loadAll() {
        isLoading = true;
        try {
            // 단일 API 호출로 모든 전처리된 데이터를 받음
            const response = await fetch(`/api/stations/${encodeURIComponent(stationId)}/prediction`, {
                cache: 'no-cache',
                signal: AbortSignal.timeout(15000)
            });
            
            if (!response.ok) {
                throw new Error(`API 호출 실패: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                // 백엔드에서 전처리된 데이터 직접 사용
                chartData = result.chart_data || [];
                metrics = {
                    lastMonthPeak: Math.round(result.last_month_peak || 0),
                    nextMonthRecommended: Math.round(result.recommended_contract_kw || 0),
                    confidence: Math.max(0, Math.min(1, result.confidence || 0))
                };
                dataInfo = {
                    startDate: result.data_start_date ? new Date(result.data_start_date) : null,
                    endDate: result.data_end_date ? new Date(result.data_end_date) : null,
                    recordCount: result.record_count || 0
                };
                
                // 고급 모델 결과 처리
                if (result.advanced_prediction) {
                    advancedPrediction = result.advanced_prediction;
                    visualizationData = result.visualization_data;
                    modelComparisons = result.advanced_prediction.models || [];
                    console.log(`고급 모델 ${advancedPrediction.model_count}개 사용, 최종 예측: ${advancedPrediction.final_prediction}kW`);
                }
                
                // DOM이 업데이트될 때까지 기다린 후 차트 생성
                setTimeout(() => {
                    createChart();
                }, 100);
                console.log(`전처리된 데이터 로드 완료: ${chartData.length}개월`);
            } else {
                throw new Error(result.error || '데이터 로드 실패');
            }
        } catch (e) {
            console.error('PeakPowerPredictor load error:', e);
            // 오류 시 기본값 설정
            chartData = [];
            metrics = { lastMonthPeak: 0, nextMonthRecommended: 0, confidence: 0 };
            dataInfo = { startDate: null, endDate: null, recordCount: 0 };
        } finally {
            isLoading = false;
            lastUpdated = new Date();
        }
    }



    function createChart() {
        console.log('createChart called - canvas:', !!chartCanvas, 'data length:', chartData.length);
        if (!chartCanvas) {
            console.warn('차트 생성 불가: canvas 없음');
            return;
        }

        // Canvas 크기 확인
        const rect = chartCanvas.getBoundingClientRect();
        console.log('Canvas size:', rect.width, 'x', rect.height);

        // 기존 차트 파괴
        if (chartInstance) {
            chartInstance.destroy();
        }

        // 데이터가 없을 때 빈 차트 생성
        if (!chartData.length) {
            console.warn('데이터가 없어 빈 차트를 생성합니다');
        }

        const ctx = chartCanvas.getContext('2d');

        // 백엔드에서 전처리된 데이터 직접 사용
        const actualData = chartData
            .filter(d => d && d.actual !== null && !isNaN(d.actual))
            .map(d => ({
                x: d.label || d.month,
                y: Number(d.actual)
            }));

        const predictedData = chartData
            .filter(d => d && d.predicted !== null && !isNaN(d.predicted))
            .map(d => ({
                x: d.label || d.month,
                y: Number(d.predicted)
            }));
            
        console.log('Actual data points:', actualData.length);
        console.log('Predicted data points:', predictedData.length);

        try {
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: [
                        {
                            label: '실제',
                            data: actualData,
                            borderColor: '#10b981',
                            backgroundColor: '#10b981',
                            borderWidth: 3,
                            pointRadius: 5,
                            pointHoverRadius: 7,
                            fill: false,
                            tension: 0.2
                        },
                        {
                            label: '예측',
                            data: predictedData,
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            borderWidth: 2,
                            pointRadius: 4,
                            pointHoverRadius: 6,
                            fill: true,
                            tension: 0.2,
                            borderDash: [5, 5]
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: '월별 최대 순간최고전력',
                            font: {
                                size: 20,
                                weight: 'bold'
                            },
                            padding: {
                                top: 10,
                                bottom: 30
                            }
                        },
                        legend: {
                            display: true,
                            position: 'top',
                            align: 'end',
                            labels: {
                                usePointStyle: true,
                                padding: 20,
                                font: {
                                    size: 12
                                }
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                            titleColor: '#374151',
                            bodyColor: '#374151',
                            borderColor: '#d1d5db',
                            borderWidth: 1,
                            cornerRadius: 8,
                            padding: 12,
                            callbacks: {
                                label: function(context) {
                                    return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}kW`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            type: 'category',
                            labels: chartData.length > 0 ? chartData.map(d => d.label || d.month) : ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                            title: {
                                display: true,
                                text: '월별',
                                font: {
                                    size: 14,
                                    weight: 'bold'
                                }
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)',
                                drawBorder: false
                            },
                            ticks: {
                                font: {
                                    size: 11
                                }
                            }
                        },
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: '전력 (kW)',
                                font: {
                                    size: 14,
                                    weight: 'bold'
                                }
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)',
                                drawBorder: false
                            },
                            ticks: {
                                font: {
                                    size: 11
                                },
                                callback: function(value) {
                                    return value + 'kW';
                                }
                            }
                        }
                    }
                }
            });
            console.log('Chart created successfully');
        } catch (error) {
            console.error('Chart creation failed:', error);
        }
    }

    // 유틸리티 함수 - UI 포맷팅만
    function fmtDate(d) {
        if (!d) return '-';
        const y = d.getFullYear();
        const m = String(d.getMonth()+1).padStart(2, '0');
        const da = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${da}`;
    }
</script>

<div class="peak-predictor">
    <div class="section-header">
        <h2>⚡ 순간 최고 전력 예측</h2>
        <div class="last-updated">
            {#if isLoading}
                <LoadingSpinner size="small" />
                <span>업데이트 중...</span>
            {:else if lastUpdated}
                <span>마지막 업데이트: {lastUpdated.toLocaleTimeString()}</span>
            {/if}
        </div>
    </div>

    <!-- 상단 3개 지표 카드 -->
    <div class="metrics-row">
        <MetricCard
            title="마지막달 최고 전력"
            value={metrics.lastMonthPeak}
            unit="kW"
            type="power"
        />
        <MetricCard
            title="다음달 권고계약 전력"
            value={metrics.nextMonthRecommended}
            unit="kW"
            type="contract"
        />
        <MetricCard
            title="예측 신뢰도"
            value={Math.round(metrics.confidence * 100)}
            unit="%"
            type="confidence"
        />
    </div>

    <!-- 데이터 범위/상태 -->
    <div class="data-range" aria-live="polite">
        {#if dataInfo.startDate && dataInfo.endDate}
            <span class="pill neutral">데이터 범위</span>
            <span
                >{fmtDate(dataInfo.startDate)} ~ {fmtDate(
                    dataInfo.endDate
                )}</span
            >
            <span class="sep">·</span>
            <span>레코드 {dataInfo.recordCount.toLocaleString()}개</span>
        {:else}
            <span class="pill warn">데이터 없음</span>
            <span>기본값으로 표시</span>
        {/if}
    </div>

    <!-- Chart.js 차트 -->
    <div class="chart-card">
        <div class="chart-container">
            <canvas bind:this={chartCanvas}></canvas>
        </div>
        {#if isLoading || chartData.length === 0}
            <div class="loading-placeholder">
                <LoadingSpinner />
                <p>차트 데이터 로딩 중...</p>
            </div>
        {/if}
    </div>

    <!-- 고급 모델 비교 섹션 -->
    {#if advancedPrediction && modelComparisons.length > 0}
        <div class="advanced-models-section">
            <div class="section-header">
                <h3>🤖 통계 모델 비교</h3>
                <button 
                    class="toggle-button" 
                    on:click={() => showModelComparison = !showModelComparison}
                    aria-expanded={showModelComparison}
                >
                    {showModelComparison ? '숨기기' : '모델 비교 보기'}
                </button>
            </div>
            
            <!-- 앙상블 결과 요약 -->
            <div class="ensemble-summary">
                <div class="summary-card">
                    <span class="label">사용된 모델 수</span>
                    <span class="value">{advancedPrediction.model_count}개</span>
                </div>
                <div class="summary-card">
                    <span class="label">앙상블 방법</span>
                    <span class="value">{advancedPrediction.ensemble_method}</span>
                </div>
                <div class="summary-card">
                    <span class="label">예측 불확실성</span>
                    <span class="value">{advancedPrediction.uncertainty.toFixed(1)}kW</span>
                </div>
            </div>

            {#if showModelComparison}
                <!-- 모델별 비교 테이블 -->
                <div class="models-comparison">
                    <h4>개별 모델 예측 결과</h4>
                    <div class="models-table">
                        <div class="table-header">
                            <span>모델명</span>
                            <span>예측값 (kW)</span>
                            <span>신뢰도</span>
                            <span>가중치</span>
                            <span>설명</span>
                        </div>
                        {#each modelComparisons as model}
                            <div class="table-row">
                                <span class="model-name">{model.name.replace(/_/g, ' ')}</span>
                                <span class="prediction-value">{model.prediction}</span>
                                <span class="confidence">
                                    <div class="confidence-bar">
                                        <div 
                                            class="confidence-fill" 
                                            style="width: {model.confidence * 100}%"
                                        ></div>
                                    </div>
                                    {(model.confidence * 100).toFixed(0)}%
                                </span>
                                <span class="weight">
                                    {(advancedPrediction.model_weights[model.name] * 100).toFixed(1)}%
                                </span>
                                <span class="description">{model.method}</span>
                            </div>
                        {/each}
                    </div>
                </div>

                <!-- 데이터 히스토그램 (가능하면) -->
                {#if visualizationData && visualizationData.histogram}
                    <div class="data-histogram">
                        <h4>원본 데이터 분포</h4>
                        <div class="histogram-info">
                            <div class="stat-item">
                                <span>평균:</span> 
                                <span>{visualizationData.statistics.mean?.toFixed(1)}kW</span>
                            </div>
                            <div class="stat-item">
                                <span>최대:</span> 
                                <span>{visualizationData.statistics.max?.toFixed(1)}kW</span>
                            </div>
                            <div class="stat-item">
                                <span>95%ile:</span> 
                                <span>{visualizationData.statistics.percentile_95?.toFixed(1)}kW</span>
                            </div>
                            <div class="stat-item">
                                <span>99%ile:</span> 
                                <span>{visualizationData.statistics.percentile_99?.toFixed(1)}kW</span>
                            </div>
                        </div>
                    </div>
                {/if}
            {/if}
        </div>
    {/if}
</div>

<style>
    .peak-predictor {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .section-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
    }

    .section-header h2 {
        margin: 0;
        font-size: 1.2rem;
    }

    .last-updated {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        color: var(--text-secondary);
        font-size: 0.9rem;
    }

    .metrics-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 12px;
    }

    .data-range {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 8px;
        font-size: 0.92rem;
        color: var(--text-secondary);
    }

    .data-range .pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border-radius: 999px;
        padding: 4px 8px;
        font-size: 0.78rem;
        border: 1px solid var(--border-color);
        background: var(--bg-secondary);
        color: var(--text-primary);
    }

    .pill.neutral {
        background: #eef2ff;
        color: #4f46e5;
        border-color: #c7d2fe;
    }

    .pill.warn {
        background: #fff7ed;
        color: #c2410c;
        border-color: #fed7aa;
    }

    .data-range .sep {
        opacity: 0.6;
    }

    .chart-card {
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 2px 8px var(--shadow);
        min-height: 400px;
    }

    .chart-container {
        position: relative;
        height: 400px;
        width: 100%;
    }

    .loading-placeholder {
        display: grid;
        place-items: center;
        padding: 60px 24px;
        color: var(--text-secondary);
        font-size: 0.95rem;
        min-height: 300px;
    }

    @media (min-width: 768px) {
        .chart-card {
            padding: 24px;
        }

        .chart-container {
            height: 450px;
        }
    }

    /* 고급 모델 비교 스타일 */
    .advanced-models-section {
        margin-top: 24px;
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 2px 8px var(--shadow);
    }

    .advanced-models-section h3 {
        margin: 0 0 16px 0;
        font-size: 1.1rem;
        color: var(--text-primary);
    }

    .toggle-button {
        background: var(--primary-color);
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 8px;
        cursor: pointer;
        font-size: 0.9rem;
        transition: background-color 0.2s;
    }

    .toggle-button:hover {
        background: var(--primary-hover);
    }

    .ensemble-summary {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin: 16px 0;
    }

    .summary-card {
        display: flex;
        flex-direction: column;
        align-items: center;
        background: var(--bg-primary);
        padding: 12px;
        border-radius: 8px;
        border: 1px solid var(--border-color);
    }

    .summary-card .label {
        font-size: 0.85rem;
        color: var(--text-secondary);
        margin-bottom: 4px;
    }

    .summary-card .value {
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .models-comparison {
        margin-top: 20px;
    }

    .models-comparison h4 {
        margin: 0 0 12px 0;
        font-size: 1rem;
        color: var(--text-primary);
    }

    .models-table {
        display: grid;
        gap: 8px;
        background: var(--bg-primary);
        border-radius: 8px;
        padding: 16px;
        border: 1px solid var(--border-color);
    }

    .table-header, .table-row {
        display: grid;
        grid-template-columns: 2fr 1fr 1.5fr 1fr 3fr;
        gap: 12px;
        align-items: center;
        padding: 8px 0;
    }

    .table-header {
        font-weight: 600;
        color: var(--text-secondary);
        border-bottom: 1px solid var(--border-color);
        font-size: 0.9rem;
    }

    .table-row {
        border-bottom: 1px solid rgba(0, 0, 0, 0.05);
        font-size: 0.9rem;
    }

    .table-row:last-child {
        border-bottom: none;
    }

    .model-name {
        font-weight: 500;
        color: var(--text-primary);
    }

    .prediction-value {
        font-weight: 600;
        color: var(--primary-color);
    }

    .confidence {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .confidence-bar {
        width: 40px;
        height: 8px;
        background: rgba(0, 0, 0, 0.1);
        border-radius: 4px;
        overflow: hidden;
    }

    .confidence-fill {
        height: 100%;
        background: linear-gradient(90deg, #ef4444, #f59e0b, #10b981);
        border-radius: 4px;
        transition: width 0.3s ease;
    }

    .weight {
        font-weight: 500;
        color: var(--text-secondary);
    }

    .description {
        color: var(--text-secondary);
        font-size: 0.85rem;
        line-height: 1.2;
    }

    .data-histogram {
        margin-top: 20px;
        padding: 16px;
        background: var(--bg-primary);
        border-radius: 8px;
        border: 1px solid var(--border-color);
    }

    .data-histogram h4 {
        margin: 0 0 12px 0;
        font-size: 1rem;
        color: var(--text-primary);
    }

    .histogram-info {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 12px;
    }

    .stat-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        background: var(--bg-secondary);
        border-radius: 6px;
        font-size: 0.9rem;
    }

    .stat-item span:first-child {
        color: var(--text-secondary);
        font-weight: 500;
    }

    .stat-item span:last-child {
        color: var(--text-primary);
        font-weight: 600;
    }

    @media (min-width: 1024px) {
        .metrics-row {
            gap: 16px;
        }

        .chart-card {
            padding: 30px;
        }

        .chart-container {
            height: 500px;
        }

        .advanced-models-section {
            padding: 24px;
        }

        .models-table {
            padding: 20px;
        }

        .table-header, .table-row {
            grid-template-columns: 2.5fr 1fr 1.5fr 1fr 4fr;
            gap: 16px;
        }
    }

    @media (max-width: 768px) {
        .table-header, .table-row {
            grid-template-columns: 1fr;
            gap: 4px;
            text-align: left;
        }

        .table-header span, .table-row span {
            padding: 4px 8px;
        }

        .table-header span:before, .table-row span:before {
            content: attr(data-label) ": ";
            font-weight: 600;
            display: inline;
        }

        .ensemble-summary {
            grid-template-columns: 1fr;
            gap: 8px;
        }

        .histogram-info {
            grid-template-columns: 1fr;
            gap: 8px;
        }
    }
</style>

<script>
    import { onMount, onDestroy } from "svelte";
    import { Chart, registerables } from "chart.js";
    import zoomPlugin from "chartjs-plugin-zoom";
    import "chartjs-adapter-date-fns";
    import MetricCard from "./MetricCard.svelte";
    import LoadingSpinner from "../LoadingSpinner.svelte";

    // Chart.js 등록 (zoom 플러그인 포함)
    Chart.register(...registerables, zoomPlugin);

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
        confidence: 0,
        algorithmPrediction: 0,
        predictionExceedsLimit: false,
    };
    let dataInfo = {
        startDate: null,
        endDate: null,
        recordCount: 0,
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
            const response = await fetch(
                `/api/stations/${encodeURIComponent(stationId)}/prediction`,
                {
                    cache: "no-cache",
                    signal: AbortSignal.timeout(15000),
                }
            );

            if (!response.ok) {
                throw new Error(`API 호출 실패: ${response.status}`);
            }

            const result = await response.json();

            if (result.success) {
                // 백엔드에서 전처리된 데이터 직접 사용
                chartData = result.chart_data || [];

                // 고급 예측 모델 결과 처리
                if (result.advanced_model_prediction) {
                    const advModel = result.advanced_model_prediction;
                    const rawPrediction = advModel.raw_prediction || 0; // 알고리즘 원본 예측값
                    const finalPrediction = advModel.final_prediction || 0; // 제한 적용된 권고값

                    // 제한 초과 여부 계산
                    const predictionExceedsLimit =
                        rawPrediction > finalPrediction;

                    metrics = {
                        lastMonthPeak: Math.round(
                            result.last_month_peak || result.current_peak || 0
                        ),
                        nextMonthRecommended: Math.round(finalPrediction), // 권고 계약 전력
                        confidence: Math.max(
                            0,
                            Math.min(1, result.confidence || 0)
                        ),
                        algorithmPrediction: Math.round(rawPrediction), // 알고리즘 예측값
                        predictionExceedsLimit: predictionExceedsLimit,
                    };

                    // 고급 모델 예측 결과 저장
                    advancedPrediction = {
                        model_count: advModel.model_predictions?.length || 0,
                        final_prediction: finalPrediction,
                        raw_prediction: rawPrediction,
                        ensemble_method:
                            advModel.ensemble_method || "weighted_confidence",
                        uncertainty: advModel.uncertainty || 0,
                    };

                    // 시각화 데이터 저장
                    visualizationData = advModel.visualization_data || null;
                } else {
                    // 고급 모델이 없는 경우 기존 방식 사용
                    const contractRecommendation =
                        monthlyContract?.recommended_contract_kw ||
                        result.recommended_contract_kw ||
                        0;
                    const algorithmPrediction =
                        result.algorithm_prediction_kw ||
                        contractRecommendation;

                    metrics = {
                        lastMonthPeak: Math.round(
                            result.last_month_peak || result.current_peak || 0
                        ),
                        nextMonthRecommended: Math.round(
                            contractRecommendation
                        ),
                        confidence: Math.max(
                            0,
                            Math.min(1, result.confidence || 0)
                        ),
                        algorithmPrediction: Math.round(algorithmPrediction),
                        predictionExceedsLimit:
                            result.prediction_exceeds_limit || false,
                    };
                }
                dataInfo = {
                    startDate: result.data_start_date
                        ? new Date(result.data_start_date)
                        : null,
                    endDate: result.data_end_date
                        ? new Date(result.data_end_date)
                        : null,
                    recordCount: result.record_count || 0,
                };

                // 고급 모델 결과 처리
                if (result.advanced_prediction) {
                    advancedPrediction = result.advanced_prediction;
                    visualizationData = result.visualization_data;
                    modelComparisons = result.advanced_prediction.models || [];
                }

                // DOM이 업데이트될 때까지 기다린 후 차트 생성
                setTimeout(() => {
                    createChart();
                }, 100);
            } else {
                throw new Error(result.error || "데이터 로드 실패");
            }
        } catch (e) {
            // 오류 시 기본값 설정
            chartData = [];
            metrics = {
                lastMonthPeak: 0,
                nextMonthRecommended: 0,
                confidence: 0,
            };
            dataInfo = { startDate: null, endDate: null, recordCount: 0 };
        } finally {
            isLoading = false;
            lastUpdated = new Date();
        }
    }

    function resetZoom() {
        if (chartInstance) {
            chartInstance.resetZoom();
        }
    }

    function createChart() {
        if (!chartCanvas) {
            return;
        }

        // Canvas 크기 확인
        const rect = chartCanvas.getBoundingClientRect();

        // 기존 차트 파괴
        if (chartInstance) {
            chartInstance.destroy();
        }

        // 데이터가 없으면 차트 생성하지 않음
        if (!chartData.length) {
            return;
        }

        const ctx = chartCanvas.getContext("2d");

        // 백엔드에서 전처리된 데이터 직접 사용
        const actualData = chartData
            .filter((d) => d && d.actual !== null && !isNaN(d.actual))
            .map((d) => ({
                x: d.label || d.month,
                y: Number(d.actual),
            }));

        const predictedData = chartData
            .filter((d) => d && d.predicted !== null && !isNaN(d.predicted))
            .map((d) => ({
                x: d.label || d.month,
                y: Number(d.predicted),
            }));

        try {
            chartInstance = new Chart(ctx, {
                type: "line",
                data: {
                    datasets: [
                        {
                            label: "실제",
                            data: actualData,
                            borderColor: "#10b981",
                            backgroundColor: "#10b981",
                            borderWidth: 3,
                            pointRadius: 5,
                            pointHoverRadius: 7,
                            fill: false,
                            tension: 0.2,
                        },
                        {
                            label: "예측",
                            data: predictedData,
                            borderColor: "#3b82f6",
                            backgroundColor: "rgba(59, 130, 246, 0.1)",
                            borderWidth: 2,
                            pointRadius: 4,
                            pointHoverRadius: 6,
                            fill: true,
                            tension: 0.2,
                            borderDash: [5, 5],
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: "index",
                        intersect: false,
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: "top",
                            align: "end",
                            labels: {
                                usePointStyle: true,
                                padding: 20,
                                font: {
                                    size: 12,
                                },
                            },
                        },
                        tooltip: {
                            backgroundColor: "rgba(255, 255, 255, 0.95)",
                            titleColor: "#374151",
                            bodyColor: "#374151",
                            borderColor: "#d1d5db",
                            borderWidth: 1,
                            cornerRadius: 8,
                            padding: 12,
                            callbacks: {
                                label: function (context) {
                                    return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}kW`;
                                },
                            },
                        },
                        zoom: {
                            limits: {
                                x: { min: "original", max: "original" },
                                y: { min: "original", max: "original" },
                            },
                            pan: {
                                enabled: true,
                                mode: "xy",
                                onPanComplete({ chart }) {},
                            },
                            zoom: {
                                wheel: {
                                    enabled: true,
                                    speed: 0.1,
                                },
                                pinch: {
                                    enabled: true,
                                },
                                mode: "xy",
                                onZoomComplete({ chart }) {},
                            },
                        },
                    },
                    scales: {
                        x: {
                            type: "category",
                            labels:
                                chartData.length > 0
                                    ? chartData.map((d) => d.label || d.month)
                                    : [],
                            title: {
                                display: true,
                                text: "월별",
                                font: {
                                    size: 14,
                                    weight: "bold",
                                },
                            },
                            grid: {
                                color: "rgba(0, 0, 0, 0.1)",
                                drawBorder: false,
                            },
                            ticks: {
                                font: {
                                    size: 11,
                                },
                            },
                        },
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: "전력 (kW)",
                                font: {
                                    size: 14,
                                    weight: "bold",
                                },
                            },
                            grid: {
                                color: "rgba(0, 0, 0, 0.1)",
                                drawBorder: false,
                            },
                            ticks: {
                                font: {
                                    size: 11,
                                },
                                callback: function (value) {
                                    return value + "kW";
                                },
                            },
                        },
                    },
                },
            });
        } catch (error) {}
    }

    // 유틸리티 함수 - UI 포맷팅만
    function fmtDate(d) {
        if (!d) return "-";
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const da = String(d.getDate()).padStart(2, "0");
        return `${y}-${m}-${da}`;
    }
</script>

<div class="peak-predictor">
    <div class="section-header">
        <h2>순간 최고 전력 예측</h2>
        <div class="last-updated">
            {#if isLoading}
                <LoadingSpinner size="small" />
                <span>업데이트 중...</span>
            {:else if lastUpdated}
                <span>마지막 업데이트: {lastUpdated.toLocaleTimeString()}</span>
            {/if}
        </div>
    </div>

    <!-- 상단 지표 카드 -->
    <div class="metrics-row">
        <MetricCard
            title="마지막달 최고 전력"
            value={metrics.lastMonthPeak}
            unit="kW"
            type="power"
            tooltip="지난 달 충전소에서 기록된 최대 순간 전력 사용량"
        />
        <MetricCard
            title="다음달 권고계약 전력"
            value={metrics.nextMonthRecommended}
            unit="kW"
            type="contract"
            tooltip="예측된 최고전력 + 안전마진으로 계산한 권고값

• 안전마진: 8-20% (데이터 품질에 따라 조정)
• 충전기별 제한:
  - 완속충전기: 최대 7kW
  - 급속충전기: 최대 100kW"
        />
        <MetricCard
            title="예측 신뢰도"
            value={Math.round(metrics.confidence * 100)}
            unit="%"
            type="confidence"
            tooltip="예측 모델의 신뢰성 지표 (0-100%)

• 계산 요소: 데이터 품질, 모델 불확실성, 패턴 일관성
• 해석 기준:
  - 70% 이상: 높은 신뢰도
  - 50-70%: 보통 신뢰도  
  - 50% 미만: 낮은 신뢰도"
        />
        <MetricCard
            title="알고리즘 예측값"
            value={metrics.algorithmPrediction}
            unit="kW"
            type={metrics.algorithmPrediction > 100 ? "algorithm-exceeded" : "algorithm"}
            subtitle={metrics.algorithmPrediction > 100 ? "100kW 제한 초과" : "예측 범위 내"}
            tooltip="순수한 알고리즘 예측값

• 제한 없이 계산된 원시 예측 결과
• 100kW 초과 시 계약전력 제한 적용됨
• 실제 권고값은 충전기 타입별 제한 반영"
        />
    </div>

    <!-- 데이터 범위/상태 -->
    <div class="data-range" aria-live="polite">
        {#if dataInfo.startDate && dataInfo.endDate}
            <div class="data-info-grid">
                <div class="data-info-card">
                    <span class="pill neutral">실제 데이터</span>
                    <div class="date-range">
                        <div class="date-item">
                            <span class="date-label">시작:</span>
                            <span class="date-value">{fmtDate(dataInfo.startDate)}</span>
                        </div>
                        <div class="date-separator">~</div>
                        <div class="date-item">
                            <span class="date-label">종료:</span>
                            <span class="date-value">{fmtDate(dataInfo.endDate)}</span>
                        </div>
                    </div>
                </div>
                <div class="data-stats-card">
                    <span class="pill stats">데이터 통계</span>
                    <div class="stats-info">
                        <span>총 {(dataInfo.recordCount || 0).toLocaleString()}개 레코드</span>
                        <span class="sep">·</span>
                        <span>기간 {Math.ceil((new Date(dataInfo.endDate) - new Date(dataInfo.startDate)) / (1000 * 60 * 60 * 24))}일</span>
                    </div>
                </div>
            </div>
        {:else}
            <span class="pill warn">데이터 없음</span>
            <span>해당 충전소({stationId}) CSV 데이터 미발견</span>
        {/if}
    </div>

    <!-- Chart.js 차트 -->
    <div class="chart-card">
        <div class="chart-header">
            <h3>월별 최대 순간최고전력 추이</h3>
            <div class="chart-controls">
                <button
                    class="zoom-reset-btn"
                    on:click={resetZoom}
                    title="줌 초기화"
                >
                    원래대로
                </button>
            </div>
        </div>
        <div class="chart-container">
            <canvas bind:this={chartCanvas}></canvas>
        </div>
        {#if isLoading}
            <div class="loading-placeholder">
                <LoadingSpinner />
                <p>차트 데이터 로딩 중...</p>
            </div>
        {:else if chartData.length === 0}
            <div class="no-chart-data">
                <div class="no-data-icon">📊</div>
                <h4>차트 데이터 없음</h4>
                <p>
                    해당 충전소({stationId})의 전력 사용 데이터를 불러올 수
                    없습니다.
                </p>
            </div>
        {/if}
    </div>
</div>

<style>
    .peak-predictor {
        display: flex;
        flex-direction: column;
        gap: 24px;
        padding: 24px;
        background: transparent;
    }

    .section-header {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 16px;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 1px solid var(--border-color);
    }

    .section-header h2 {
        display: none;
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
        margin: 16px 0;
    }

    .data-info-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
    }

    .data-info-card, .data-stats-card {
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 4px var(--shadow);
    }

    .date-range {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-top: 12px;
        font-size: 0.9rem;
    }

    .date-item {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .date-label {
        color: var(--text-secondary);
        font-size: 0.8rem;
        font-weight: 500;
    }

    .date-value {
        color: var(--text-primary);
        font-weight: 600;
        font-family: 'Courier New', monospace;
    }

    .date-separator {
        color: var(--text-secondary);
        font-weight: bold;
        padding: 0 4px;
    }

    .stats-info {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 12px;
        font-size: 0.9rem;
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

    .pill.stats {
        background: #f0fdf4;
        color: #16a34a;
        border-color: #bbf7d0;
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

    .chart-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--border-color);
    }

    .chart-header h3 {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .chart-controls {
        display: flex;
        gap: 8px;
    }

    .zoom-reset-btn {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 12px;
        background: var(--primary-color);
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    .zoom-reset-btn:hover {
        background: var(--primary-dark);
        transform: translateY(-1px);
        box-shadow: 0 2px 8px var(--shadow);
    }

    .zoom-reset-btn svg {
        width: 16px;
        height: 16px;
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

    .no-chart-data {
        display: grid;
        place-items: center;
        padding: 60px 24px;
        text-align: center;
        min-height: 300px;
    }

    .no-chart-data .no-data-icon {
        font-size: 2.5em;
        margin-bottom: 12px;
        opacity: 0.6;
    }

    .no-chart-data h4 {
        margin: 0 0 8px 0;
        color: var(--text-primary);
        font-size: 1.1em;
        font-weight: 600;
    }

    .no-chart-data p {
        margin: 0;
        color: var(--text-secondary);
        font-size: 0.9em;
        line-height: 1.4;
    }

    @media (min-width: 768px) {
        .chart-card {
            padding: 24px;
        }

        .chart-container {
            height: 450px;
        }
    }

    @media (max-width: 768px) {
        .data-info-grid {
            grid-template-columns: 1fr;
            gap: 12px;
        }

        .date-range {
            flex-direction: column;
            align-items: flex-start;
            gap: 8px;
        }

        .date-item {
            flex-direction: row;
            gap: 8px;
            align-items: center;
        }

        .stats-info {
            flex-direction: column;
            align-items: flex-start;
            gap: 4px;
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

    .table-header,
    .table-row {
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

        .table-header,
        .table-row {
            grid-template-columns: 2.5fr 1fr 1.5fr 1fr 4fr;
            gap: 16px;
        }
    }

    @media (max-width: 768px) {
        .table-header,
        .table-row {
            grid-template-columns: 1fr;
            gap: 4px;
            text-align: left;
        }

        .table-header span,
        .table-row span {
            padding: 4px 8px;
        }

        .table-header span:before,
        .table-row span:before {
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

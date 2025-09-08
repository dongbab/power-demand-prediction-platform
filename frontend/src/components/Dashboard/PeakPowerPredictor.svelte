<script>
    import { onMount, onDestroy } from "svelte";
    import MetricCard from "./MetricCard.svelte";
    import LoadingSpinner from "../LoadingSpinner.svelte";

    // Chart.js는 클라이언트에서만 동적 로드
    let Chart;

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

    // Method comparison data
    let methodComparison = null;
    let showMethodComparison = false;

    onMount(async () => {
        // 브라우저 환경에서만 실행
        if (typeof window === "undefined") return;

        try {
            // Chart.js와 플러그인들 동적 로드
            const [{ default: ChartJS }, dateAdapter, zoomPlugin] =
                await Promise.all([
                    import("chart.js/auto"),
                    import("chartjs-adapter-date-fns"),
                    import("chartjs-plugin-zoom"),
                ]);

            Chart = ChartJS;
            Chart.register(zoomPlugin.default);

            // 데이터 로드
            loadAll();
        } catch (error) {
            console.error("Chart.js 로드 실패:", error);
        }
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
                    let rawPrediction = advModel.raw_prediction || 0; // 알고리즘 원본 예측값

                    // 비정상적으로 큰 값이면 단위 변환 (와트 → 킬로와트)
                    if (rawPrediction > 100000) {
                        console.warn(
                            "비정상적으로 큰 예측값 감지:",
                            rawPrediction,
                            "-> kW로 변환"
                        );
                        rawPrediction = rawPrediction / 1000;
                    }

                    // 여전히 비정상적으로 크면 제한
                    if (rawPrediction > 10000) {
                        console.warn(
                            "여전히 비정상적으로 큰 값:",
                            rawPrediction,
                            "-> 10000kW로 제한"
                        );
                        rawPrediction = 10000;
                    }
                    const finalPrediction = advModel.final_prediction || 0; // 제한 적용된 권고값

                    console.log("PeakPowerPredictor - API 원본 데이터:", {
                        rawPrediction,
                        finalPrediction,
                        advModel,
                    });

                    // 제한 초과 여부 계산
                    const predictionExceedsLimit =
                        rawPrediction > finalPrediction;

                    metrics = {
                        lastMonthPeak: parseFloat(
                            (
                                result.last_month_peak ||
                                result.current_peak ||
                                0
                            ).toFixed(1)
                        ),
                        nextMonthRecommended: parseFloat(
                            finalPrediction.toFixed(1)
                        ), // 소수점 1자리
                        confidence: Math.max(
                            0,
                            Math.min(1, result.confidence || 0)
                        ),
                        algorithmPrediction: parseFloat(
                            rawPrediction.toFixed(1)
                        ), // 소수점 1자리
                        predictionExceedsLimit: predictionExceedsLimit,
                    };

                    console.log("PeakPowerPredictor - 계산된 메트릭:", {
                        originalRawPrediction: rawPrediction,
                        roundedAlgorithmPrediction: Math.round(rawPrediction),
                        finalMetrics: metrics,
                    });

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
                    const algorithmPrediction = Math.min(
                        result.algorithm_prediction_kw ||
                            contractRecommendation,
                        10000
                    ); // 최대 10000kW 제한

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
                        algorithmPrediction: Math.round(
                            Math.min(algorithmPrediction, 10000)
                        ),
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

                // Method comparison data processing
                if (result.method_comparison) {
                    methodComparison = result.method_comparison;
                    console.log("Method comparison data:", methodComparison);
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
        // 브라우저 환경 체크
        if (typeof window === "undefined" || !Chart) return;

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

        // 날짜 변환 헬퍼 함수
        const convertToYearMonth = (dateStr) => {
            if (!dateStr) return null;
            if (dateStr.includes(".")) {
                // yy.mm 형태를 yyyy-mm로 변환
                const [year, month] = dateStr.split(".");
                const fullYear = year.length === 2 ? `20${year}` : year;
                return `${fullYear}-${month.padStart(2, "0")}`;
            } else if (dateStr.includes("-") && dateStr.length >= 7) {
                // 이미 yyyy-mm 형태거나 yyyy-mm-dd 형태인 경우
                return dateStr.substring(0, 7); // yyyy-mm만 추출
            }
            return dateStr;
        };

        // 실제 데이터 처리
        const actualData = chartData
            .filter((d) => d && d.actual !== null && !isNaN(d.actual))
            .map((d) => {
                const xValue = convertToYearMonth(d.month || d.label);
                return {
                    x: xValue,
                    y: Number(d.actual),
                };
            })
            .filter((d) => d.x); // null 값 제거

        // 실제 데이터의 마지막 시점 찾기
        const actualDataSorted = [...actualData].sort((a, b) =>
            a.x.localeCompare(b.x)
        );
        const lastActualMonth =
            actualDataSorted.length > 0
                ? actualDataSorted[actualDataSorted.length - 1].x
                : null;

        console.log("실제 데이터 마지막 월:", lastActualMonth);
        console.log(
            "실제 데이터 전체:",
            actualDataSorted.map((d) => d.x)
        );

        // Dynamic Pattern 예측 데이터 처리 (실제 데이터 이후만)
        const predictedData = chartData
            .filter((d) => d && d.predicted !== null && !isNaN(d.predicted))
            .map((d) => {
                const xValue = convertToYearMonth(d.month || d.label);
                return {
                    x: xValue,
                    y: Number(d.predicted),
                };
            })
            .filter((d) => d.x && (!lastActualMonth || d.x > lastActualMonth)); // 실제 데이터 이후만

        console.log(
            "Dynamic Pattern 예측 데이터:",
            predictedData.map((d) => d.x)
        );

        // 모든 x 값을 수집하고 정렬
        const allXValues = new Set();
        actualData.forEach((d) => allXValues.add(d.x));
        predictedData.forEach((d) => allXValues.add(d.x));

        const sortedXValues = Array.from(allXValues).sort();

        console.log("전체 X 값들 (정렬됨):", sortedXValues);

        // 데이터셋 구성
        const datasets = [];

        // 실제 데이터 - 항상 포함
        if (actualData.length > 0) {
            datasets.push({
                label: "실제 데이터",
                data: actualData,
                borderColor: "#10b981",
                backgroundColor: "#10b981",
                borderWidth: 3,
                pointRadius: 5,
                pointHoverRadius: 7,
                fill: false,
                tension: 0.2,
                spanGaps: false,
            });
        }

        // 적응형 예측 데이터 - 실제 데이터 이후만
        if (predictedData.length > 0) {
            datasets.push({
                label: "적응형 예측",
                data: predictedData,
                borderColor: "#3b82f6",
                backgroundColor: "rgba(59, 130, 246, 0.1)",
                borderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                fill: true,
                tension: 0.2,
                borderDash: [5, 5],
                spanGaps: false,
            });
        }

        try {
            chartInstance = new Chart(ctx, {
                type: "line",
                data: {
                    datasets: datasets,
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
                                title: function (context) {
                                    return `${context[0].label} 월`;
                                },
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
                            labels: sortedXValues,
                            grid: {
                                color:
                                    document.documentElement.getAttribute(
                                        "data-theme"
                                    ) === "dark"
                                        ? "rgba(255, 255, 255, 0.05)"
                                        : "rgba(0, 0, 0, 0.1)",
                                drawBorder: false,
                            },
                            ticks: {
                                color:
                                    document.documentElement.getAttribute(
                                        "data-theme"
                                    ) === "dark"
                                        ? "#d1d5db"
                                        : "#4b5563",
                                font: {
                                    size: 11,
                                },
                                maxRotation: 45,
                                minRotation: 0,
                            },
                        },
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: "전력 (kW)",
                                color:
                                    document.documentElement.getAttribute(
                                        "data-theme"
                                    ) === "dark"
                                        ? "#e5e7eb"
                                        : "#374151",
                                font: {
                                    size: 14,
                                    weight: "bold",
                                },
                            },
                            grid: {
                                color:
                                    document.documentElement.getAttribute(
                                        "data-theme"
                                    ) === "dark"
                                        ? "rgba(255, 255, 255, 0.1)"
                                        : "rgba(0, 0, 0, 0.1)",
                                drawBorder: false,
                            },
                            ticks: {
                                color:
                                    document.documentElement.getAttribute(
                                        "data-theme"
                                    ) === "dark"
                                        ? "#d1d5db"
                                        : "#4b5563",
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
            title="다음 달 권고계약 전력"
            value={metrics.nextMonthRecommended}
            unit="kW"
            type={metrics.nextMonthRecommended >= 80
                ? "contract-high"
                : metrics.nextMonthRecommended >= 50
                  ? "contract-medium"
                  : "contract-low"}
            highlighted={true}
            tooltip="알고리즘 예측값 + 안전마진으로 계산한 권고값

• 안전마진: 8-20% (데이터 품질에 따라 조정)
• 충전기별 권고 계약 전력 제한:
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
            type={metrics.algorithmPrediction > 100
                ? "algorithm-exceeded"
                : "algorithm"}
            subtitle={metrics.algorithmPrediction > 100
                ? "100kW 제한 초과"
                : "예측 범위 내"}
            tooltip="순수한 알고리즘 예측값

• 제한 없이 계산된 원시 예측 결과
• 100kW 초과 시 계약전력 제한 적용됨
• 실제 권고값은 충전기 타입별 제한 반영"
        />
    </div>

    <!-- Chart.js 차트 -->
    <div class="chart-card">
        <div class="chart-header">
            <h3>월별 최대 순간최고전력 추이</h3>
            <div class="chart-meta">
                {#if dataInfo.startDate && dataInfo.endDate}
                    <div class="data-info">
                        <div class="data-period">
                            <svg
                                width="14"
                                height="14"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2"
                            >
                                <path d="M8 2v4"></path>
                                <path d="M16 2v4"></path>
                                <rect x="3" y="4" width="18" height="18" rx="2"
                                ></rect>
                                <path d="M3 10h18"></path>
                            </svg>
                            <span
                                >{fmtDate(dataInfo.startDate)} ~ {fmtDate(
                                    dataInfo.endDate
                                )}</span
                            >
                        </div>
                        <div class="data-stats">
                            <span class="stat-badge">
                                <svg
                                    width="12"
                                    height="12"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    stroke-width="2"
                                >
                                    <path d="M12 20V10"></path>
                                    <path d="M18 20V4"></path>
                                    <path d="M6 20v-6"></path>
                                </svg>
                                {(dataInfo.recordCount || 0).toLocaleString()}개
                            </span>
                            <span class="duration-badge">
                                {Math.ceil(
                                    (new Date(dataInfo.endDate) -
                                        new Date(dataInfo.startDate)) /
                                        (1000 * 60 * 60 * 24)
                                )}일
                            </span>
                        </div>
                    </div>
                {:else}
                    <div class="no-data-info">
                        <svg
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                        >
                            <path
                                d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
                            ></path>
                            <line x1="12" y1="9" x2="12" y2="13"></line>
                            <line x1="12" y1="17" x2="12.01" y2="17"></line>
                        </svg>
                        <span>충전소 {stationId} 데이터 불러올 수 없음</span>
                    </div>
                {/if}
                {#if lastUpdated}
                    <div class="last-updated-info">
                        <svg
                            width="12"
                            height="12"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                        >
                            <circle cx="12" cy="12" r="10"></circle>
                            <polyline points="12,6 12,12 16,14"></polyline>
                        </svg>
                        <span
                            >마지막 업데이트 : {lastUpdated.toLocaleTimeString()}</span
                        >
                    </div>
                {/if}
                <div class="chart-controls">
                    <button
                        class="zoom-reset-btn"
                        on:click={resetZoom}
                        title="줌 초기화"
                    >
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                        >
                            <path d="M3 3v18h18" />
                            <path d="M18.5 9.5L12 16l-4-4-3.5 3.5" />
                        </svg>
                        원래대로
                    </button>
                </div>
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

    <!-- Method Comparison Section -->
    {#if methodComparison}
        <div class="method-comparison-card">
            <div class="comparison-header">
                <h3>예측 방법 비교</h3>
                <button
                    class="toggle-btn"
                    on:click={() =>
                        (showMethodComparison = !showMethodComparison)}
                    class:active={showMethodComparison}
                >
                    {showMethodComparison ? "숨기기" : "자세히 보기"}
                    <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        class:rotated={showMethodComparison}
                    >
                        <path d="M6 9l6 6 6-6" />
                    </svg>
                </button>
            </div>

            {#if showMethodComparison}
                <div class="comparison-content">
                    {#if methodComparison}
                        <div class="comparison-methods">
                            <!-- Dynamic Pattern Method -->
                            <div class="method-card">
                                <div class="method-header">
                                    <div class="method-indicator dynamic"></div>
                                    <h4>Dynamic Pattern 예측</h4>
                                    <span class="confidence-badge dynamic">
                                        {Math.round(
                                            methodComparison.dynamic_patterns
                                                .confidence * 100
                                        )}%
                                    </span>
                                </div>
                                <div class="method-details">
                                    <div class="metric">
                                        <span class="label">예측값:</span>
                                        <span class="value"
                                            >{methodComparison.dynamic_patterns
                                                .predicted_value}kW</span
                                        >
                                    </div>
                                    <div class="metric">
                                        <span class="label">원본 예측:</span>
                                        <span class="value"
                                            >{Math.round(
                                                methodComparison
                                                    .dynamic_patterns
                                                    .raw_prediction
                                            )}kW</span
                                        >
                                    </div>
                                    <div class="metric">
                                        <span class="label">패턴 조정:</span>
                                        <span
                                            class="value status"
                                            class:applied={methodComparison
                                                .dynamic_patterns
                                                .applied_adjustments}
                                        >
                                            {methodComparison.dynamic_patterns
                                                .applied_adjustments
                                                ? "적용됨"
                                                : "미적용"}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    {/if}
                </div>
            {/if}
        </div>
    {/if}
</div>

<style>
    .peak-predictor {
        display: flex;
        flex-direction: column;
        gap: 24px;
        padding: 24px;
        background: transparent;
    }

    .metrics-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 12px;
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
        flex-direction: column;
        gap: 12px;
        margin-bottom: 16px;
        padding-bottom: 16px;
        border-bottom: 1px solid var(--border-color);
    }

    .chart-header h3 {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .chart-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
    }

    .data-info {
        display: flex;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
    }

    .data-period {
        display: flex;
        align-items: center;
        gap: 6px;
        color: var(--text-primary);
        font-size: 0.9rem;
    }

    .data-stats {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .stat-badge,
    .duration-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 500;
    }

    .stat-badge {
        background: rgba(16, 185, 129, 0.1);
        color: #059669;
        border: 1px solid rgba(16, 185, 129, 0.2);
    }

    .duration-badge {
        background: rgba(99, 102, 241, 0.1);
        color: #4f46e5;
        border: 1px solid rgba(99, 102, 241, 0.2);
    }

    .no-data-info {
        display: flex;
        align-items: center;
        gap: 6px;
        color: #f59e0b;
        font-size: 0.9rem;
        font-weight: 500;
    }

    .last-updated-info {
        display: flex;
        align-items: center;
        gap: 4px;
        color: var(--text-secondary);
        font-size: 0.85rem;
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

    /* 다크모드 지원 */
    :global([data-theme="dark"]) .data-info-card {
        --bg-secondary: #1f2937;
        --border-color: #374151;
        --shadow: rgba(0, 0, 0, 0.3);
        --shadow-hover: rgba(0, 0, 0, 0.5);
        --text-primary: #f9fafb;
        --text-secondary: #d1d5db;
        --primary-color: #6366f1;
    }

    /* 라이트모드 지원 */
    :global([data-theme="light"]) .data-info-card {
        --bg-secondary: #ffffff;
        --border-color: rgba(0, 0, 0, 0.1);
        --shadow: rgba(0, 0, 0, 0.05);
        --shadow-hover: rgba(0, 0, 0, 0.15);
        --text-primary: #111827;
        --text-secondary: #6b7280;
        --primary-color: #4f46e5;
    }

    /* 애니메이션 최적화 */
    @media (prefers-reduced-motion: reduce) {
        .data-info-card {
            transition: none !important;
        }
    }

    @media (max-width: 768px) {
        .chart-meta {
            flex-direction: column;
            align-items: flex-start;
            gap: 8px;
        }

        .data-info {
            flex-direction: column;
            align-items: flex-start;
            gap: 8px;
        }

        .data-stats {
            gap: 6px;
        }

        .stat-badge,
        .duration-badge {
            padding: 3px 6px;
            font-size: 0.75rem;
        }

        .last-updated-info {
            font-size: 0.8rem;
        }
    }

    /* Method Comparison Styles */
    .method-comparison-card {
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 2px 8px var(--shadow);
    }

    .comparison-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }

    .comparison-header h3 {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .toggle-btn {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        background: var(--bg-secondary);
        color: var(--text-secondary);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    .toggle-btn:hover {
        background: var(--primary-color);
        color: white;
        border-color: var(--primary-color);
    }

    .toggle-btn.active {
        background: var(--primary-color);
        color: white;
        border-color: var(--primary-color);
    }

    .toggle-btn svg {
        width: 16px;
        height: 16px;
        transition: transform 0.2s ease;
    }

    .toggle-btn svg.rotated {
        transform: rotate(180deg);
    }

    .comparison-content {
        border-top: 1px solid var(--border-color);
        padding-top: 16px;
    }

    .comparison-methods {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 16px;
    }

    .method-card {
        background: linear-gradient(
            135deg,
            var(--bg-secondary) 0%,
            rgba(var(--primary-rgb), 0.02) 100%
        );
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 16px;
        transition: all 0.2s ease;
    }

    .method-card:hover {
        box-shadow: 0 4px 12px var(--shadow);
        transform: translateY(-2px);
    }

    .method-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
    }

    .method-indicator {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .method-indicator.dynamic {
        background: #3b82f6;
        box-shadow: 0 0 8px rgba(59, 130, 246, 0.4);
    }

    .method-header h4 {
        margin: 0;
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary);
        flex-grow: 1;
    }

    .confidence-badge {
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
        color: white;
    }

    .confidence-badge.dynamic {
        background: #3b82f6;
    }

    .method-details {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .metric {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
    }

    .metric .label {
        font-size: 0.9rem;
        color: var(--text-secondary);
        font-weight: 500;
    }

    .metric .value {
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .metric .value.status {
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.8rem;
    }

    .metric .value.status.applied {
        background: rgba(34, 197, 94, 0.1);
        color: #16a34a;
    }

    .metric .value.status.success {
        background: rgba(34, 197, 94, 0.1);
        color: #16a34a;
    }

    .metric .value.status.error {
        background: rgba(239, 68, 68, 0.1);
        color: #dc2626;
    }

    .error-message {
        margin-top: 8px;
        padding: 8px;
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.2);
        border-radius: 6px;
        font-size: 0.85rem;
        color: #dc2626;
        line-height: 1.4;
    }
</style>

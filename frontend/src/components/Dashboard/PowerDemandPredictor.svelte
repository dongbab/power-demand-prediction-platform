<script>
    import { onMount, onDestroy, tick } from "svelte";
    import MetricCard from "./MetricCard.svelte";
    import DistributionChart from "./DistributionChart.svelte";
    import MonthlyChart from "./MonthlyChart.svelte";
    import LoadingSpinner from "../LoadingSpinner.svelte";

    export let stationId;
    export let analysis = null;

    let isLoading = false;
    let lastUpdated = null;
    let refreshInterval;
    let energyForecast = null;
    let selectedTimeframe = "90days";
    let chartContainer;

    // 데이터 범위 정보
    let dataRange = {
        startDate: null,
        endDate: null,
        recordCount: 0,
    };

    const timeframes = [
        { value: "30days", label: "30일" },
        { value: "90days", label: "90일" },
        { value: "180days", label: "6개월" },
        { value: "365days", label: "1년" },
    ];

    // Chart.js는 클라이언트에서만 동적 로드
    let Chart;
    let chart; // 차트 인스턴스

    onMount(async () => {
        try {
            // Chart.js와 time adapter, zoom plugin 로드 (클라이언트 전용)
            const [{ default: ChartJS }, { default: zoomPlugin }] =
                await Promise.all([
                    import("chart.js/auto"),
                    import("chartjs-adapter-date-fns"),
                    import("chartjs-plugin-zoom"),
                ]);
            Chart = ChartJS;
            Chart.register(zoomPlugin);

            // 초기 데이터 로드
            if (stationId) {
                await updateEnergyForecast();
            }
            // 5분마다 갱신
            refreshInterval = setInterval(updateEnergyForecast, 5 * 60 * 1000);
        } catch (error) {}
    });

    onDestroy(() => {
        try {
            if (refreshInterval) {
                clearInterval(refreshInterval);
            }
            // 차트 정리
            if (chart) {
                chart.destroy();
                chart = null;
            }
        } catch (error) {}
    });

    async function updateEnergyForecast() {
        if (!stationId) {
            return;
        }

        isLoading = true;

        try {
            const days = parseInt(selectedTimeframe.replace("days", ""));
            const url = `/api/stations/${encodeURIComponent(stationId)}/energy-demand-forecast?days=${days}`;

            const response = await fetch(url, {
                cache: "no-cache",
                signal: AbortSignal.timeout(15000),
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                },
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(
                    `API 호출 실패: ${response.status} ${response.statusText}`
                );
            }

            const result = await response.json();

            if (
                result.success &&
                result.energy_statistics &&
                result.data_range
            ) {
                energyForecast = result;

                // 실제 데이터 범위 설정
                dataRange = {
                    startDate: new Date(result.data_range.start_date),
                    endDate: new Date(result.data_range.end_date),
                    recordCount: result.data_range.total_records,
                };

                // DOM 업데이트 보장 후 차트 생성
                await tick();
                setTimeout(createEnergyChart, 100);
            } else {
                energyForecast = null;
                dataRange = {
                    startDate: null,
                    endDate: null,
                    recordCount: 0,
                };
            }

            lastUpdated = new Date();
        } catch (error) {
            energyForecast = null;
        } finally {
            isLoading = false;
        }
    }

    async function createEnergyChart() {
        // DOM 요소가 실제로 렌더링되었는지 확인
        await tick();

        // 1. Canvas 컨테이너 확인
        if (!chartContainer) {
            return false;
        }

        // 2. Chart.js 라이브러리 확인
        if (!Chart) {
            return false;
        }

        // 3. 에너지 예측 데이터 확인
        if (!energyForecast) {
            return false;
        }

        // 4. DOM 연결 확인
        if (!chartContainer.parentElement) {
            return false;
        }

        try {
            // 기존 차트 제거
            if (chart) {
                chart.destroy();
                chart = null;
            }

            // Canvas 컨텍스트 가져오기
            const ctx = chartContainer.getContext("2d");
            if (!ctx) {
                return false;
            }

            // 실제 데이터 추출
            let actualData = [];
            let predictedData = [];

            // API 응답 구조에 따라 데이터 추출
            if (energyForecast.timeseries_data) {
                actualData =
                    energyForecast.timeseries_data.filter(
                        (d) => d.type === "actual"
                    ) || [];
                predictedData =
                    energyForecast.timeseries_data.filter(
                        (d) => d.type === "predicted"
                    ) || [];
            } else {
                actualData = energyForecast.actual_data || [];
                predictedData = energyForecast.predicted_data || [];
            }

            // 데이터가 없으면 차트를 생성하지 않음
            if (actualData.length === 0 && predictedData.length === 0) {
                return false;
            }

            // Chart.js 설정
            const chartConfig = {
                type: "line",
                data: {
                    datasets: [
                        {
                            label: "실제 에너지 소비 (kWh)",
                            data: actualData.map((d) => ({
                                x: d.date,
                                y: d.energy,
                            })),
                            borderColor: "#4caf50",
                            backgroundColor: "rgba(76, 175, 80, 0.1)",
                            fill: false,
                            borderWidth: 2,
                            tension: 0.2,
                            pointRadius: 3,
                            pointHoverRadius: 5,
                        },
                        {
                            label: "예측 에너지 소비 (kWh)",
                            data: predictedData.map((d) => ({
                                x: d.date,
                                y: d.energy,
                            })),
                            borderColor: "#2196f3",
                            backgroundColor: "rgba(33, 150, 243, 0.1)",
                            fill: false,
                            borderWidth: 2,
                            borderDash: [8, 4],
                            tension: 0.2,
                            pointRadius: 3,
                            pointHoverRadius: 5,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: "time",
                            time: {
                                unit: "day",
                                displayFormats: {
                                    day: "MM/dd",
                                },
                            },
                            title: {
                                display: true,
                                text: "날짜",
                            },
                        },
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: "전력량 (kWh)",
                            },
                        },
                    },
                    plugins: {
                        legend: {
                            position: "top",
                        },
                        tooltip: {
                            mode: "index",
                            intersect: false,
                        },
                        zoom: {
                            limits: {
                                x: { min: "original", max: "original" },
                                y: { min: "original", max: "original" },
                            },
                            pan: {
                                enabled: true,
                                mode: "xy",
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
                            },
                        },
                    },
                },
            };

            chart = new Chart(ctx, chartConfig);

            return true;
        } catch (error) {
            return false;
        }
    }

    function resetZoom() {
        if (chart) {
            chart.resetZoom();
        }
    }

    // 시간대 변경 시 데이터 다시 로드 (초기 로드 제외)
    let initialized = false;
    $: {
        if (selectedTimeframe && initialized && stationId) {
            updateEnergyForecast();
        }
    }

    // 초기화 완료 표시
    setTimeout(() => {
        initialized = true;
    }, 1000);

    $: averageDailyEnergy = energyForecast?.energy_statistics?.avg_daily || 0;
    $: totalEnergy = energyForecast?.energy_statistics?.total_energy || 0;
    $: growthRate = energyForecast?.growth_rate || 0;
    $: averageDemand = analysis?.current_statistics?.avg_power || 0;
    $: peakDemand = analysis?.predictions?.peak_power || 0;
    $: recommendedContract =
        analysis?.contract_power_recommendation?.recommended_contract_kw || 0;

    const MAX_INSIGHTS_PREVIEW = 5;
    let showAllInsights = false;

    $: insightsCount = energyForecast?.insights?.length || 0;
    $: visibleInsights = energyForecast?.insights
        ? showAllInsights
            ? energyForecast.insights
            : energyForecast.insights.slice(0, MAX_INSIGHTS_PREVIEW)
        : [];
</script>

<div class="demand-predictor">
    <div class="component-header">
        <div class="data-range">
            {#if dataRange.startDate && dataRange.endDate}
                <div class="range-pill">
                    <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                    >
                        <rect
                            x="3"
                            y="4"
                            width="18"
                            height="18"
                            rx="2"
                            ry="2"
                        />
                        <line x1="16" y1="2" x2="16" y2="6" />
                        <line x1="8" y1="2" x2="8" y2="6" />
                        <line x1="3" y1="10" x2="21" y2="10" />
                    </svg>
                    <span
                        >{dataRange.startDate.toLocaleDateString()} ~ {dataRange.endDate.toLocaleDateString()}</span
                    >
                </div>
                <div class="records-pill">
                    <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                    >
                        <path
                            d="M9 11H15M9 15H15M17 21H7C6.46957 21 5.96086 20.7893 5.58579 20.4142C5.21071 20.0391 5 19.5304 5 19V5C5 4.46957 5.21071 3.96086 5.58579 3.58579C5.96086 3.21071 6.46957 3 7 3H12.5858C12.851 3 13.1054 3.10536 13.2929 3.29289L16.7071 6.70711C16.8946 6.89464 17 7.149 17 7.41421V19C17 19.5304 16.7893 20.0391 16.4142 20.4142C16.0391 20.7893 15.5304 21 15 21H7Z"
                        />
                    </svg>
                    <span>{dataRange.recordCount}건</span>
                </div>
            {/if}
        </div>

        <div class="controls">
            <select bind:value={selectedTimeframe} class="timeframe-select">
                {#each timeframes as timeframe}
                    <option value={timeframe.value}>{timeframe.label}</option>
                {/each}
            </select>
            <div class="last-updated">
                {#if isLoading}
                    <LoadingSpinner size="small" />
                    <span>분석 중...</span>
                {:else if lastUpdated}
                    <span
                        >마지막 업데이트: {lastUpdated.toLocaleTimeString()}</span
                    >
                {/if}
            </div>
        </div>
    </div>

    <div class="metrics-row">
        <MetricCard
            title="일평균 에너지"
            value={averageDailyEnergy}
            unit="kWh"
            type="energy"
        />
        <MetricCard
            title="총 에너지 소비"
            value={totalEnergy}
            unit="kWh"
            type="total"
        />
        <MetricCard title="성장률" value={growthRate} unit="%" type="growth" />
        {#if energyForecast?.energy_statistics}
            <MetricCard
                title="최대 일소비"
                value={energyForecast.energy_statistics.max_daily}
                unit="kWh"
                type="peak"
            />
        {/if}
    </div>

    <div class="chart-section">
        {#if isLoading}
            <div class="chart-loading">
                <LoadingSpinner size="large" />
                <p>데이터를 불러오는 중...</p>
            </div>
        {:else if energyForecast && (energyForecast.actual_data?.length > 0 || energyForecast.predicted_data?.length > 0 || energyForecast.timeseries_data?.length > 0)}
            <div class="chart-container-wrapper">
                <div class="chart-header">
                    <h3>전력량 수요 추이</h3>
                    <button
                        class="zoom-reset-btn"
                        on:click={resetZoom}
                        title="줌 초기화"
                    >
                        원래대로
                    </button>
                </div>
                <div
                    class="chart-container"
                    style="position: relative; height: 400px; width: 100%;"
                >
                    <canvas
                        bind:this={chartContainer}
                        style="display: block; box-sizing: border-box; height: 400px; width: 100%;"
                    ></canvas>
                </div>
            </div>
        {:else}
            <div class="no-data-message">
                <div class="no-data-icon">📊</div>
                <h4>차트 데이터 없음</h4>
                <p>
                    해당 충전소({stationId})의 에너지 소비 데이터가 CSV에서
                    발견되지 않았습니다.
                </p>
                <div class="data-check-info">
                    <p><strong>확인해주세요!</strong></p>
                    <ul>
                        <li>CSV 파일에 해당 충전소 ID 데이터 존재 여부</li>
                        <li>해당 충전소의 데이터 기간 범위</li>
                        <li>데이터 형식 및 필드명 일치 여부</li>
                    </ul>
                </div>
            </div>
        {/if}
    </div>

    {#if energyForecast && energyForecast.insights && energyForecast.insights.length > 0}
        <!-- 간결하고 일관된 스타일의 인사이트 섹션 -->
        <div class="insights-section cohesive">
            <div class="insights-header">
                <div class="insights-title-wrap">
                    <span class="insights-icon">💡</span>
                    <h3 class="insights-title">참고 사항</h3>
                </div>
            </div>

            <div class="insights-list">
                {#each visibleInsights as insight, index}
                    <div
                        class="insight-item card"
                        style="--delay: {index * 0.06}s"
                    >
                        <div class="insight-accent" aria-hidden="true"></div>
                        <div class="insight-body">
                            <div class="insight-content">{insight}</div>
                        </div>
                    </div>
                {/each}
            </div>

            {#if insightsCount > MAX_INSIGHTS_PREVIEW}
                <div class="insights-footer">
                    <button
                        class="btn outline small"
                        on:click={() => (showAllInsights = !showAllInsights)}
                    >
                        {#if showAllInsights}간단히 보기{/if}
                        {#if !showAllInsights}더 보기 (+{insightsCount -
                                MAX_INSIGHTS_PREVIEW}){/if}
                    </button>
                </div>
            {/if}
        </div>
    {/if}

    {#if energyForecast && energyForecast.monthly_summary && energyForecast.monthly_summary.length > 0}
        <div class="monthly-summary">
            <h3>📅 월별 에너지 소비</h3>
            <div class="monthly-grid">
                {#each energyForecast.monthly_summary.slice(-6) as month}
                    <div class="month-card">
                        <div class="month-label">{month.month_label}</div>
                        <div class="month-total">
                            {month.total_energy.toFixed(1)}kWh
                        </div>
                        <div class="month-avg">
                            일평균: {month.avg_daily.toFixed(1)}kWh
                        </div>
                        <div class="month-days">{month.active_days}일 활동</div>
                    </div>
                {/each}
            </div>
        </div>
    {/if}
</div>

<style>
    /* Mobile-first base styles */
    .demand-predictor {
        background: transparent;
        border-radius: 0;
        padding: 24px;
        border: none;
        box-shadow: none;
        transition: all 0.3s ease;
    }

    .component-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 20px;
        margin-bottom: 24px;
        padding-bottom: 16px;
        border-bottom: 1px solid var(--border-color);
        flex-wrap: wrap;
    }

    .data-range {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }

    .range-pill,
    .records-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        background: var(--neutral-light);
        border: 1px solid var(--border-color);
        border-radius: 20px;
        font-size: 0.85em;
        color: var(--text-primary);
        font-weight: 500;
    }

    .range-pill svg,
    .records-pill svg {
        width: 14px;
        height: 14px;
        color: var(--primary-color);
    }

    .range-pill {
        background: linear-gradient(
            135deg,
            rgba(33, 150, 243, 0.1),
            rgba(33, 150, 243, 0.05)
        );
        border-color: rgba(33, 150, 243, 0.2);
    }

    .records-pill {
        background: linear-gradient(
            135deg,
            rgba(76, 175, 80, 0.1),
            rgba(76, 175, 80, 0.05)
        );
        border-color: rgba(76, 175, 80, 0.2);
    }

    .controls {
        display: flex;
        align-items: center;
        gap: 12px;
        width: 100%;
        justify-content: space-between;
    }

    .timeframe-select {
        padding: 6px 10px;
        border: 2px solid var(--border-color);
        border-radius: 6px;
        background: var(--bg-secondary);
        color: var(--text-primary);
        cursor: pointer;
        font-size: 0.8em;
        min-width: 80px;
        transition: all 0.3s ease;
    }

    .timeframe-select:focus {
        outline: none;
        border-color: var(--primary-color);
    }

    .last-updated {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 0.75em;
        color: var(--text-muted);
        flex-shrink: 0;
    }

    .metrics-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin-bottom: 20px;
    }

    .insights-section {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    /* Tablet Layout */
    @media (min-width: 768px) {
        .demand-predictor {
            padding: 32px;
        }

        .component-header {
            flex-wrap: nowrap;
            gap: 24px;
        }

        .data-range {
            gap: 16px;
        }

        .range-pill,
        .records-pill {
            font-size: 0.9em;
            padding: 8px 16px;
        }

        .controls {
            gap: 16px;
            width: auto;
        }

        .timeframe-select {
            padding: 8px 12px;
            font-size: 0.9em;
            min-width: 120px;
        }

        .last-updated {
            font-size: 0.9em;
            gap: 6px;
        }

        .metrics-row {
            grid-template-columns: repeat(4, 1fr);
            gap: 14px;
            margin-bottom: 24px;
        }

        .insights-section {
            gap: 14px;
        }
    }

    /* Desktop Layout */
    @media (min-width: 1024px) {
        .demand-predictor {
            padding: 40px;
        }

        .metrics-row {
            gap: 16px;
            margin-bottom: 32px;
        }

        .insights-section {
            gap: 16px;
        }
    }

    /* 새로운 에너지 차트 및 인사이트 스타일 */
    .chart-section {
        background: transparent;
        border-radius: 0;
        padding: 0;
        margin-bottom: 32px;
        border: none;
        box-shadow: none;
    }

    .chart-section h3 {
        margin: 0 0 20px 0;
        color: var(--text-primary);
        font-size: 1.2em;
        font-weight: 700;
    }

    .chart-container {
        position: relative;
        height: 400px;
        width: 100%;
        background: var(--neutral-light);
        border-radius: 12px;
        padding: 16px;
        border: 1px solid var(--border-color);
        margin-bottom: 24px;
    }

    .insights-section {
        background: transparent;
        border-radius: 0;
        padding: 0;
        margin-bottom: 32px;
        border: none;
        box-shadow: none;
    }

    .insights-section h3 {
        margin: 0 0 20px 0;
        color: var(--text-primary);
        font-size: 1.2em;
        font-weight: 700;
    }

    .insights-grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 12px;
    }

    .insight-card {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 16px;
        background: var(--neutral-light);
        border-radius: 12px;
        border-left: 4px solid var(--primary-color);
        transition:
            transform 0.2s ease,
            box-shadow 0.2s ease;
        position: relative;
    }

    .insight-card:hover {
        transform: translateX(4px);
        box-shadow: 0 4px 12px var(--shadow);
    }

    .insight-icon {
        font-size: 1.2em;
        flex-shrink: 0;
    }

    .insight-text {
        color: var(--text-primary);
        font-size: 0.9em;
        line-height: 1.5;
        font-family: "Consolas", "Monaco", "SF Mono", monospace;
        font-weight: 500;
    }

    .monthly-summary {
        background: transparent;
        border-radius: 0;
        padding: 0;
        margin-bottom: 32px;
        border: none;
        box-shadow: none;
    }

    .monthly-summary h3 {
        margin: 0 0 20px 0;
        color: var(--text-primary);
        font-size: 1.2em;
        font-weight: 700;
    }

    .monthly-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 16px;
    }

    .month-card {
        background: var(--neutral-light);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        border: 1px solid var(--border-color);
        transition:
            transform 0.2s ease,
            box-shadow 0.2s ease;
    }

    .month-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 20px var(--shadow);
    }

    .month-label {
        font-size: 0.9em;
        color: var(--text-muted);
        font-weight: 600;
        margin-bottom: 8px;
    }

    .month-total {
        font-size: 1.4em;
        font-weight: 700;
        color: var(--primary-color);
        margin-bottom: 4px;
    }

    .month-avg {
        font-size: 0.8em;
        color: var(--text-secondary);
        margin-bottom: 2px;
    }

    .month-days {
        font-size: 0.75em;
        color: var(--text-muted);
    }

    .no-data-message {
        text-align: center;
        padding: 40px 20px;
        background: var(--neutral-light);
        border-radius: 12px;
        border: 1px solid var(--border-color);
        margin-bottom: 24px;
    }

    .no-data-icon {
        font-size: 3em;
        margin-bottom: 16px;
        opacity: 0.6;
    }

    .no-data-message h4 {
        margin: 0 0 12px 0;
        color: var(--text-primary);
        font-size: 1.2em;
        font-weight: 600;
    }

    .no-data-message p {
        margin: 0 0 20px 0;
        color: var(--text-secondary);
        line-height: 1.5;
    }

    .data-check-info {
        background: var(--bg-secondary);
        border-radius: 8px;
        padding: 16px;
        text-align: left;
        margin-top: 20px;
    }

    .data-check-info p {
        margin: 0 0 8px 0;
        font-weight: 600;
        color: var(--text-primary);
    }

    .data-check-info ul {
        margin: 0;
        padding-left: 20px;
        color: var(--text-secondary);
    }

    .data-check-info li {
        margin-bottom: 4px;
        font-size: 0.9em;
    }

    .chart-loading {
        text-align: center;
        padding: 60px 20px;
        color: var(--text-secondary);
    }

    .chart-loading p {
        margin-top: 16px;
        font-size: 1.1em;
    }

    .chart-container-wrapper {
        margin-bottom: 24px;
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 8px var(--shadow);
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

    /* 태블릿 반응형 */
    @media (min-width: 768px) {
        .chart-container {
            height: 450px;
        }

        .insights-grid {
            grid-template-columns: repeat(2, 1fr);
        }

        .monthly-grid {
            grid-template-columns: repeat(3, 1fr);
        }
    }

    /* 데스크톱 반응형 */
    @media (min-width: 1024px) {
        .chart-container {
            height: 500px;
        }

        .monthly-grid {
            grid-template-columns: repeat(6, 1fr);
        }
    }

    /* Large Desktop Layout */
    @media (min-width: 1440px) {
        .demand-predictor {
            padding: 48px;
        }
    }

    /* Modern Insights Section Styles */
    .insights-section {
        margin: 32px 0;
        padding: 0;
    }

    .insights-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 24px;
        padding-bottom: 12px;
        border-bottom: 2px solid var(--border-color);
    }

    .insights-icon {
        font-size: 1.5em;
        filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
    }

    .insights-title {
        margin: 0;
        color: var(--text-primary);
        font-size: 1.5em;
        font-weight: 600;
        letter-spacing: -0.025em;
    }

    .insights-list {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .insight-item {
        display: flex;
        align-items: flex-start;
        gap: 16px;
        padding: 4px 0;
        opacity: 0;
        animation: fadeInUp 0.6s ease forwards;
        animation-delay: var(--delay);
    }

    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .insight-bullet {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: linear-gradient(
            135deg,
            var(--primary-color),
            var(--primary-light)
        );
        flex-shrink: 0;
        margin-top: 8px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease;
    }

    .insight-item:hover .insight-bullet {
        transform: scale(1.2);
    }

    .insight-content {
        color: var(--text-primary);
        font-size: 1.1rem;
        line-height: 1.1;
        font-weight: 400;
        transition: color 0.2s ease;
    }

    .insight-item:hover .insight-content {
        color: var(--primary-color);
    }

    /* Modern Insights (override/extend) */
    .insights-section.modern {
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 14px;
        padding: 16px;
        box-shadow: 0 2px 10px var(--shadow);
    }

    .insights-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 12px;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--border-color);
    }

    .insights-title-wrap {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .insights-icon {
        font-size: 1.2rem;
    }

    .insights-title {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--text-primary);
    }

    .btn.outline {
        background: transparent;
        border: 1px solid var(--primary-color);
        color: var(--primary-color);
    }
    .btn.outline:hover {
        background: rgba(var(--primary-rgb), 0.08);
        transform: translateY(-1px);
    }

    .insights-list {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .insight-item.card {
        display: grid;
        grid-template-columns: 4px 1fr;
        gap: 0;
        background: var(--neutral-light);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        overflow: hidden;
        opacity: 0;
        animation: fadeInUp 0.5s ease forwards;
        animation-delay: var(--delay);
    }

    .insight-accent {
        background: linear-gradient(
            180deg,
            var(--primary-color),
            var(--primary-light)
        );
    }

    .insight-body {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 14px;
    }

    .insight-content {
        color: var(--text-primary);
        font-size: 1rem;
        line-height: 1.4;
    }

    .icon-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 8px;
        border: 1px solid var(--border-color);
        background: var(--bg-secondary);
        color: var(--text-secondary);
        cursor: pointer;
        transition:
            background 0.2s ease,
            border-color 0.2s ease,
            color 0.2s ease,
            transform 0.1s ease;
    }
    .icon-button:hover {
        border-color: var(--primary-color);
        color: var(--primary-color);
        transform: translateY(-1px);
    }

    .insights-footer {
        margin-top: 12px;
        display: flex;
        justify-content: center;
    }

    /* Cohesive Insights (다른 카드·차트와 톤 통일) */
    .insights-section.cohesive {
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 8px var(--shadow);
        margin: 32px 0;
    }

    .insights-section.cohesive .insights-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 12px;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--border-color);
    }

    .insights-section.cohesive .insights-title-wrap {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .insights-section.cohesive .insights-icon {
        font-size: 1.2rem;
    }

    .insights-section.cohesive .insights-title {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--text-primary);
    }

    .insights-section.cohesive .insights-count {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        height: 22px;
        padding: 0 8px;
        border-radius: 999px;
        background: var(--neutral-light);
        border: 1px solid var(--border-color);
        font-size: 0.75rem;
        color: var(--text-secondary);
    }

    .insights-section.cohesive .insights-list {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .insights-section.cohesive .insight-item.card {
        display: grid;
        grid-template-columns: 4px 1fr;
        gap: 0;
        background: var(--neutral-light);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        overflow: hidden;
        opacity: 0;
        animation: fadeInUp 0.5s ease forwards;
        animation-delay: var(--delay);
    }

    .insight-accent {
        background: linear-gradient(
            180deg,
            var(--primary-color),
            var(--primary-light)
        );
    }

    .insight-body {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 14px;
    }

    .insight-content {
        color: var(--text-primary);
        font-size: 1rem;
        line-height: 1.4;
    }
</style>

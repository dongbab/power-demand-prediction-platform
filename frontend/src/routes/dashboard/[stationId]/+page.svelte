<script>
    import { onMount, onDestroy } from "svelte";
    import { page } from "$app/stores";
    import { goto } from "$app/navigation";
    import {
        stationActions,
        stationData,
        currentStation,
        isLoading,
        error,
        stationById,
    } from "../../../stores/stationStore.ts";
    import { uiActions, isRefreshing } from "../../../stores/uiStore.ts";
    import { theme } from "../../../stores/themeStore.ts";

    import PeakPowerPredictor from "../../../components/Dashboard/PeakPowerPredictor.svelte";
    import PowerDemandPredictor from "../../../components/Dashboard/PowerDemandPredictor.svelte";
    import EnsemblePrediction from "../../../components/Dashboard/EnsemblePrediction.svelte";
    import LoadingSpinner from "../../../components/LoadingSpinner.svelte";

    let stationId;
    let station = null;
    let showResults = false;
    let resultsContent = "";

    $: stationId = $page.params.stationId;
    $: station = $stationById.get(stationId);

    onMount(async () => {
        // Initialize theme
        theme.init();
        
        // Chart.js 모듈 미리 로드 (병렬 처리)
        if (typeof window !== 'undefined') {
            import('../../../lib/chart-utils.js').then(({ preloadChartModules }) => {
                preloadChartModules();
            }).catch(error => {
                console.log('Chart utils preload failed:', error);
            });
        }
        
        if (!stationId) {
            goto("/");
            return;
        }

        // Load station data if not already loaded (최적화: 병렬 처리)
        let stationLoadPromise = null;
        if (!station) {
            stationLoadPromise = stationActions.loadStations();
        }

        // 차트 데이터 로딩을 미리 시작 (충전소 정보와 병렬 처리)
        const dataLoadPromise = loadData();

        // 충전소 정보가 필요한 경우 대기
        if (stationLoadPromise) {
            await stationLoadPromise;
            station = $stationById.get(stationId);
        }

        if (!station) {
            uiActions.showNotification(
                `충전소 '${stationId}'를 찾을 수 없습니다.`,
                "error"
            );
            goto("/");
            return;
        }

        stationActions.setCurrentStation(station);
        
        // 데이터 로딩 완료 대기
        await dataLoadPromise;

        // Keyboard shortcuts (브라우저에서만 실행)
        if (typeof document !== 'undefined') {
            document.addEventListener("keydown", handleKeydown);
        }
    });

    onDestroy(() => {
        if (typeof document !== 'undefined') {
            document.removeEventListener("keydown", handleKeydown);
        }
    });

    async function loadData() {
        try {
            await stationActions.loadStationData(stationId);
        } catch (error) {
            uiActions.showNotification(
                '데이터 로딩에 실패했습니다. 새로고침을 시도해주세요.',
                'error'
            );
        }
    }

    async function refreshDashboard() {
        uiActions.setRefreshing(true);
        try {
            await loadData();
            uiActions.showNotification(
                "대시보드가 새로고침되었습니다",
                "success"
            );
        } catch (err) {
            uiActions.showNotification("새로고침에 실패했습니다", "error");
        } finally {
            uiActions.setRefreshing(false);
        }
    }

    async function testRealtime() {
        try {
            const prediction = $stationData.prediction;
            if (prediction) {
                resultsContent = JSON.stringify(prediction, null, 2);
                showResults = true;
                uiActions.showNotification(
                    "실시간 예측이 완료되었습니다",
                    "success"
                );
            }
        } catch (err) {
            uiActions.showNotification("실시간 예측에 실패했습니다", "error");
        }
    }

    async function testMonthly() {
        try {
            const monthlyContract = $stationData.monthlyContract;
            if (monthlyContract) {
                resultsContent = JSON.stringify(monthlyContract, null, 2);
                showResults = true;
                uiActions.showNotification(
                    "월별 계약 권고가 완료되었습니다",
                    "success"
                );
            }
        } catch (err) {
            uiActions.showNotification(
                "월별 계약 권고에 실패했습니다",
                "error"
            );
        }
    }

    async function testAnalysis() {
        try {
            const analysis = $stationData.analysis;
            if (analysis) {
                resultsContent = JSON.stringify(analysis, null, 2);
                showResults = true;
                uiActions.showNotification(
                    "상세 분석이 완료되었습니다",
                    "success"
                );
            }
        } catch (err) {
            uiActions.showNotification("상세 분석에 실패했습니다", "error");
        }
    }

    function exportData() {
        try {
            const exportData = {
                timestamp: new Date().toISOString(),
                station_id: stationId,
                station_info: station,
                data: $stationData,
            };

            const blob = new Blob([JSON.stringify(exportData, null, 2)], {
                type: "application/json",
            });

            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${stationId}_dashboard_${new Date().toISOString().split("T")[0]}.json`;
            a.click();
            URL.revokeObjectURL(url);

            uiActions.showNotification("데이터 내보내기 완료", "success");
        } catch (err) {
            uiActions.showNotification(
                "데이터 내보내기에 실패했습니다",
                "error"
            );
        }
    }

    function handleKeydown(event) {
        if (event.ctrlKey || event.metaKey) {
            switch (event.key.toLowerCase()) {
                case "r":
                    event.preventDefault();
                    refreshDashboard();
                    break;
                case "e":
                    event.preventDefault();
                    exportData();
                    break;
                case "1":
                    event.preventDefault();
                    testRealtime();
                    break;
                case "2":
                    event.preventDefault();
                    testAnalysis();
                    break;
                case "3":
                    event.preventDefault();
                    testMonthly();
                    break;
                case "arrowleft":
                    event.preventDefault();
                    window.history.back();
                    break;
            }
        }

        if (event.key === "Escape") {
            showResults = false;
        }
    }


    $: analysis = $stationData.analysis;
    $: monthlyContract = $stationData.monthlyContract;
</script>

<svelte:head>
    <title>{station?.name || stationId} - 전력 예측 대시보드</title>
</svelte:head>

<div class="container">
    <div class="header">
        <div class="header-content">
            <div class="navigation-section">
                <nav class="breadcrumb">
                    <a href="/" class="breadcrumb-item">
                        <svg
                            class="breadcrumb-icon"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                        >
                            <path
                                d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
                            />
                            <polyline points="9,22 9,12 15,12 15,22" />
                        </svg>
                        <span>충전소 목록</span>
                    </a>
                    <svg
                        class="breadcrumb-separator"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                    >
                        <polyline points="9,18 15,12 9,6" />
                    </svg>
                    <span class="breadcrumb-current">
                        <svg
                            class="breadcrumb-icon"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                        >
                            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                        </svg>
                        <span>대시보드</span>
                    </span>
                </nav>

                <button
                    class="btn-back-enhanced"
                    on:click={() => window.history.back()}
                >
                    <svg
                        class="back-arrow"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                    >
                        <path d="M19 12H5m7-7-7 7 7 7" />
                    </svg>
                    <div class="btn-back-content">
                        <span class="btn-back-text">뒤로 가기</span>
                        <span class="btn-back-hint">Ctrl + ←</span>
                    </div>
                </button>
            </div>

            <div class="header-title">
                <h1>전력 예측 대시보드</h1>
                <p class="header-subtitle">
                    블루네트웍스 전력 수요 예측 시스템
                </p>
            </div>

            <div class="header-actions">
                <div class="quick-actions">
                    <!-- 테마 토글 버튼 -->
                    <button 
                        class="header-action-btn theme-toggle" 
                        on:click={() => theme.toggleTheme()}
                        title={$theme === 'light' ? '다크 모드로 변경' : '라이트 모드로 변경'}
                    >
                        {#if $theme === 'light'}
                            <!-- Moon icon for dark mode -->
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                            </svg>
                        {:else}
                            <!-- Sun icon for light mode -->
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="5"/>
                                <line x1="12" y1="1" x2="12" y2="3"/>
                                <line x1="12" y1="21" x2="12" y2="23"/>
                                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                                <line x1="1" y1="12" x2="3" y2="12"/>
                                <line x1="21" y1="12" x2="23" y2="12"/>
                                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                            </svg>
                        {/if}
                    </button>

                    <button 
                        class="header-action-btn" 
                        title="대시보드 새로고침"
                        on:click={refreshDashboard}
                    >
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                        >
                            <path d="M23 4v6h-6" />
                            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                        </svg>
                    </button>
                    <button class="header-action-btn" title="데이터 내보내기">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                        >
                            <path
                                d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
                            />
                            <polyline points="7,10 12,15 17,10" />
                            <line x1="12" y1="15" x2="12" y2="3" />
                        </svg>
                    </button>
                    <button class="header-action-btn" title="알림 설정">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                        >
                            <path
                                d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"
                            />
                            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    </div>

    {#if station}
        <div class="station-info">
            <h2>🏢 {station.name}</h2>
            <div class="station-details">
                <div class="detail-item">
                    <span class="detail-label">⚡ 충전기 타입</span>
                    <span class="detail-value">{station.charger_type}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">🔌 커넥터</span>
                    <span class="detail-value">{station.connector_type}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">
                        📊 용량 효율성
                        <div class="info-tooltip">
                            <div class="info-icon">?</div>
                            <div class="tooltip-content">
                                <div class="tooltip-formula">
                                    <strong>계산 방식:</strong> 평균전력 / 정격용량 × 100%
                                </div>
                                <div class="capacity-examples">
                                    완속(AC): 7kW 기준 • 급속(DC): 100kW 기준
                                </div>
                            </div>
                        </div>
                    </span>
                    <span class="detail-value capacity-efficiency"
                        >{station.capacity_efficiency || "-"}</span
                    >
                </div>
            </div>
            <p class="station-location">📍 {station.location}</p>
        </div>
    {/if}

    {#if $isLoading}
        <div class="loading-container">
            <LoadingSpinner size="large" />
            <p>데이터를 로드하는 중...</p>
        </div>
    {:else if $error}
        <div class="alert alert-error">
            <strong>오류</strong>
            {$error}
        </div>
    {:else}
        <!-- Phase 3: AI 앙상블 예측 (최상단) -->
        <EnsemblePrediction {stationId} currentContractKw={100} />

        <!-- Main Prediction Sections -->
        <div class="prediction-sections">
            <!-- 순간최고 전력 예측 박스 -->
            <div class="prediction-box peak-power-box">
                <div class="prediction-box-header">
                    <div class="box-title">
                        <h2>순간 최고 전력 예측</h2>
                        <p>계약전력 권고 및 피크 전력 분석</p>
                    </div>
                    <button
                        class="box-refresh-btn primary"
                        on:click={refreshDashboard}
                        disabled={$isRefreshing}
                        title="순간최고전력 예측 갱신"
                    >
                        {#if $isRefreshing}
                            <LoadingSpinner size="small" />
                        {:else}
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M23 4v6h-6" />
                                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                            </svg>
                        {/if}
                        <span>갱신</span>
                    </button>
                </div>
                <div class="prediction-box-content">
                    <PeakPowerPredictor
                        {stationId}
                        {monthlyContract}
                    />
                </div>
            </div>

            <!-- 에너지 수요 예측 박스 -->
            <div class="prediction-box energy-demand-box">
                <div class="prediction-box-header">
                    <div class="box-title">
                        <h2>전력량 수요 예측</h2>
                        <p>전력량 기반 수요 패턴 분석 및 예측</p>
                    </div>
                    <button
                        class="box-refresh-btn secondary"
                        on:click={refreshDashboard}
                        disabled={$isRefreshing}
                        title="에너지 수요 예측 갱신"
                    >
                        {#if $isRefreshing}
                            <LoadingSpinner size="small" />
                        {:else}
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M23 4v6h-6" />
                                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                            </svg>
                        {/if}
                        <span>갱신</span>
                    </button>
                </div>
                <div class="prediction-box-content">
                    <PowerDemandPredictor
                        {stationId}
                        {analysis}
                    />
                </div>
            </div>
        </div>

        <div class="control-dashboard">
            <div class="dashboard-header">
                <div class="header-info">
                    <div class="header-icon">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                        >
                            <path d="M12 20h9" />
                            <path
                                d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"
                            />
                        </svg>
                    </div>
                    <div class="header-text">
                        <h3>API 테스트 대시보드</h3>
                        <p>API 테스트 도구</p>
                    </div>
                </div>
            </div>

            <div class="action-grid">
                <div class="action-card primary" class:loading={$isRefreshing}>
                    <div class="action-icon">
                        {#if $isRefreshing}
                            <LoadingSpinner size="small" />
                        {:else}
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                            >
                                <path d="M23 4v6h-6" />
                                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                            </svg>
                        {/if}
                    </div>
                    <div class="action-content">
                        <h4>대시보드 새로고침</h4>
                        <p>전체 데이터 및 차트 업데이트</p>
                        <button
                            class="action-btn"
                            on:click={refreshDashboard}
                            disabled={$isRefreshing}
                        >
                            새로고침
                        </button>
                    </div>
                </div>

                <div class="action-card">
                    <div class="action-icon">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                        >
                            <path d="M12 2L2 7l10 5 10-5-10-5z" />
                            <path d="M2 17l10 5 10-5" />
                            <path d="M2 12l10 5 10-5" />
                        </svg>
                    </div>
                    <div class="action-content">
                        <h4>예측 데이터 확인하기</h4>
                        <p>전력 수요 예측 및 분석</p>
                        <button class="action-btn" on:click={testRealtime}>
                            데이터 확인
                        </button>
                    </div>
                </div>

                <div class="action-card">
                    <div class="action-icon">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
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
                    </div>
                    <div class="action-content">
                        <h4>월별 계약 권고</h4>
                        <p>최적 계약 전력 및 비용 분석</p>
                        <button class="action-btn" on:click={testMonthly}>
                            분석 시작
                        </button>
                    </div>
                </div>

                <div class="action-card">
                    <div class="action-icon">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                        >
                            <line x1="18" y1="20" x2="18" y2="10" />
                            <line x1="12" y1="20" x2="12" y2="4" />
                            <line x1="6" y1="20" x2="6" y2="14" />
                        </svg>
                    </div>
                    <div class="action-content">
                        <h4>상세 분석</h4>
                        <p>종합적인 성능 및 이용 패턴 분석</p>
                        <button class="action-btn" on:click={testAnalysis}>
                            분석 보기
                        </button>
                    </div>
                </div>

                <div class="action-card">
                    <div class="action-icon">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                        >
                            <path
                                d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
                            />
                            <polyline points="7,10 12,15 17,10" />
                            <line x1="12" y1="15" x2="12" y2="3" />
                        </svg>
                    </div>
                    <div class="action-content">
                        <h4>데이터 내보내기</h4>
                        <p>JSON 형식으로 전체 데이터 다운로드</p>
                        <button class="action-btn" on:click={exportData}>
                            내보내기
                        </button>
                    </div>
                </div>
            </div>

            {#if showResults}
                <div class="results-modal">
                    <div class="modal-header">
                        <div class="modal-title">
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                            >
                                <polyline
                                    points="22,12 18,12 15,21 9,3 6,12 2,12"
                                />
                            </svg>
                            분석 결과
                        </div>
                        <button
                            class="close-btn"
                            on:click={() => (showResults = false)}
                        >
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                            >
                                <line x1="18" y1="6" x2="6" y2="18" />
                                <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                        </button>
                    </div>
                    <div class="modal-content">
                        <pre class="results-code">{resultsContent}</pre>
                    </div>
                    <div class="modal-actions">
                        <button
                            class="action-btn secondary"
                            on:click={async () => {
                                try {
                                    await navigator.clipboard.writeText(resultsContent);
                                    uiActions.showNotification("복사되었습니다", "success");
                                } catch (err) {
                                    uiActions.showNotification("복사에 실패했습니다", "error");
                                }
                            }}
                        >
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                            >
                                <rect
                                    x="9"
                                    y="9"
                                    width="13"
                                    height="13"
                                    rx="2"
                                    ry="2"
                                />
                                <path
                                    d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
                                />
                            </svg>
                            복사
                        </button>
                        <button
                            class="action-btn"
                            on:click={() => (showResults = false)}
                        >
                            닫기
                        </button>
                    </div>
                </div>
            {/if}
        </div>
    {/if}
</div>

<style>
    .loading-container {
        text-align: center;
        padding: 60px 20px;
    }

    .loading-container p {
        margin-top: 20px;
        color: var(--text-secondary);
        font-size: 1.1em;
    }

    .station-details {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 16px;
        margin: 16px 0;
    }

    .detail-item {
        display: flex;
        flex-direction: column;
        padding: 12px;
        background: var(--neutral-light);
        border-radius: 8px;
        border-left: 4px solid var(--primary-color);
        transition: background-color 0.3s ease;
    }

    .detail-label {
        font-size: 0.9em;
        color: var(--text-secondary);
        margin-bottom: 4px;
        font-weight: 500;
    }

    .detail-value {
        font-size: 1.1em;
        color: var(--primary-color);
        font-weight: 600;
    }

    /* Base styles for mobile-first approach */
    .container {
        padding: 16px;
        max-width: 100%;
        margin: 0 auto;
    }

    .header {
        margin-bottom: 32px;
        padding: 24px;
        background: var(--gradient-primary);
        color: white;
        border-radius: 20px;
        box-shadow: 0 8px 32px var(--shadow-hover);
    }

    .header-content {
        display: flex;
        flex-direction: column;
        gap: 24px;
    }

    .navigation-section {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
    }

    .breadcrumb {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.9em;
    }

    .breadcrumb-item {
        display: flex;
        align-items: center;
        gap: 6px;
        color: rgba(255, 255, 255, 0.8);
        text-decoration: none;
        padding: 6px 12px;
        border-radius: 8px;
        transition: all 0.3s ease;
    }

    .breadcrumb-item:hover {
        color: white;
        background: rgba(255, 255, 255, 0.15);
        transform: translateY(-1px);
    }

    .breadcrumb-current {
        display: flex;
        align-items: center;
        gap: 6px;
        color: white;
        font-weight: 600;
        padding: 6px 12px;
        background: rgba(255, 255, 255, 0.15);
        border-radius: 8px;
    }

    .breadcrumb-icon {
        width: 16px;
        height: 16px;
        stroke-width: 2;
    }

    .breadcrumb-separator {
        width: 16px;
        height: 16px;
        stroke-width: 2;
        color: rgba(255, 255, 255, 0.5);
    }

    .btn-back-enhanced {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 16px;
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.25);
        color: white;
        border-radius: 12px;
        cursor: pointer;
        transition: all 0.3s ease;
        font-size: 0.9em;
        backdrop-filter: blur(10px);
    }

    .btn-back-enhanced:hover {
        background: rgba(255, 255, 255, 0.25);
        border-color: rgba(255, 255, 255, 0.4);
        transform: translateY(-2px);
        box-shadow: 0 4px 20px var(--shadow-hover);
    }

    .back-arrow {
        width: 18px;
        height: 18px;
        stroke-width: 2;
        transition: transform 0.3s ease;
    }

    .btn-back-enhanced:hover .back-arrow {
        transform: translateX(-3px);
    }

    .btn-back-content {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
    }

    .btn-back-text {
        font-weight: 600;
        line-height: 1;
    }

    .btn-back-hint {
        font-size: 0.75em;
        opacity: 0.7;
        font-weight: 400;
    }
    
    /* 툴팁 스타일 */
    .info-tooltip {
        position: relative;
        display: inline-block;
        margin-left: 4px;
    }
    
    .info-icon {
        width: 16px;
        height: 16px;
        color: var(--primary-color, #4f46e5);
        cursor: help;
        transition: all 0.2s ease;
        opacity: 0.6;
        flex-shrink: 0;
        border-radius: 50%;
        background: rgba(79, 70, 229, 0.1);
        border: 1px solid rgba(79, 70, 229, 0.2);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        font-weight: 700;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        line-height: 1;
    }
    
    .info-icon:hover {
        color: white;
        opacity: 1;
        transform: scale(1.1);
        background: var(--primary-color, #4f46e5);
        border-color: var(--primary-color, #4f46e5);
    }
    
    .tooltip-content {
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        background: var(--bg-primary);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 12px;
        box-shadow: 0 4px 20px var(--shadow);
        opacity: 0;
        visibility: hidden;
        transition: all 0.3s ease;
        z-index: 1000;
        min-width: 200px;
        max-width: 280px;
        white-space: nowrap;
    }
    
    .info-tooltip:hover .tooltip-content {
        opacity: 1;
        visibility: visible;
        transform: translateX(-50%) translateY(-8px);
    }
    
    .tooltip-formula {
        margin-bottom: 6px;
        line-height: 1.3;
    }
    
    .capacity-examples {
        font-style: italic;
        color: var(--text-muted);
        font-size: 11px;
        line-height: 1.2;
    }

    .header-title {
        text-align: center;
        flex: 1;
    }

    .header-title h1 {
        margin: 0 0 8px 0;
        font-size: 2em;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
    }

    .header-subtitle {
        margin: 0;
        font-size: 1em;
        opacity: 0.9;
        font-weight: 400;
    }

    .header-actions {
        display: flex;
        align-items: center;
    }

    .quick-actions {
        display: flex;
        gap: 8px;
    }

    .header-action-btn {
        width: 40px;
        height: 40px;
        border: none;
        background: rgba(255, 255, 255, 0.15);
        color: white;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.3s ease;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    .header-action-btn:hover {
        background: rgba(255, 255, 255, 0.25);
        transform: translateY(-2px);
        box-shadow: 0 4px 15px var(--shadow);
    }

    .header-action-btn svg {
        width: 20px;
        height: 20px;
        stroke-width: 2;
    }

    /* 테마 토글 버튼 특별 스타일 */
    .header-action-btn.theme-toggle:hover {
        background: rgba(255, 255, 255, 0.3);
        box-shadow: 0 4px 20px rgba(255, 255, 255, 0.1);
    }

    .theme-toggle svg {
        transition: all 0.3s ease;
    }

    .theme-toggle:hover svg {
        transform: rotate(180deg);
    }


    .station-info {
        background: var(--bg-secondary);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 24px;
        box-shadow: 0 2px 8px var(--shadow);
        border: 1px solid var(--border-color);
        transition:
            background-color 0.3s ease,
            border-color 0.3s ease;
    }

    .station-info h2 {
        margin: 0 0 16px 0;
        font-size: 1.4em;
        color: var(--primary-color);
    }

    .station-details {
        display: grid;
        grid-template-columns: 1fr;
        gap: 12px;
        margin: 16px 0;
    }

    .station-location {
        margin: 16px 0 0 0;
        color: var(--text-secondary);
        font-size: 1em;
    }


    .prediction-sections {
        display: grid;
        grid-template-columns: 1fr;
        gap: 32px;
        margin-bottom: 40px;
    }

    .prediction-box {
        background: var(--bg-secondary);
        border-radius: 20px;
        padding: 0;
        box-shadow: 0 8px 24px var(--shadow);
        border: 1px solid var(--border-color);
        transition: all 0.3s ease;
        overflow: hidden;
    }

    .prediction-box:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 32px var(--shadow-hover);
    }

    .prediction-box-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 24px 32px;
        border-bottom: 2px solid var(--border-color);
        gap: 20px;
    }

    .peak-power-box .prediction-box-header {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-light) 100%);
        color: white;
        border-bottom: none;
    }

    .energy-demand-box .prediction-box-header {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        color: white;
        border-bottom: none;
    }

    .box-title h2 {
        margin: 0 0 8px 0;
        font-size: 1.5em;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .box-title p {
        margin: 0;
        opacity: 0.9;
        font-size: 1em;
        font-weight: 400;
    }

    .box-refresh-btn {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px 20px;
        border: none;
        border-radius: 12px;
        cursor: pointer;
        font-weight: 600;
        font-size: 0.9em;
        transition: all 0.3s ease;
        min-width: 100px;
        justify-content: center;
    }

    .box-refresh-btn.primary {
        background: rgba(255, 255, 255, 0.2);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }

    .box-refresh-btn.primary:hover:not(:disabled) {
        background: rgba(255, 255, 255, 0.3);
        border-color: rgba(255, 255, 255, 0.5);
        transform: scale(1.05);
    }

    .box-refresh-btn.secondary {
        background: rgba(255, 255, 255, 0.2);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }

    .box-refresh-btn.secondary:hover:not(:disabled) {
        background: rgba(255, 255, 255, 0.3);
        border-color: rgba(255, 255, 255, 0.5);
        transform: scale(1.05);
    }

    .box-refresh-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
        transform: none;
    }

    .box-refresh-btn svg {
        width: 18px;
        height: 18px;
        stroke-width: 2;
    }

    .prediction-box-content {
        padding: 0;
    }

    /* Modern Control Dashboard Styles */
    .control-dashboard {
        background: linear-gradient(
            135deg,
            var(--bg-secondary) 0%,
            var(--neutral-light) 100%
        );
        border-radius: 24px;
        padding: 32px;
        box-shadow: 0 12px 40px var(--shadow);
        border: 1px solid var(--border-color);
        position: relative;
        overflow: hidden;
        transition:
            background 0.3s ease,
            border-color 0.3s ease;
    }

    .control-dashboard::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: var(--gradient-primary);
    }

    .dashboard-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 32px;
        flex-wrap: wrap;
        gap: 20px;
    }

    .header-info {
        display: flex;
        align-items: center;
        gap: 16px;
    }

    .header-icon {
        width: 48px;
        height: 48px;
        background: var(--gradient-primary);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
    }

    .header-icon svg {
        width: 24px;
        height: 24px;
        stroke-width: 2;
    }

    .header-text h3 {
        margin: 0 0 4px 0;
        font-size: 1.4em;
        font-weight: 700;
        color: var(--primary-color);
    }

    .header-text p {
        margin: 0;
        font-size: 0.9em;
        color: var(--text-secondary);
    }

    .action-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 20px;
        margin-bottom: 32px;
    }

    .action-card {
        background: var(--bg-secondary);
        border-radius: 16px;
        padding: 24px;
        border: 1px solid var(--border-color);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }

    .action-card::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: var(--gradient-secondary);
        opacity: 0;
        transition: opacity 0.3s ease;
    }

    .action-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 32px var(--shadow-hover);
        border-color: var(--primary-color);
    }

    .action-card:hover::before {
        opacity: 1;
    }

    .action-card.primary {
        background: linear-gradient(
            135deg,
            var(--primary-color) 0%,
            var(--primary-light) 100%
        );
        color: white;
        border: none;
    }

    .action-card.primary .action-content h4,
    .action-card.primary .action-content p {
        color: white;
    }

    .action-card.loading {
        animation: pulse 2s infinite;
    }

    .action-icon {
        width: 56px;
        height: 56px;
        border-radius: 14px;
        background: var(--neutral-light);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 20px;
        color: var(--primary-color);
        transition: background-color 0.3s ease;
    }

    .action-card.primary .action-icon {
        background: rgba(255, 255, 255, 0.2);
        color: white;
    }

    .action-icon svg {
        width: 28px;
        height: 28px;
        stroke-width: 2;
    }

    .action-content h4 {
        margin: 0 0 8px 0;
        font-size: 1.1em;
        font-weight: 600;
        color: var(--primary-color);
    }

    .action-content p {
        margin: 0 0 20px 0;
        font-size: 0.9em;
        color: var(--text-secondary);
        line-height: 1.4;
    }

    .action-btn {
        width: 100%;
        padding: 12px 20px;
        background: var(--neutral-light);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        color: var(--primary-color);
        font-weight: 600;
        font-size: 0.9em;
        cursor: pointer;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
    }

    .action-btn:hover:not(:disabled) {
        background: var(--primary-color);
        color: white;
        transform: translateY(-1px);
    }

    .action-card.primary .action-btn {
        background: rgba(255, 255, 255, 0.2);
        color: white;
        border-color: rgba(255, 255, 255, 0.3);
    }

    .action-card.primary .action-btn:hover:not(:disabled) {
        background: rgba(255, 255, 255, 0.3);
        border-color: rgba(255, 255, 255, 0.5);
    }

    .results-modal {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 90vw;
        max-width: 800px;
        max-height: 80vh;
        background: var(--bg-secondary);
        border-radius: 20px;
        box-shadow: 0 25px 50px var(--shadow-hover);
        z-index: 1000;
        overflow: hidden;
        border: 1px solid var(--border-color);
    }

    .results-modal::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        z-index: -1;
        backdrop-filter: blur(4px);
    }

    .modal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 24px 32px;
        background: var(--gradient-primary);
        color: white;
    }

    .modal-title {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 1.2em;
        font-weight: 700;
    }

    .modal-title svg {
        width: 20px;
        height: 20px;
        stroke-width: 2;
    }

    .close-btn {
        width: 32px;
        height: 32px;
        border: none;
        background: rgba(255, 255, 255, 0.2);
        color: white;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .close-btn:hover {
        background: rgba(255, 255, 255, 0.3);
        transform: scale(1.1);
    }

    .close-btn svg {
        width: 16px;
        height: 16px;
        stroke-width: 2;
    }

    .modal-content {
        padding: 32px;
        max-height: 400px;
        overflow-y: auto;
    }

    .results-code {
        background: var(--neutral-light);
        border: 1px solid rgba(46, 86, 166, 0.1);
        border-radius: 12px;
        padding: 20px;
        font-family: "Consolas", "Monaco", "Courier New", monospace;
        font-size: 0.9em;
        line-height: 1.5;
        color: var(--primary-color);
        white-space: pre-wrap;
        word-break: break-all;
    }

    .modal-actions {
        display: flex;
        justify-content: flex-end;
        gap: 12px;
        padding: 24px 32px;
        background: var(--neutral-light);
        border-top: 1px solid var(--border-color);
    }

    .action-btn.secondary {
        background: var(--bg-secondary);
        color: var(--primary-color);
        border: 1px solid var(--border-color);
        width: auto;
        padding: 10px 20px;
    }

    .action-btn.secondary:hover {
        background: var(--neutral-light);
        color: var(--primary-color);
        border-color: var(--primary-color);
    }

    .modal-actions .action-btn {
        width: auto;
        min-width: 80px;
        padding: 8px 16px;
        font-size: 1.2rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
    }

    .modal-actions .action-btn svg {
        width: 16px;
        height: 16px;
        stroke-width: 2;
    }

    /* Tablet Layout */
    @media (min-width: 768px) {
        .container {
            padding: 24px;
        }

        .header {
            padding: 32px;
            margin-bottom: 40px;
            border-radius: 24px;
        }

        .navigation-section {
            flex-wrap: nowrap;
        }

        .header-title h1 {
            font-size: 2.2em;
        }

        .btn-back-enhanced {
            padding: 12px 20px;
        }

        .quick-actions {
            gap: 10px;
        }

        .action-btn {
            width: 44px;
            height: 44px;
        }

        .station-info {
            padding: 24px;
            margin-bottom: 32px;
        }

        .station-info h2 {
            font-size: 1.6em;
        }

        .station-details {
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
        }

        .prediction-sections {
            gap: 40px;
            margin-bottom: 48px;
        }

        .prediction-box-header {
            padding: 28px 36px;
            flex-wrap: nowrap;
        }

        .box-title h2 {
            font-size: 1.6em;
        }

        .box-title p {
            font-size: 1.05em;
        }

        .box-refresh-btn {
            padding: 14px 24px;
            font-size: 1em;
            min-width: 120px;
        }

    }

    /* Desktop Layout */
    @media (min-width: 1024px) {
        .container {
            padding: 32px;
            max-width: 1200px;
        }

        .header {
            padding: 40px;
            margin-bottom: 48px;
        }

        .header-content {
            flex-direction: row;
            align-items: center;
            gap: 32px;
        }

        .navigation-section {
            flex: 0 0 auto;
            flex-direction: column;
            align-items: flex-start;
            gap: 12px;
        }

        .header-title {
            flex: 1;
            text-align: center;
        }

        .header-title h1 {
            font-size: 2.5em;
        }

        .header-actions {
            flex: 0 0 auto;
        }

        .station-info {
            padding: 32px;
            margin-bottom: 40px;
        }

        .station-details {
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }

        .prediction-sections {
            gap: 48px;
            margin-bottom: 56px;
        }

        .prediction-box-header {
            padding: 32px 40px;
        }

        .box-title h2 {
            font-size: 1.7em;
        }

        .box-title p {
            font-size: 1.1em;
        }

        .box-refresh-btn {
            padding: 16px 28px;
            font-size: 1.05em;
            min-width: 140px;
        }

    }

    /* Large Desktop Layout */
    @media (min-width: 1440px) {
        .container {
            max-width: 1400px;
            padding: 40px;
        }

        .prediction-sections {
            gap: 56px;
            margin-bottom: 64px;
        }

        .prediction-box {
            border-radius: 24px;
        }

        .prediction-box-header {
            padding: 36px 44px;
        }

        .box-title h2 {
            font-size: 1.8em;
        }

        .box-refresh-btn {
            padding: 18px 32px;
            font-size: 1.1em;
            min-width: 160px;
        }
    }

    /* 카드 레이아웃: 데스크톱에서 4열, 그 외 auto-fit */
    .control-dashboard .action-grid {
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }
    @media (min-width: 1024px) {
        .control-dashboard .action-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }
    }

    /* 카드 높이/정렬 균일화 */
    .control-dashboard .action-card {
        display: flex;
        flex-direction: column;
        min-height: 220px; /* 필요 시 240~260 조정 */
    }
    .control-dashboard .action-content {
        display: flex;
        flex-direction: column;
        gap: 12px;
        flex: 1;
    }
    .control-dashboard .action-content .action-btn {
        margin-top: auto; /* 버튼을 카드 하단으로 */
    }
    .control-dashboard .action-icon {
        flex: 0 0 auto;
    }

    /* 잘못된 미디어 쿼리로 .action-btn이 44px 정사각형 되는 문제 오버라이드 */
    @media (min-width: 768px) {
        .control-dashboard .action-btn {
            width: 100%;
            height: auto;
        }
    }

    /* 다크모드 대비 강화 */
    .control-dashboard,
    .control-dashboard .action-card {
        background: var(--bg-secondary);
    }
    .control-dashboard .action-card.primary {
        background: var(--gradient-primary);
    }

    /* 큰 화면에서 카드 가독성 향상 */
    @media (min-width: 1440px) {
        .control-dashboard {
            padding: 36px;
        }
        .control-dashboard .action-card {
            min-height: 240px;
        }
    }
</style>

<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import type { Chart as ChartInstance, Point } from 'chart.js';
    import type { EnsemblePredictionResponse } from '../../lib/types';
    
    export let optimizationData: any = null;
    export let predictionDistribution: number[] = [];
    export let ensemblePrediction: EnsemblePredictionResponse['ensemble_prediction'] | null = null;
    
    let chartContainer: HTMLDivElement;
    let chartCanvas: HTMLCanvasElement | null = null;
    let chartInstance: ChartInstance | null = null;
    let isDarkMode = false;
    let histogram: { x: number; y: number }[] = [];
    let lstmProjection: { x: number; y: number }[] = [];
    let q5 = 0;
    let q95 = 0;
    let optimalCandidate: any = null;
    let allCandidates: any[] = [];
    let ChartCtor: typeof import('chart.js/auto')['default'] | null = null;
    let chartReady = false;
    let timeSeriesCanvas: HTMLCanvasElement | null = null;
    let timeSeriesChartInstance: ChartInstance | null = null;
    let sessionSeries: SessionPoint[] = [];
    let sessionPredictionSeries: SessionPoint[] = [];
    let combinedSessionSeries: SessionPoint[] = [];
    let hasSessionTimeline = false;
    let sessionDomain: { min: number | null; max: number | null } = { min: null, max: null };
    const DEFAULT_SESSION_WINDOW_DAYS = 90;

    type ScenarioMode = 'auto' | 'overage' | 'waste';
    type SessionPoint = { date: string; power_kw: number };
    type ScenarioSummary = {
        badge: string;
        title: string;
        highlight: string;
        note: string;
        description: string;
        metricLabel: string;
        metricValue: string;
        extraLabel?: string;
        extraValue?: string;
        extraNote?: string;
    } | null;
    type ShortfallDailyPoint = {
        date: string;
        simulated_peak_kw: number;
        overshoot_kw: number;
        historical_peak_kw?: number;
        risk_factor?: number;
    };
    type ShortfallScenario = {
        contract_kw: number;
        overshoot_probability: number;
        expected_overshoot_kw: number;
        p90_overshoot_kw: number;
        model_source?: string;
        updated_at?: string;
        daily_projection: ShortfallDailyPoint[];
    };
    const scenarioOptions: { value: ScenarioMode; label: string; helper: string }[] = [
        { value: 'auto', label: 'AI 추천 기준', helper: '기존 최적화 결과에 따른 기본 권장치' },
        { value: 'overage', label: '과다 계약 체크', helper: '초과 계약 위험을 최소화하는 보수적 선택' },
        { value: 'waste', label: '과소 계약 대비', helper: '최근 실측 데이터를 기준으로 과소 위험 점검' }
    ];
    let selectedScenario: ScenarioMode = 'auto';
    let selectedScenarioMeta = scenarioOptions[0];
    let scenarioSummary: ScenarioSummary = null;
    let q90 = 0;
    let historicalMax = 0;
    let selectedContractKw: number | null = null;
    let manualCandidate: any = null;
    let isManualUndershoot = false;
    let projectedPeakKw = 0;
    let shortfallScenarios: ShortfallScenario[] = [];
    let activeShortfallScenario: ShortfallScenario | null = null;
    let shortfallDailyProjection: ShortfallDailyPoint[] = [];
    let defaultRecentRange: { min: number | null; max: number | null } = { min: null, max: null };
    type OverfitSignal = {
        isRisk: boolean;
        mae: number | null;
        relativeError: number | null;
        coverageDays: number;
    };
    let overfitSignal: OverfitSignal = {
        isRisk: false,
        mae: null,
        relativeError: null,
        coverageDays: 0
    };
    
    async function ensureChartModules() {
        if (chartReady) {
            return;
        }
        const [
            { default: Chart },
            { default: annotation },
            zoomModule
        ] = await Promise.all([
            import('chart.js/auto'),
            import('chartjs-plugin-annotation'),
            import('chartjs-plugin-zoom'),
            import('chartjs-adapter-date-fns')
        ]);
        const zoomPlugin = (zoomModule && zoomModule.default) || zoomModule;
        Chart.register(annotation, zoomPlugin);
        ChartCtor = Chart;
        chartReady = true;
    }
    
    // 다크모드 감지
    function detectDarkMode() {
        if (typeof window !== 'undefined') {
            // Tailwind dark mode 클래스 체크
            isDarkMode = document.documentElement.classList.contains('dark');
            
            // 만약 Tailwind dark 클래스가 없으면 시스템 설정 체크
            if (!isDarkMode) {
                isDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
            }
        }
        return isDarkMode;
    }
    
    // 분포 데이터에서 히스토그램 생성
    function generateHistogram(distribution: number[], bins: number = 30) {
        if (!distribution || distribution.length === 0) return [];
        
        const min = Math.min(...distribution);
        const max = Math.max(...distribution);
        const range = max - min;
        const binWidth = range / bins;

        if (range === 0 || binWidth === 0) {
            return [
                {
                    x: min,
                    y: distribution.length
                }
            ];
        }
        
        const histogram = Array(bins).fill(0);
        distribution.forEach(value => {
            const binIndex = Math.min(Math.floor((value - min) / binWidth), bins - 1);
            histogram[binIndex]++;
        });
        
        return histogram.map((count, i) => ({
            x: min + (i + 0.5) * binWidth,
            y: count
        }));
    }

    function normalPdf(x: number, mean: number, stdDev: number) {
        if (stdDev <= 0) return 0;
        const coeff = 1 / (stdDev * Math.sqrt(2 * Math.PI));
        const exponent = Math.exp(-0.5 * Math.pow((x - mean) / stdDev, 2));
        return coeff * exponent;
    }

    function normalizeSessionSeries(series?: any[] | null): SessionPoint[] {
        if (!Array.isArray(series) || series.length === 0) {
            return [];
        }

        return series
            .map((entry) => {
                const rawDate = entry?.timestamp ?? entry?.date ?? entry?.time;
                const rawPeak = entry?.peak_kw ?? entry?.peakKw ?? entry?.predicted_peak_kw ?? entry?.predictedPeakKw ?? entry?.value;
                const parsedDate = rawDate ? new Date(rawDate) : null;
                const peakValue = rawPeak !== undefined && rawPeak !== null ? Number(rawPeak) : NaN;

                if (!parsedDate || Number.isNaN(parsedDate.getTime()) || Number.isNaN(peakValue)) {
                    return null;
                }

                return {
                    date: parsedDate.toISOString(),
                    power_kw: Number(peakValue.toFixed(2))
                } satisfies SessionPoint;
            })
            .filter((point): point is SessionPoint => point !== null)
            .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    }

    function computeSessionDomain(points: SessionPoint[]) {
        if (!points.length) {
            return { min: null, max: null };
        }
        const times = points.map((point) => new Date(point.date).getTime());
        return {
            min: Math.min(...times),
            max: Math.max(...times)
        };
    }

    function computeRecentRange(domain: { min: number | null; max: number | null }, days = DEFAULT_SESSION_WINDOW_DAYS) {
        if (!domain.max) {
            return { min: null, max: null };
        }
        const dayMs = 24 * 60 * 60 * 1000;
        const minCandidate = domain.max - days * dayMs;
        return {
            min: domain.min ? Math.max(domain.min, minCandidate) : minCandidate,
            max: domain.max
        };
    }

    function smoothChronologicalSeries(entries: { date: string; value: number }[], windowSize = 8) {
        if (!Array.isArray(entries) || entries.length === 0) {
            return [];
        }
        const sorted = [...entries].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
        const buffer: number[] = [];
        let sum = 0;
        return sorted.map(entry => {
            const value = Number(entry.value) || 0;
            buffer.push(value);
            sum += value;
            if (buffer.length > windowSize) {
                sum -= buffer.shift() ?? 0;
            }
            const avg = buffer.length > 0 ? sum / buffer.length : value;
            return {
                x: new Date(entry.date).getTime(),
                y: Number(avg.toFixed(2))
            } satisfies Point;
        });
    }

    function aggregateDailyPeaks(points: SessionPoint[]) {
        const map = new Map<string, number>();
        points.forEach(point => {
            const key = toDateKey(point.date);
            const current = map.get(key) ?? Number.NEGATIVE_INFINITY;
            if (point.power_kw > current) {
                map.set(key, point.power_kw);
            }
        });
        return map;
    }

    function toDateKey(dateInput: string) {
        const ts = new Date(dateInput);
        if (Number.isNaN(ts.getTime())) {
            return '';
        }
        return ts.toISOString().slice(0, 10);
    }

    function computeOverfitSignal(sessionPoints: SessionPoint[], projectionPoints: ShortfallDailyPoint[]): OverfitSignal {
        const base: OverfitSignal = { isRisk: false, mae: null, relativeError: null, coverageDays: 0 };
        if (!sessionPoints.length || !projectionPoints.length) {
            return base;
        }
        const dailyPeaks = aggregateDailyPeaks(sessionPoints);
        let sampleCount = 0;
        let errorSum = 0;
        let actualSum = 0;
        projectionPoints.forEach(point => {
            const key = toDateKey(point.date);
            if (!key) {
                return;
            }
            const actual = dailyPeaks.get(key);
            if (actual === undefined) {
                return;
            }
            sampleCount += 1;
            errorSum += Math.abs(actual - point.simulated_peak_kw);
            actualSum += actual;
        });
        if (sampleCount < 5) {
            return { ...base, coverageDays: sampleCount };
        }
        const mae = errorSum / sampleCount;
        const avgActual = actualSum / sampleCount;
        const relativeError = avgActual > 0 ? mae / avgActual : null;
        const isRisk = relativeError !== null && relativeError > 0.35;
        return {
            isRisk,
            mae: Number(mae.toFixed(2)),
            relativeError: relativeError !== null ? Number(relativeError.toFixed(3)) : null,
            coverageDays: sampleCount
        };
    }

    function normalizeShortfallProjection(series?: any[] | null): ShortfallDailyPoint[] {
        if (!Array.isArray(series) || series.length === 0) {
            return [];
        }

        return series
            .map((entry) => {
                const rawDate = entry?.date ?? entry?.timestamp ?? entry?.day;
                const simulatedValue = entry?.simulated_peak_kw ?? entry?.simulatedPeakKw;
                const overshootValue = entry?.overshoot_kw ?? entry?.overshootKw;
                const historicalValue = entry?.historical_peak_kw ?? entry?.historicalPeakKw ?? entry?.peak_kw;
                const parsedDate = rawDate ? new Date(rawDate) : null;

                if (!parsedDate || Number.isNaN(parsedDate.getTime()) || simulatedValue === undefined) {
                    return null;
                }

                const safeSimulated = Number(simulatedValue);
                if (Number.isNaN(safeSimulated)) {
                    return null;
                }

                const overshootRaw = overshootValue !== undefined ? Number(overshootValue) : Math.max(0, safeSimulated - (entry?.contract_kw ?? 0));
                const safeOvershoot = Number.isNaN(overshootRaw) ? 0 : overshootRaw;
                let historical: number | undefined;
                if (historicalValue !== undefined && historicalValue !== null) {
                    const numericHistorical = Number(historicalValue);
                    if (!Number.isNaN(numericHistorical)) {
                        historical = Number(numericHistorical.toFixed(2));
                    }
                }

                return {
                    date: parsedDate.toISOString(),
                    simulated_peak_kw: Number(safeSimulated.toFixed(2)),
                    overshoot_kw: Number(Math.max(0, safeOvershoot).toFixed(2)),
                    historical_peak_kw: historical,
                    risk_factor: entry?.risk_factor ?? entry?.riskFactor
                } as ShortfallDailyPoint;
            })
            .filter((point): point is ShortfallDailyPoint => point !== null)
            .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    }

    function findShortfallScenario(
        scenarios: ShortfallScenario[],
        contractKw: number | null
    ): ShortfallScenario | null {
        if (!scenarios.length) {
            return null;
        }

        if (contractKw === null || contractKw === undefined) {
            return scenarios[0];
        }

        const exactMatch = scenarios.find((scenario) => scenario.contract_kw === contractKw);
        if (exactMatch) {
            return exactMatch;
        }

        return scenarios.reduce((closest, scenario) => {
            if (!closest) {
                return scenario;
            }
            const currentDelta = Math.abs(scenario.contract_kw - contractKw);
            const bestDelta = Math.abs(closest.contract_kw - contractKw);
            return currentDelta < bestDelta ? scenario : closest;
        }, scenarios[0]);
    }

    function getModelLabel(source?: string): string {
        if (!source) {
            return '딥러닝 모델';
        }
        if (source === 'lstm_mc_dropout') {
            return 'LSTM Monte Carlo';
        }
        return source.replace(/_/g, ' ').toUpperCase();
    }

    function buildLstmUndershootProjection(contractKw: number) {
        if (!ensemblePrediction?.lstm || predictionDistribution.length === 0) {
            return [];
        }

        const { prediction_kw, uncertainty_kw, weight } = ensemblePrediction.lstm;
        const mean = prediction_kw;
        const stdDev = Math.max(uncertainty_kw, 0.5);
        const histogramPeak = histogram.reduce((max, bin) => Math.max(max, bin.y ?? 0), 0);
        const scaleBase = histogramPeak || Math.max(1, predictionDistribution.length / 12);
        const steps = 80;
        const start = Math.max(0, Math.min(contractKw - stdDev * 2, mean - stdDev * 4));
        const end = Math.max(contractKw + stdDev * 3, mean + stdDev * 3);
        const emphasis = 1 + (weight || 0.5);

        const points: { x: number; y: number }[] = [];
        for (let i = 0; i <= steps; i++) {
            const x = start + ((end - start) * i) / steps;
            const baseDensity = normalPdf(x, mean, stdDev);
            let adjusted = baseDensity * scaleBase * emphasis;

            if (x < contractKw) {
                const deficitRatio = (contractKw - x) / Math.max(contractKw, 1);
                adjusted *= Math.max(0.2, 1 - deficitRatio * 0.9);
            } else {
                const overshootRatio = (x - contractKw) / Math.max(stdDev * 1.5, 1);
                adjusted *= 1 + Math.min(1.5, overshootRatio);
            }

            points.push({
                x: Number(x.toFixed(2)),
                y: Number(adjusted.toFixed(2))
            });
        }

        return points;
    }

    function safeMax(arr: number[]): number {
        if (!arr || arr.length === 0) return 0;
        return Math.max(...arr);
    }
    
    // 분위수 계산
    function percentile(arr: number[], p: number): number {
        if (!arr || arr.length === 0) return 0;
        const sorted = [...arr].sort((a, b) => a - b);
        const index = (p / 100) * (sorted.length - 1);
        const lower = Math.floor(index);
        const upper = Math.ceil(index);
        const weight = index - lower;
        return sorted[lower] * (1 - weight) + sorted[upper] * weight;
    }
    
    // Chart.js로 차트 생성
    function createChart() {
        if (!chartCanvas || predictionDistribution.length === 0 || !ChartCtor) return;
        
        const histogramData = histogram.length ? histogram : generateHistogram(predictionDistribution);
        const q5Val = percentile(predictionDistribution, 5);
        const q95Val = percentile(predictionDistribution, 95);
        const optimalKw = optimalCandidate?.contract_kw || 0;
        const manualKw = manualCandidate?.contract_kw || optimalKw;
        const projectedMax = projectedPeakKw || q95Val;
        const showUnderProjection = manualCandidate && isManualUndershoot && projectedMax > manualKw;
        
        // 기존 차트 제거
        if (chartInstance) {
            chartInstance.destroy();
        }
        
        // 다크모드 색상
        const textColor = isDarkMode ? '#e2e8f0' : '#1f2937';
        const gridColor = isDarkMode ? 'rgba(148, 163, 184, 0.2)' : 'rgba(0, 0, 0, 0.1)';
        
        // annotation 구성
        const annotations: Record<string, any> = {
            q5Line: {
                type: 'line',
                xMin: Math.round(q5Val),
                xMax: Math.round(q5Val),
                borderColor: '#9c27b0',
                borderWidth: 2,
                borderDash: [5, 5],
                label: {
                    content: `Q₅: ${Math.round(q5Val)}kW`,
                    display: true,
                    position: 'start',
                    backgroundColor: '#9c27b0',
                    color: 'white',
                    font: { size: 11, weight: 'bold' }
                }
            },
            q95Line: {
                type: 'line',
                xMin: Math.round(q95Val),
                xMax: Math.round(q95Val),
                borderColor: '#9c27b0',
                borderWidth: 2,
                borderDash: [5, 5],
                label: {
                    content: `Q₉₅: ${Math.round(q95Val)}kW`,
                    display: true,
                    position: 'end',
                    backgroundColor: '#9c27b0',
                    color: 'white',
                    font: { size: 11, weight: 'bold' }
                }
            },
            optimalLine: {
                type: 'line',
                xMin: optimalKw,
                xMax: optimalKw,
                borderColor: '#10b981',
                borderWidth: 3,
                borderDash: [10, 5],
                label: {
                    content: `최적: ${optimalKw}kW`,
                    display: true,
                    position: 'center',
                    backgroundColor: '#10b981',
                    color: 'white',
                    font: { size: 12, weight: 'bold' }
                }
            }
        };

        if (manualCandidate) {
            annotations.manualLine = {
                type: 'line',
                xMin: manualKw,
                xMax: manualKw,
                borderColor: '#f97316',
                borderWidth: 3,
                borderDash: [6, 4],
                label: {
                    content: `선택: ${manualKw}kW`,
                    display: true,
                    position: 'center',
                    backgroundColor: '#f97316',
                    color: '#fff',
                    font: { size: 12, weight: 'bold' }
                }
            };
        }

        if (showUnderProjection && manualKw < projectedMax) {
            annotations.underProjection = {
                type: 'box',
                xMin: manualKw,
                xMax: Math.round(projectedMax),
                backgroundColor: 'rgba(14, 165, 233, 0.12)',
                borderColor: 'rgba(14, 165, 233, 0.6)',
                borderWidth: 1,
                label: {
                    display: true,
                    position: 'start',
                    backgroundColor: 'rgba(14, 165, 233, 0.9)',
                    color: '#fff',
                    content: `과소 리스크 예상 ${Math.round(projectedMax)}kW`,
                    font: { size: 11, weight: '600' }
                }
            };
        }

        const datasets: any[] = [
            {
                label: '예측 분포',
                data: histogramData.map(h => ({ x: h.x, y: h.y })),
                borderColor: '#3b82f6',
                backgroundColor: (context) => {
                    const ctx = context.chart.ctx;
                    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
                    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.5)');
                    gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');
                    return gradient;
                },
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
            }
        ];

        if (lstmProjection.length > 0) {
            datasets.push({
                label: 'LSTM 과소 계약 시 분포',
                data: lstmProjection,
                borderColor: '#dc2626',
                backgroundColor: 'rgba(220, 38, 38, 0.18)',
                borderWidth: 2,
                borderDash: [8, 4],
                fill: true,
                tension: 0.35,
                pointRadius: 0,
                pointHoverRadius: 0,
            });
        }

        // Chart.js 차트 생성
        chartInstance = new ChartCtor(chartCanvas, {
            type: 'line',
            data: {
                datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: isDarkMode ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                        titleColor: textColor,
                        bodyColor: textColor,
                        borderColor: isDarkMode ? '#475569' : '#e5e7eb',
                        borderWidth: 1,
                        callbacks: {
                            label: function(context) {
                                return `빈도: ${context.parsed.y}`;
                            }
                        }
                    },
                    annotation: {
                        annotations
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        title: {
                            display: true,
                            text: '전력 (kW)',
                            color: textColor,
                            font: { size: 13, weight: 'bold' }
                        },
                        ticks: {
                            color: textColor,
                            maxTicksLimit: 10
                        },
                        grid: {
                            color: gridColor
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: '빈도',
                            color: textColor,
                            font: { size: 13, weight: 'bold' }
                        },
                        ticks: {
                            color: textColor
                        },
                        grid: {
                            color: gridColor
                        }
                    }
                }
            }
        });
    }

    function createTimeSeriesChart() {
        if (!timeSeriesCanvas || !ChartCtor) {
            return;
        }

        if (timeSeriesChartInstance) {
            timeSeriesChartInstance.destroy();
            timeSeriesChartInstance = null;
        }

        if (!hasSessionTimeline) {
            return;
        }

        const textColor = isDarkMode ? '#e2e8f0' : '#1f2937';
        const gridColor = isDarkMode ? 'rgba(148, 163, 184, 0.2)' : 'rgba(0, 0, 0, 0.08)';

        const chronologicalSessions = sessionSeries.map(point => ({
            x: new Date(point.date).getTime(),
            y: point.power_kw
        }));

        const predictedSessions = sessionPredictionSeries.map(point => ({
            x: new Date(point.date).getTime(),
            y: point.power_kw
        }));

        const manualKw = selectedContractKw ?? optimalCandidate?.contract_kw ?? null;
        const predictedOvershootFill = manualKw !== null
            ? predictedSessions.map(point => ({
                x: point.x,
                y: point.y > manualKw ? point.y : null
            }))
            : [];

        const projectionDataset = shortfallDailyProjection.map(point => ({
            x: new Date(point.date).getTime(),
            y: point.simulated_peak_kw
        }));
        const smoothedProjectionLine = smoothChronologicalSeries(
            shortfallDailyProjection.map(point => ({ date: point.date, value: point.simulated_peak_kw })),
            6
        );

        const hasSimulation = manualKw !== null && projectionDataset.length > 0;
        const overshootFillDataset = hasSimulation
            ? shortfallDailyProjection.map(point => ({
                x: new Date(point.date).getTime(),
                y: point.simulated_peak_kw > manualKw ? point.simulated_peak_kw : null
            }))
            : [];

        const annotations: Record<string, any> = {};

        if (manualKw !== null) {
            annotations.contractLine = {
                type: 'line',
                yMin: manualKw,
                yMax: manualKw,
                borderColor: '#f97316',
                borderWidth: 2,
                borderDash: [6, 4],
                label: {
                    content: `계약선: ${manualKw}kW`,
                    display: true,
                    position: 'end',
                    backgroundColor: '#f97316',
                    color: '#fff',
                    font: { size: 11, weight: 'bold' }
                }
            };
        }

        const domainMin = sessionDomain.min ?? null;
        const domainMax = sessionDomain.max ?? null;
        const initialRange = defaultRecentRange.min && defaultRecentRange.max
            ? { ...defaultRecentRange }
            : { min: domainMin, max: domainMax };

        timeSeriesChartInstance = new ChartCtor(timeSeriesCanvas, {
            type: 'line',
            data: {
                datasets: (() => {
                    const baseDatasets: any[] = [];

                    if (sessionSeries.length > 0) {
                        baseDatasets.push({
                            label: '실제 세션 궤적',
                            data: chronologicalSessions,
                            borderColor: '#0ea5e9',
                            backgroundColor: 'rgba(14, 165, 233, 0.08)',
                            borderWidth: 1.8,
                            pointRadius: 0,
                            pointHoverRadius: 2,
                            tension: 0.2,
                            fill: false,
                            order: 3,
                            parsing: false,
                            spanGaps: false
                        });
                    }

                    if (sessionPredictionSeries.length > 0) {
                        if (manualKw !== null) {
                            baseDatasets.push({
                                label: '예측 초과 영역',
                                data: predictedOvershootFill,
                                borderColor: 'rgba(139, 92, 246, 0)',
                                backgroundColor: 'rgba(139, 92, 246, 0.15)',
                                borderWidth: 0,
                                pointRadius: 0,
                                pointHoverRadius: 0,
                                tension: 0.3,
                                fill: { target: { value: manualKw } },
                                order: 1,
                                parsing: false,
                                spanGaps: true
                            });
                        }
                        baseDatasets.push({
                            label: '세션 예측 궤적',
                            data: predictedSessions,
                            borderColor: '#8b5cf6',
                            backgroundColor: 'rgba(139, 92, 246, 0.12)',
                            borderWidth: 1.6,
                            pointRadius: 0,
                            pointHoverRadius: 2,
                            tension: 0.3,
                            fill: false,
                            order: manualKw !== null ? 2 : 1,
                            parsing: false,
                            spanGaps: false
                        });
                    }

                    if (hasSimulation) {
                        baseDatasets.push({
                            label: '과소 위험 영역',
                            data: overshootFillDataset,
                            borderColor: 'rgba(248, 113, 113, 0)',
                            backgroundColor: 'rgba(248, 113, 113, 0.2)',
                            pointRadius: 0,
                            pointHoverRadius: 0,
                            tension: 0.2,
                            borderWidth: 0,
                            fill: manualKw !== null ? { target: { value: manualKw } } : false,
                            order: 0,
                            spanGaps: true,
                            parsing: false
                        });
                        baseDatasets.push({
                            label: '딥러닝 예측 곡선',
                            data: smoothedProjectionLine.length > 0 ? smoothedProjectionLine : projectionDataset,
                            borderColor: '#fb7185',
                            backgroundColor: 'rgba(251, 113, 133, 0.12)',
                            borderWidth: 2,
                            pointRadius: 0,
                            pointHoverRadius: 2,
                            tension: 0.35,
                            fill: false,
                            order: 1,
                            parsing: false
                        });
                    }

                    return baseDatasets;
                })()
            },
            options: {
                parsing: false,
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'nearest',
                    intersect: false
                },
                scales: {
                    x: {
                        type: 'time',
                        min: initialRange.min ?? undefined,
                        max: initialRange.max ?? undefined,
                        time: {
                            tooltipFormat: 'yyyy-MM-dd',
                            unit: 'month',
                            displayFormats: {
                                day: 'MM-dd',
                                month: 'yyyy-MM'
                            }
                        },
                        adapters: {
                            date: {}
                        },
                        ticks: {
                            color: textColor
                        },
                        grid: {
                            color: gridColor
                        },
                        title: {
                            display: true,
                            text: '시간 (일)',
                            color: textColor,
                            font: { size: 13, weight: 'bold' }
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: '전력 (kW)',
                            color: textColor,
                            font: { size: 13, weight: 'bold' }
                        },
                        ticks: {
                            color: textColor
                        },
                        grid: {
                            color: gridColor
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            title: items => items[0]?.parsed?.x ? new Date(items[0].parsed.x).toLocaleDateString('ko-KR') : '',
                            label: context => {
                                const value = context.parsed?.y;
                                if (value === null || value === undefined || Number.isNaN(value)) {
                                    return '';
                                }
                                const formatted = Number(value).toFixed(1);
                                const label = context.dataset?.label ?? '';
                                if (label === '딥러닝 예측 곡선') {
                                    return `예측 피크: ${formatted} kW`;
                                }
                                if (label === '과소 위험 영역') {
                                    return `과소 영역 상한: ${formatted} kW`;
                                }
                                if (label === '실제 세션 궤적') {
                                    return `실제 세션: ${formatted} kW`;
                                }
                                if (label === '세션 예측 궤적') {
                                    return `예측 세션: ${formatted} kW`;
                                }
                                if (label === '예측 초과 영역') {
                                    return `계약선 초과 예측: ${formatted} kW`;
                                }
                                return `세션 샘플: ${formatted} kW`;
                            }
                        },
                        backgroundColor: isDarkMode ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                        titleColor: textColor,
                        bodyColor: textColor,
                        borderColor: isDarkMode ? '#475569' : '#e5e7eb',
                        borderWidth: 1
                    },
                    annotation: {
                        annotations
                    },
                    zoom: {
                        limits: {
                            x: {
                                min: domainMin ?? undefined,
                                max: domainMax ?? undefined
                            }
                        },
                        zoom: {
                            wheel: {
                                enabled: true
                            },
                            pinch: {
                                enabled: true
                            },
                            mode: 'x'
                        },
                        pan: {
                            enabled: true,
                            mode: 'x'
                        }
                    }
                }
            }
        });
    }

    function applyTimelineRange(range: { min: number | null; max: number | null }) {
        if (!timeSeriesChartInstance) {
            return;
        }
        if (range.min !== null) {
            timeSeriesChartInstance.options.scales!.x!.min = range.min;
        } else {
            delete timeSeriesChartInstance.options.scales!.x!.min;
        }
        if (range.max !== null) {
            timeSeriesChartInstance.options.scales!.x!.max = range.max;
        } else {
            delete timeSeriesChartInstance.options.scales!.x!.max;
        }
        timeSeriesChartInstance.update('none');
    }

    function showFullTimeline() {
        applyTimelineRange({ min: sessionDomain.min, max: sessionDomain.max });
        if (timeSeriesChartInstance && typeof timeSeriesChartInstance.resetZoom === 'function') {
            timeSeriesChartInstance.resetZoom();
        }
    }

    function showRecentTimeline() {
        const range = computeRecentRange(sessionDomain);
        applyTimelineRange(range);
    }

    function computeScenarioSummary(
        mode: ScenarioMode,
        optimal: any,
        candidates: any[],
        q90Value: number,
        historicalMaxValue: number,
        projectedMaxValue: number
    ): ScenarioSummary {
        if (!optimizationData || !optimal) {
            return null;
        }

        const baseSummary: ScenarioSummary = {
            badge: '기본 추천',
            title: 'AI 최적화 기준',
            highlight: `${optimizationData.optimal_contract_kw}kW`,
            note: '추천 로직 그대로 유지',
            description: '10kW 단위 최적화와 리스크 스코어를 반영한 기본 권장 계약전력입니다.',
            metricLabel: '초과 · 과소 위험',
            metricValue: `초과 ${Math.round(optimal.overage_probability ?? 0)}% · 과소 ${Math.round(optimal.waste_probability ?? 0)}%`
        };

        if (mode === 'auto') {
            return baseSummary;
        }

        if (mode === 'overage' && candidates.length > 0) {
            const conservativeCandidate = candidates.reduce((best, current) => {
                if (!best) return current;
                return current.overage_probability < best.overage_probability ? current : best;
            }, candidates[0]);

            return {
                badge: '과다 체크',
                title: '보수적 검증',
                highlight: `${conservativeCandidate.contract_kw}kW`,
                note: '사용자 수동 선택 기준',
                description: '초과(Overage) 확률이 가장 낮은 후보를 표시하여 과다 계약 시나리오를 직접 점검할 수 있습니다.',
                metricLabel: '초과 위험 (Overage)',
                metricValue: `${Math.round(conservativeCandidate.overage_probability)}%`,
                extraLabel: '해당 후보 비용',
                extraValue: `${Math.round(conservativeCandidate.expected_annual_cost / 10000)}만원/년`,
                extraNote: 'AI 추천 결과에는 영향을 주지 않습니다.'
            };
        }

        const q90Rounded = Math.round(q90Value);
        const guardKw = q90Rounded > 0 ? Math.ceil(q90Rounded / 10) * 10 : optimizationData.optimal_contract_kw;
        const projectedRounded = projectedMaxValue ? Math.round(projectedMaxValue) : Math.round(historicalMaxValue);
        return {
            badge: '과소 대비',
            title: '실측 기반 보강',
            highlight: `${guardKw}kW`,
            note: '최근 데이터 참고',
            description: '과소(Waste) 시나리오 선택 시 최근 실측 분포의 90% 구간과 최대값을 참고해 수동 판단을 돕습니다.',
            metricLabel: '실측 분포 지표',
            metricValue: `Q90 ${q90Rounded}kW · Max ${projectedRounded}kW`,
            extraLabel: '참고 계약안',
            extraValue: `${guardKw}kW 제안`,
            extraNote: '과거 데이터 기반 참고치'
        };
    }
    
    // 다크모드 변경 감지
    function setupDarkModeListener() {
        if (typeof window === 'undefined') return;
        
        // MutationObserver로 dark 클래스 변경 감지
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.attributeName === 'class') {
                    const newDarkMode = detectDarkMode();
                    if (newDarkMode !== isDarkMode) {
                        isDarkMode = newDarkMode;
                        createChart();
                        createTimeSeriesChart();
                    }
                }
            });
        });
        
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['class']
        });
        
        // 시스템 설정 변경 감지
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        const handleChange = (e: MediaQueryListEvent) => {
            isDarkMode = e.matches;
            createChart();
            createTimeSeriesChart();
        };
        mediaQuery.addEventListener('change', handleChange);
        
        return () => {
            observer.disconnect();
            mediaQuery.removeEventListener('change', handleChange);
        };
    }
    
    onMount(() => {
        isDarkMode = detectDarkMode();
        ensureChartModules().then(() => {
            createChart();
            createTimeSeriesChart();
        });
        const cleanup = setupDarkModeListener();
        
        return cleanup;
    });
    
    onDestroy(() => {
        if (chartInstance) {
            chartInstance.destroy();
        }
        if (timeSeriesChartInstance) {
            timeSeriesChartInstance.destroy();
        }
    });
    
    // 데이터 변경 시 차트 업데이트
    $: if (predictionDistribution.length > 0 && chartCanvas && chartReady) {
        manualCandidate;
        isManualUndershoot;
        projectedPeakKw;
        lstmProjection;
        createChart();
    }

    $: sessionSeries = normalizeSessionSeries(optimizationData?.session_power_series);
    $: sessionPredictionSeries = normalizeSessionSeries(optimizationData?.session_prediction_series);
    $: combinedSessionSeries = [...sessionSeries, ...sessionPredictionSeries];
    $: sessionDomain = computeSessionDomain(combinedSessionSeries);
    $: defaultRecentRange = computeRecentRange(sessionDomain);
    $: hasSessionTimeline = combinedSessionSeries.length > 0;

    $: if (chartReady && timeSeriesCanvas) {
        sessionSeries;
        sessionPredictionSeries;
        combinedSessionSeries;
        hasSessionTimeline;
        sessionDomain;
        defaultRecentRange;
        shortfallDailyProjection;
        activeShortfallScenario;
        isDarkMode;
        manualCandidate;
        optimalCandidate;
        createTimeSeriesChart();
    }
    
    $: histogram = generateHistogram(predictionDistribution);
    $: q5 = percentile(predictionDistribution, 5);
    $: q95 = percentile(predictionDistribution, 95);
    $: q90 = percentile(predictionDistribution, 90);
    $: historicalMax = safeMax(predictionDistribution);
    $: projectedPeakKw = Math.max(percentile(predictionDistribution, 99), historicalMax || 0);
    $: optimalCandidate = optimizationData?.optimal_candidate;
    $: allCandidates = optimizationData?.all_candidates || [];
    $: selectedScenarioMeta = scenarioOptions.find(option => option.value === selectedScenario) || scenarioOptions[0];
    $: scenarioSummary = computeScenarioSummary(selectedScenario, optimalCandidate, allCandidates, q90, historicalMax, projectedPeakKw);
    $: if (allCandidates.length > 0) {
        const defaultKw = optimizationData?.optimal_candidate?.contract_kw ?? allCandidates[0].contract_kw;
        const hasSelection = selectedContractKw !== null && allCandidates.some(candidate => candidate.contract_kw === selectedContractKw);
        if (!hasSelection) {
            selectedContractKw = defaultKw;
        }
    } else {
        selectedContractKw = null;
    }
    $: manualCandidate = allCandidates.find(candidate => candidate.contract_kw === selectedContractKw) || null;
    $: isManualUndershoot = !!manualCandidate && (
        (manualCandidate.waste_probability ?? 0) > 50 ||
        manualCandidate.contract_kw < q90
    );
    $: shortfallScenarios = Array.isArray(optimizationData?.contract_shortfall_simulations)
        ? optimizationData.contract_shortfall_simulations
        : [];
    $: activeShortfallScenario = findShortfallScenario(
        shortfallScenarios,
        manualCandidate?.contract_kw ?? optimalCandidate?.contract_kw ?? null
    );
    $: shortfallDailyProjection = normalizeShortfallProjection(activeShortfallScenario?.daily_projection);
    $: overfitSignal = computeOverfitSignal(sessionSeries, shortfallDailyProjection);

    $: if (manualCandidate && isManualUndershoot) {
        lstmProjection = buildLstmUndershootProjection(manualCandidate.contract_kw);
    } else {
        lstmProjection = [];
    }

    function handleCandidateSelect(contractKw: number) {
        selectedContractKw = contractKw;
    }
</script>

<div class="optimization-chart" bind:this={chartContainer}>
    <h3 class="chart-title">10kW 단위 계약전력 최적화 알고리즘</h3>
    
    <div class="chart-sections">
        <!-- Section 1: 예측분포 (Chart.js) -->
        <div class="section prediction-distribution">
            <h4>예측분포 생성 결과</h4>
            <div class="chart-wrapper">
                <canvas bind:this={chartCanvas} id="prediction-chart"></canvas>
            </div>
            <div class="chart-legend">
                <div class="legend-item">
                    <span class="legend-color" style="background: #9c27b0;"></span>
                    <span class="legend-text">Q₅: {Math.round(q5)}kW, Q₉₅: {Math.round(q95)}kW</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background: #10b981;"></span>
                    <span class="legend-text">최적 계약: {optimalCandidate ? optimalCandidate.contract_kw : 0}kW</span>
                </div>
                {#if lstmProjection.length > 0}
                    <div class="legend-item">
                        <span class="legend-color projection"></span>
                        <span class="legend-text">LSTM 과소 계약 시 예상 분포</span>
                    </div>
                {/if}
                {#if shortfallDailyProjection.length > 0}
                    <div class="legend-item">
                        <span class="legend-color overshoot"></span>
                        <span class="legend-text">딥러닝 과소 시뮬레이션</span>
                    </div>
                {/if}
            </div>
        </div>

        <div class="section time-series">
            <div class="section-header">
                <h4>세션 기반 순간전력 추이</h4>
                {#if hasSessionTimeline}
                    <div class="chart-actions">
                        <button type="button" class="reset-zoom" on:click={showRecentTimeline}>최근 3개월</button>
                        <button type="button" class="reset-zoom" on:click={showFullTimeline}>전체 기간</button>
                        <span class="zoom-hint">스크롤 · 터치로 확대/축소</span>
                    </div>
                {/if}
            </div>

            {#if hasSessionTimeline}
                <div class="chart-wrapper time-domain-chart">
                    <canvas bind:this={timeSeriesCanvas}></canvas>
                </div>
                <p class="chart-footnote">
                    모든 충전 세션(실측 + 모델 예측)의 순간최대 전력을 시계열로 표현했습니다. 기본 뷰는 최근 3개월이며 확대/축소로 전체 기간을 탐색할 수 있습니다. 선택한 계약전력 시나리오가 있으면 예측 궤적이 계약선을 넘을 때 보라색 초과 영역으로 강조되어, 제한이 없을 경우 얼마나 초과할 수 있는지 직관적으로 확인할 수 있습니다.
                    {#if shortfallDailyProjection.length > 0}
                        딥러닝 기반 예측 곡선(분홍색)과 과소 위험 영역(붉은 음영)으로 계약선 초과 가능성을 강조했습니다.
                    {/if}
                </p>
                {#if overfitSignal.coverageDays >= 3}
                    <div class="overfit-banner" class:risk={overfitSignal.isRisk}>
                        <div class="overfit-header">
                            <span class="status-chip">{overfitSignal.isRisk ? '과적합 의심' : '일관성 양호'}</span>
                            <span class="overfit-meta">
                                MAE {overfitSignal.mae !== null ? `${overfitSignal.mae.toFixed(1)}kW` : '측정 불가'} · 비교 {overfitSignal.coverageDays}일
                                {#if overfitSignal.relativeError !== null}
                                    · 상대 오차 {(overfitSignal.relativeError * 100).toFixed(1)}%
                                {/if}
                            </span>
                        </div>
                        <p>
                            {#if overfitSignal.isRisk}
                                최근 실측 패턴과 예측 추세가 다르게 움직여 과적합 가능성이 있습니다. 최신 데이터를 반영하거나 하이퍼파라미터를 조정해 주세요.
                            {:else}
                                예측 곡선이 실측 추세와 충분히 일치하여 안정적으로 일반화되고 있습니다.
                            {/if}
                        </p>
                    </div>
                {/if}
                {#if activeShortfallScenario && selectedContractKw !== null && shortfallDailyProjection.length > 0}
                    <div class="simulation-summary">
                        <div class="summary-header">
                            <span>{selectedContractKw}kW 기준 딥러닝 과소 시뮬레이션</span>
                            <span class="model-chip">{getModelLabel(activeShortfallScenario.model_source)}</span>
                        </div>
                        <div class="summary-grid">
                            <div class="summary-metric">
                                <span>과소 확률</span>
                                <strong>{activeShortfallScenario.overshoot_probability.toFixed(1)}%</strong>
                            </div>
                            <div class="summary-metric">
                                <span>예상 초과 폭 (평균)</span>
                                <strong>{activeShortfallScenario.expected_overshoot_kw.toFixed(1)}kW</strong>
                            </div>
                            <div class="summary-metric">
                                <span>P90 초과 폭</span>
                                <strong>{activeShortfallScenario.p90_overshoot_kw.toFixed(1)}kW</strong>
                            </div>
                        </div>
                    </div>
                {/if}
            {:else}
                <div class="empty-state">
                    세션 기반 피크 데이터가 부족하여 시계열 그래프를 표시할 수 없습니다.
                </div>
            {/if}
        </div>
    </div>
    
    <!-- Section 3: 비용 산정 테이블 -->
    <div class="section cost-table">
        <h4>확률 및 비용 산정 모듈</h4>
        <div class="table-info">
            <div class="info-badge">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="16" x2="12" y2="12"/>
                    <line x1="12" y1="8" x2="12.01" y2="8"/>
                </svg>
                <span>각 행을 클릭하면 선택한 계약전력 기준으로 그래프 상 선형 안내선이 갱신됩니다.</span>
            </div>
        </div>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th rowspan="2" class="sticky-col">후보<br/><small>(kW)</small></th>
                        <th colspan="2" class="group-header overage-group">과다 계약 (Overage)</th>
                        <th colspan="2" class="group-header waste-group">과소 계약 (Waste)</th>
                        <th rowspan="2" class="total-header">총비용<br/><small>(만원/년)</small></th>
                        <th rowspan="2" class="remark-header">비고</th>
                    </tr>
                    <tr>
                        <th class="sub-header">확률</th>
                        <th class="sub-header">기회비용<br/><small>(만원/년)</small></th>
                        <th class="sub-header">확률</th>
                        <th class="sub-header">초과금<br/><small>(만원/년)</small></th>
                    </tr>
                </thead>
                <tbody>
                    {#each allCandidates as candidate, i}
                        {@const isOptimal = candidate.contract_kw === optimalCandidate?.contract_kw}
                        {@const isSelected = candidate.contract_kw === selectedContractKw}
                        {@const overageCost = candidate.expected_annual_cost * (candidate.overage_probability / 100)}
                        {@const wasteCost = candidate.expected_annual_cost * (candidate.waste_probability / 100)}
                        
                        <tr
                            class:optimal={isOptimal}
                            class:high-overage={candidate.overage_probability > 70}
                            class:high-waste={candidate.waste_probability > 70}
                            class:selected={isSelected}
                            on:click={() => handleCandidateSelect(candidate.contract_kw)}
                        >
                            <td class="contract-value sticky-col" data-label="후보 (kW)">{candidate.contract_kw}</td>
                            <td class="overage-data" data-label="과다 계약 확률" class:highlight={candidate.overage_probability > 70}>
                                <span class="percentage">{Math.round(candidate.overage_probability)}%</span>
                            </td>
                            <td class="overage-data" data-label="과다 계약 기회비용 (만원/년)" class:highlight={candidate.overage_probability > 70}>
                                <span class="cost-value">{Math.round(overageCost / 10000)}</span>
                            </td>
                            <td class="waste-data" data-label="과소 계약 확률" class:highlight={candidate.waste_probability > 70}>
                                <span class="percentage">{Math.round(candidate.waste_probability)}%</span>
                            </td>
                            <td class="waste-data" data-label="과소 계약 초과금 (만원/년)" class:highlight={candidate.waste_probability > 70}>
                                <span class="cost-value">{Math.round(wasteCost / 10000)}</span>
                            </td>
                            <td class="total-cost" data-label="총비용 (만원/년)">
                                <span class="total-value">{Math.round(candidate.expected_annual_cost / 10000)}</span>
                                {#if isOptimal}
                                    <span class="star">★</span>
                                {/if}
                            </td>
                            <td class="remark" data-label="비고">
                                {#if isOptimal}
                                    <div class="optimal-badge">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                            <polyline points="20 6 9 17 4 12"/>
                                        </svg>
                                        <strong>최적</strong>
                                    </div>
                                {:else if candidate.waste_probability > 85}
                                    <div class="risk-badge risk-high waste">과다 리스크 높음</div>
                                {:else if candidate.waste_probability > 70}
                                    <div class="risk-badge risk-medium waste">과다 주의</div>
                                {:else if candidate.overage_probability > 85}
                                    <div class="risk-badge risk-high overage">과소 리스크 높음</div>
                                {:else if candidate.overage_probability > 70}
                                    <div class="risk-badge risk-medium overage">과소 주의</div>
                                {:else}
                                    <span class="normal">-</span>
                                {/if}
                            </td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        </div>
    </div>
</div>

<style>
    :global([data-theme="light"]) .optimization-chart {
        --container-bg: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%);
        --container-border: rgba(15, 23, 42, 0.08);
        --container-shadow: 0 18px 32px rgba(15, 23, 42, 0.08);
        --section-bg: #ffffff;
        --section-border: rgba(148, 163, 184, 0.25);
        --section-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
        --section-hover-shadow: 0 10px 28px rgba(15, 23, 42, 0.12);
        --text-primary: #0f172a;
        --text-secondary: #475569;
        --legend-color: #334155;
        --accent-primary: #4f46e5;
        --accent-secondary: #22c55e;
        --accent-tertiary: #f97316;
        --badge-bg: rgba(79, 70, 229, 0.1);
        --badge-text: #4338ca;
        --table-header-bg: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
        --table-header-text: #1e1b4b;
        --table-border: rgba(148, 163, 184, 0.35);
        --table-row-alt: #f8fafc;
        --table-total-bg: rgba(16, 185, 129, 0.12);
        --table-total-text: #065f46;
        --optimal-bg: rgba(16, 185, 129, 0.16);
        --optimal-bg-hover: rgba(16, 185, 129, 0.22);
        --optimal-text: #047857;
        --optimal-border: rgba(16, 185, 129, 0.32);
        --risk-high-bg: rgba(239, 68, 68, 0.18);
        --risk-high-text: #b91c1c;
        --risk-medium-bg: rgba(249, 115, 22, 0.2);
        --risk-medium-text: #c2410c;
        --star-color: #f59e0b;
        --output-bg: rgba(59, 130, 246, 0.12);
        --output-border: rgba(59, 130, 246, 0.24);
    }

    :global([data-theme="dark"]) .optimization-chart {
        --container-bg: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        --container-border: rgba(148, 163, 184, 0.28);
        --container-shadow: 0 18px 36px rgba(2, 6, 23, 0.6);
        --section-bg: rgba(15, 23, 42, 0.96);
        --section-border: rgba(148, 163, 184, 0.32);
        --section-shadow: 0 8px 24px rgba(2, 6, 23, 0.6);
        --section-hover-shadow: 0 12px 32px rgba(2, 6, 23, 0.7);
        --text-primary: #e2e8f0;
        --text-secondary: #cbd5f5;
        --legend-color: #cbd5f5;
        --accent-primary: #818cf8;
        --accent-secondary: #34d399;
        --accent-tertiary: #fb923c;
        --badge-bg: rgba(129, 140, 248, 0.22);
        --badge-text: #c7d2fe;
        --table-header-bg: linear-gradient(135deg, rgba(148, 163, 184, 0.28) 0%, rgba(129, 140, 248, 0.24) 100%);
        --table-header-text: #f8fafc;
        --table-border: rgba(71, 85, 105, 0.65);
        --table-row-alt: rgba(30, 41, 59, 0.82);
        --table-total-bg: rgba(16, 185, 129, 0.32);
        --table-total-text: #d1fae5;
        --optimal-bg: rgba(16, 185, 129, 0.34);
        --optimal-bg-hover: rgba(16, 185, 129, 0.44);
        --optimal-text: #d1fae5;
        --optimal-border: rgba(16, 185, 129, 0.48);
        --risk-high-bg: rgba(239, 68, 68, 0.38);
        --risk-high-text: #fecaca;
        --risk-medium-bg: rgba(249, 115, 22, 0.38);
        --risk-medium-text: #fdba74;
        --star-color: #fbbf24;
        --output-bg: rgba(59, 130, 246, 0.24);
        --output-border: rgba(59, 130, 246, 0.32);
    }

    .optimization-chart {
        background: var(--container-bg);
        border: 1px solid var(--container-border);
        border-radius: 18px;
        padding: clamp(20px, 4vw, 28px);
        box-shadow: var(--container-shadow);
        color: var(--text-primary);
    }

    .chart-title {
        text-align: center;
        font-size: clamp(1.35rem, 2vw, 1.6rem);
        font-weight: 800;
        margin-bottom: clamp(20px, 3vw, 28px);
        color: var(--text-primary);
        letter-spacing: -0.3px;
    }

    .chart-sections {
        display: grid;
        grid-template-columns: 1fr;
        gap: clamp(16px, 3vw, 24px);
        margin-bottom: clamp(18px, 3vw, 26px);
    }

    .section {
        background: var(--section-bg);
        border: 1px solid var(--section-border);
        border-radius: 14px;
        padding: clamp(16px, 2.5vw, 20px);
        box-shadow: var(--section-shadow);
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }

    .section:hover {
        transform: translateY(-3px);
        box-shadow: var(--section-hover-shadow);
        border-color: rgba(79, 70, 229, 0.18);
    }

    .section h4 {
        margin: 0 0 14px;
        font-size: 1.05rem;
        font-weight: 700;
        background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .section-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        margin-bottom: 8px;
    }

    .prediction-distribution {
        border-left: 4px solid var(--accent-primary);
    }

    .time-series {
        border-left: 4px solid var(--accent-tertiary);
    }

    .chart-actions {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        justify-content: flex-end;
    }

    .reset-zoom {
        padding: 6px 14px;
        border-radius: 999px;
        border: 1px solid var(--accent-primary);
        background: transparent;
        color: var(--accent-primary);
        font-size: 0.85rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    .reset-zoom:hover {
        background: var(--accent-primary);
        color: #fff;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25);
    }

    .zoom-hint {
        font-size: 0.8rem;
        color: var(--text-secondary);
    }

    .chart-wrapper {
        position: relative;
        height: clamp(260px, 35vw, 320px);
    }

    .time-domain-chart {
        height: clamp(240px, 34vw, 320px);
    }

    .chart-legend {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 14px;
    }

    .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.92rem;
        color: var(--legend-color);
    }

    .legend-color {
        width: 18px;
        height: 10px;
        border-radius: 3px;
        flex-shrink: 0;
    }

    .legend-color.projection {
        background: #dc2626;
    }

    .legend-color.overshoot {
        background: #fb7185;
    }

    .chart-footnote {
        margin-top: 8px;
        font-size: 0.82rem;
        color: var(--text-secondary);
    }

    .overfit-banner {
        margin-top: 10px;
        padding: 12px 14px;
        border-radius: 12px;
        border: 1px solid rgba(14, 165, 233, 0.25);
        background: rgba(14, 165, 233, 0.08);
        color: var(--text-primary);
        font-size: 0.88rem;
    }

    .overfit-banner.risk {
        border-color: rgba(248, 113, 113, 0.45);
        background: rgba(248, 113, 113, 0.12);
    }

    .overfit-header {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        flex-wrap: wrap;
        margin-bottom: 6px;
        font-weight: 600;
    }

    .status-chip {
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        background: rgba(59, 130, 246, 0.15);
        color: var(--accent-primary);
    }

    .overfit-banner.risk .status-chip {
        background: rgba(248, 113, 113, 0.2);
        color: #dc2626;
    }

    .overfit-meta {
        font-size: 0.78rem;
        color: var(--text-secondary);
    }

    .simulation-summary {
        margin-top: 12px;
        padding: 14px 16px;
        border-radius: 12px;
        border: 1px solid var(--section-border);
        background: rgba(251, 113, 133, 0.08);
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .summary-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        font-size: 0.9rem;
        color: var(--text-primary);
        flex-wrap: wrap;
    }

    .model-chip {
        padding: 4px 10px;
        border-radius: 999px;
        background: rgba(251, 113, 133, 0.2);
        color: var(--accent-tertiary);
        font-size: 0.75rem;
        font-weight: 600;
    }

    .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 12px;
    }

    .summary-metric {
        display: flex;
        flex-direction: column;
        gap: 4px;
        padding: 10px 12px;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.35);
        border: 1px solid rgba(251, 113, 133, 0.22);
    }

    :global([data-theme='dark']) .summary-metric {
        background: rgba(15, 23, 42, 0.7);
    }

    .summary-metric span {
        font-size: 0.78rem;
        color: var(--text-secondary);
    }

    .summary-metric strong {
        font-size: 1.05rem;
        color: var(--text-primary);
    }

    .empty-state {
        padding: 20px;
        border: 1px dashed var(--section-border);
        border-radius: 12px;
        text-align: center;
        font-size: 0.9rem;
        color: var(--text-secondary);
        background: rgba(148, 163, 184, 0.08);
    }

    .table-info {
        margin-bottom: 14px;
    }

    .info-badge {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 10px 14px;
        background: var(--badge-bg);
        border-radius: 10px;
        font-size: 0.85rem;
        color: var(--badge-text);
        border: 1px solid var(--section-border);
    }

    .info-badge svg {
        width: 18px;
        height: 18px;
        stroke-width: 2.2;
    }

    .table-container {
        overflow-x: auto;
    }

    table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-size: 0.92rem;
        color: var(--text-primary);
    }

    thead {
        background: var(--table-header-bg);
        color: var(--table-header-text);
    }

    th {
        padding: 12px 10px;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.78rem;
        letter-spacing: 0.5px;
        border: none;
        text-align: center;
    }

    th small {
        display: block;
        font-size: 0.7rem;
        text-transform: none;
        opacity: 0.8;
    }

    th.sticky-col {
        position: sticky;
        left: 0;
        z-index: 5;
        background: var(--table-header-bg);
        box-shadow: 2px 0 4px rgba(15, 23, 42, 0.08);
    }

    td {
        padding: 12px 10px;
        text-align: center;
        border-bottom: 1px solid var(--table-border);
        transition: background 0.2s ease, color 0.2s ease;
    }

    td.sticky-col {
        position: sticky;
        left: 0;
        z-index: 4;
        background: var(--section-bg);
        box-shadow: 2px 0 4px rgba(15, 23, 42, 0.05);
        font-weight: 700;
        color: var(--text-primary);
    }

    td.highlight {
        font-weight: 700;
    }

    tbody tr {
        background: var(--section-bg);
        transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
    }

    tbody tr:nth-child(even) {
        background: var(--table-row-alt);
    }

    tbody tr:hover {
        transform: translateY(-1px);
        box-shadow: var(--section-hover-shadow);
    }

    tr.optimal {
        background: var(--optimal-bg) !important;
        border-left: 4px solid var(--accent-secondary);
    }

    tr.optimal td {
        color: var(--optimal-text);
        font-weight: 700;
    }

    tr.optimal td.sticky-col {
        background: var(--optimal-bg);
    }

    tr.optimal:hover {
        background: var(--optimal-bg-hover) !important;
    }

    tr.high-overage .overage-data {
        background: var(--risk-high-bg) !important;
        color: var(--risk-high-text) !important;
        font-weight: 600;
    }

    tr.high-waste .waste-data {
        background: var(--risk-medium-bg) !important;
        color: var(--risk-medium-text) !important;
        font-weight: 600;
    }

    td.total-cost {
        background: var(--table-total-bg);
        color: var(--table-total-text);
        font-weight: 700;
        font-size: 1.02rem;
    }

    .percentage,
    .cost-value {
        font-weight: 600;
    }

    .star {
        color: var(--star-color);
        font-size: 1.2rem;
        margin-left: 6px;
        display: inline-block;
        animation: pulse 2s ease-in-out infinite;
    }

    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.15); }
    }

    .remark {
        color: var(--text-secondary);
        font-size: 0.9rem;
    }

    .optimal-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border-radius: 999px;
        background: var(--table-total-bg);
        color: var(--table-total-text);
        border: 1px solid var(--optimal-border);
        font-weight: 700;
    }

    .optimal-badge svg {
        width: 16px;
        height: 16px;
        stroke-width: 2.4;
    }

    .risk-badge {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        line-height: 1;
    }

    .risk-badge.risk-high {
        background: var(--risk-high-bg);
        color: var(--risk-high-text);
    }

    .risk-badge.risk-medium {
        background: var(--risk-medium-bg);
        color: var(--risk-medium-text);
    }

    .normal {
        color: var(--text-secondary);
    }

    tbody tr {
        cursor: pointer;
    }

    tr.selected {
        box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.35);
        transform: translateY(-1px);
    }

    /* Scenario/conclusion UI styles removed as markup no longer renders those sections */

    @media (max-width: 1200px) {
        .chart-sections {
            grid-template-columns: 1fr;
        }
    }

    @media (max-width: 768px) {
        .optimization-chart {
            padding: 18px;
        }

        .section {
            padding: 16px;
        }

        .chart-wrapper {
            height: 240px;
        }
    }

    @media (max-width: 640px) {
        .table-container {
            overflow-x: visible;
        }

        table,
        thead,
        tbody,
        th,
        td,
        tr {
            display: block;
        }

        thead {
            display: none;
        }

        tbody tr {
            margin-bottom: 16px;
            border: 1px solid var(--section-border);
            border-radius: 12px;
            padding: 12px 14px;
            background: var(--section-bg);
            box-shadow: var(--section-shadow);
        }

        td {
            text-align: right;
            padding: 10px 0 10px 120px;
            border-bottom: 1px solid var(--table-border);
            position: relative;
        }

        td::before {
            content: attr(data-label);
            position: absolute;
            left: 0;
            top: 50%;
            transform: translateY(-50%);
            font-weight: 600;
            color: var(--text-secondary);
            text-align: left;
        }

        td:last-child {
            border-bottom: none;
        }

        td.sticky-col {
            position: static;
            padding-left: 0;
            text-align: left;
            font-size: 1rem;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        .section,
        tbody tr,
        .star {
            transition: none;
            animation: none;
        }
    }
</style>

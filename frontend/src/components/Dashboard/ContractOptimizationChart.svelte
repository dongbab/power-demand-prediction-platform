<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import type { Chart as ChartInstance, Point } from 'chart.js';
    import type {
        EnsemblePredictionResponse,
        ContractShortfallSimulation,
        ContractShortfallDailyPoint,
        ContractCandidateDetail
    } from '../../lib/types';

    export let optimizationData: any = null;
    export let predictionDistribution: number[] = [];
    export let ensemblePrediction: EnsemblePredictionResponse['ensemble_prediction'] | null = null;
    export let stationId: string;
    
    let chartContainer: HTMLDivElement;
    let chartCanvas: HTMLCanvasElement | null = null;
    let chartInstance: ChartInstance | null = null;
    let isDarkMode = false;
    let histogram: { x: number; y: number }[] = [];
    let lstmProjection: { x: number; y: number }[] = [];
    let q5 = 0;
    let q90 = 0;
    let q95 = 0;
    let historicalMax = 0;
    let projectedPeakKw = 0;
    let optimalCandidate: ContractCandidateDetail | null = null;
    let manualCandidate: ContractCandidateDetail | null = null;
    let allCandidates: ContractCandidateDetail[] = [];
    let ChartCtor: typeof import('chart.js/auto')['default'] | null = null;
    let chartReady = false;
    let timeSeriesCanvas: HTMLCanvasElement | null = null;
    let timeSeriesChartInstance: ChartInstance | null = null;
    let sessionSeries: SessionPoint[] = [];
    let sessionPredictionSeries: SessionPoint[] = [];
    let combinedSessionSeries: SessionPoint[] = [];
    let hasSessionTimeline = false;
    let sessionDomain: { min: number | null; max: number | null } = { min: null, max: null };
    let scenarioRows: ScenarioRow[] = [];
    let shortfallScenarios: ShortfallScenario[] = [];
    let shortfallDailyProjection: ShortfallDailyPoint[] = [];
    let activeShortfallScenario: ShortfallScenario | null = null;
    let overfitSignal: OverfitSignal = { isRisk: false, mae: null, relativeError: null, coverageDays: 0 };
    let selectedContractKw: number | null = null;
    let targetContractKw: number | null = null;
    let scenarioPredictedPeakAvg: number | null = null;
    let scenarioPredictedPeakP90: number | null = null;
    let scenarioOverageProbability: number | null = null;
    let scenarioP50: number | null = null;
    let isManualUndershoot = false;
    let isManualOvershoot = false;
    let defaultRecentRange: { min: number | null; max: number | null } = { min: null, max: null };
    const DEFAULT_SESSION_WINDOW_DAYS = 90;

    // 모델 검증 데이터 (9월까지 학습 → 10월 예측)
    let validationData: any = null;
    let validationLoading = false;
    let validationError: string | null = null;
    const BASIC_RATE_PER_KW = 8320;
    const SHORTAGE_PENALTY_RATIO = 1.5;
    const BASIC_RATE_LABEL = BASIC_RATE_PER_KW.toLocaleString('ko-KR');

    type SessionPoint = { date: string; power_kw: number };
    type OverfitSignal = {
        isRisk: boolean;
        mae: number | null;
        relativeError: number | null;
        coverageDays: number;
    };
    type ScenarioRow = {
        scenario: 'over' | 'optimal' | 'under';
        scenarioLabel: string;
        contractKw: number;
        baseMonthly: number;
        overCostMonthly: number;
        shortageMonthly: number;
        totalLossMonthly: number;
        evaluation: string;
    };
    type ShortfallDailyPoint = ContractShortfallDailyPoint;
    type ShortfallScenario = ContractShortfallSimulation;

    function toNumber(value: any): number | null {
        const num = Number(value);
        return Number.isFinite(num) ? num : null;
    }

    function normalizeCandidate(candidate: any): ContractCandidateDetail | null {
        const contractKw = toNumber(candidate?.contract_kw);
        if (contractKw === null) {
            return null;
        }

        const normalizeOptional = (val: any) => {
            const num = toNumber(val);
            return num === null ? undefined : num;
        };

        return {
            ...candidate,
            contract_kw: contractKw,
            expected_annual_cost: toNumber(candidate?.expected_annual_cost) ?? 0,
            overage_probability: toNumber(candidate?.overage_probability) ?? 0,
            waste_probability: toNumber(candidate?.waste_probability) ?? 0,
            cost_std: normalizeOptional(candidate?.cost_std),
            risk_score: normalizeOptional(candidate?.risk_score),
            session_overage_probability: normalizeOptional(candidate?.session_overage_probability),
            session_average_overshoot_kw: normalizeOptional(candidate?.session_average_overshoot_kw),
            session_max_overshoot_kw: normalizeOptional(candidate?.session_max_overshoot_kw),
            session_waste_probability: normalizeOptional(candidate?.session_waste_probability),
            session_average_waste_kw: normalizeOptional(candidate?.session_average_waste_kw),
            session_sample_size: normalizeOptional(candidate?.session_sample_size),
            session_expected_waste_cost: normalizeOptional(candidate?.session_expected_waste_cost)
        };
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

    function normalPdf(x: number, mean: number, stdDev: number) {
        const safeStd = Math.max(stdDev, 1e-3);
        const coeff = 1 / (safeStd * Math.sqrt(2 * Math.PI));
        const exponent = -0.5 * ((x - mean) / safeStd) ** 2;
        return coeff * Math.exp(exponent);
    }

    function generateHistogram(values: number[], targetBins = 26) {
        if (!Array.isArray(values) || values.length === 0) {
            return [];
        }
        const normalized = values
            .map((value) => Number(value))
            .filter((value) => Number.isFinite(value));
        if (normalized.length === 0) {
            return [];
        }
        const min = Math.min(...normalized);
        const max = Math.max(...normalized);
        const bins = Math.max(8, Math.min(targetBins, normalized.length));
        const range = max - min || 1;
        const width = range / bins;
        const counts = new Array(bins).fill(0);
        normalized.forEach((value) => {
            const index = Math.min(bins - 1, Math.floor((value - min) / width));
            counts[index] += 1;
        });
        return counts.map((count, index) => {
            const x = min + width * index + width / 2;
            return { x: Number(x.toFixed(2)), y: Number(count.toFixed(2)) };
        });
    }

    function detectDarkMode() {
        if (typeof document === 'undefined') {
            return false;
        }
        const html = document.documentElement;
        if (html.classList.contains('dark') || html.getAttribute('data-theme') === 'dark') {
            return true;
        }
        if (typeof window !== 'undefined' && window.matchMedia) {
            return window.matchMedia('(prefers-color-scheme: dark)').matches;
        }
        return false;
    }

    function formatManwon(value?: number | null) {
        if (value === null || value === undefined || Number.isNaN(value)) {
            return '-';
        }
        const manwon = value / 10000;
        const digits = Math.abs(manwon) >= 100 ? 0 : 1;
        return manwon.toLocaleString('ko-KR', {
            maximumFractionDigits: digits,
            minimumFractionDigits: digits
        });
    }

    function calcWasteCost(candidate: ContractCandidateDetail, referenceKw: number) {
        if (typeof candidate.session_expected_waste_cost === 'number') {
            return candidate.session_expected_waste_cost;
        }
        const wasteProb = (candidate.session_waste_probability ?? candidate.waste_probability ?? 0) / 100;
        if (wasteProb <= 0) {
            return 0;
        }
        const wasteKw = Math.max(0, candidate.contract_kw - referenceKw);
        if (wasteKw <= 0) {
            return 0;
        }
        return wasteKw * BASIC_RATE_PER_KW * wasteProb;
    }

    function calcShortageCost(candidate: ContractCandidateDetail, referenceKw: number) {
        const overshootKw = candidate.session_average_overshoot_kw
            ?? candidate.session_max_overshoot_kw
            ?? Math.max(0, referenceKw - candidate.contract_kw);
        if (!overshootKw) {
            return 0;
        }
        const probability = (candidate.session_overage_probability ?? candidate.overage_probability ?? 0) / 100;
        if (probability <= 0) {
            return 0;
        }
        return overshootKw * BASIC_RATE_PER_KW * SHORTAGE_PENALTY_RATIO * probability;
    }

    function describeScenarioImpact(scenario: ScenarioRow['scenario'], candidate: ContractCandidateDetail) {
        const overProb = candidate.session_overage_probability ?? candidate.overage_probability ?? 0;
        const wasteProb = candidate.session_waste_probability ?? candidate.waste_probability ?? 0;
        if (scenario === 'optimal') {
            return '추천';
        }
        if (scenario === 'under') {
            if (overProb >= 60) return '위험';
            if (overProb >= 30) return '주의';
            return '조건부';
        }
        if (wasteProb >= 60) return '비효율';
        if (wasteProb >= 30) return '여유';
        return '안정';
    }

    function buildScenarioRows(candidates: ContractCandidateDetail[], optimalKw: number | null): ScenarioRow[] {
        if (!Array.isArray(candidates) || candidates.length === 0) {
            return [];
        }
        const referenceKw = optimalKw ?? candidates[0].contract_kw;
        const rows = candidates.map((candidate) => {
            const scenario: ScenarioRow['scenario'] = candidate.contract_kw === referenceKw
                ? 'optimal'
                : candidate.contract_kw > referenceKw
                    ? 'over'
                    : 'under';
            const scenarioLabel = scenario === 'optimal' ? '최적안' : scenario === 'over' ? '과다' : '과소';
            const baseMonthly = candidate.contract_kw * BASIC_RATE_PER_KW;
            const overCostMonthly = scenario === 'over' ? calcWasteCost(candidate, referenceKw) : 0;
            const shortageMonthly = scenario === 'under' ? calcShortageCost(candidate, referenceKw) : 0;
            const totalLossMonthly = overCostMonthly + shortageMonthly;
            return {
                scenario,
                scenarioLabel,
                contractKw: candidate.contract_kw,
                baseMonthly,
                overCostMonthly,
                shortageMonthly,
                totalLossMonthly,
                evaluation: describeScenarioImpact(scenario, candidate)
            } satisfies ScenarioRow;
        });
        const orderWeight: Record<ScenarioRow['scenario'], number> = { optimal: 0, under: 1, over: 2 };
        return rows.sort((a, b) => orderWeight[a.scenario] - orderWeight[b.scenario] || a.contractKw - b.contractKw);
    }

    async function fetchValidationData() {
        if (!stationId) return;

        validationLoading = true;
        validationError = null;

        try {
            console.log('[ContractOptimizationChart] Fetching validation data for:', stationId);
            const response = await fetch(`/api/stations/${stationId}/model-validation`);
            const data = await response.json();

            if (data.success) {
                console.log('[ContractOptimizationChart] Validation data received:', data);
                validationData = data;
            } else {
                console.warn('[ContractOptimizationChart] Validation failed:', data.error);
                validationError = data.error || '검증 데이터를 불러올 수 없습니다.';
            }
        } catch (error) {
            console.error('[ContractOptimizationChart] Validation data fetch error:', error);
            validationError = '네트워크 오류가 발생했습니다.';
        } finally {
            validationLoading = false;
        }
    }

    async function ensureChartModules() {
        if (typeof window === 'undefined') {
            return;
        }
        if (ChartCtor) {
            chartReady = true;
            return;
        }
        try {
            const [{ default: ChartJS }, annotationPlugin, zoomPlugin] = await Promise.all([
                import('chart.js/auto'),
                import('chartjs-plugin-annotation'),
                import('chartjs-plugin-zoom')
            ]);
            await import('chartjs-adapter-date-fns');
            ChartJS.register(annotationPlugin.default || annotationPlugin);
            ChartJS.register(zoomPlugin.default || zoomPlugin);
            ChartCtor = ChartJS;
            chartReady = true;
        } catch (error) {
            chartReady = false;
            console.error('ContractOptimizationChart: Chart.js 모듈 로드 실패', error);
        }
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
        const optimalKw = optimalCandidate?.contract_kw ?? 0;
        const manualKw = selectedContractKw ?? optimalKw;
        const projectedMax = projectedPeakKw || q95Val;
        const showUnderProjection = manualKw !== null && isManualUndershoot && projectedMax > manualKw;
        
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

        if (manualKw !== null && manualKw !== undefined) {
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

        // 과다 시나리오 시각화
        const showOverProjection = manualKw !== null && isManualOvershoot && manualKw > q95Val;
        if (showOverProjection) {
            annotations.overProjection = {
                type: 'box',
                xMin: Math.round(q95Val),
                xMax: manualKw,
                backgroundColor: 'rgba(34, 197, 94, 0.08)',
                borderColor: 'rgba(34, 197, 94, 0.5)',
                borderWidth: 1,
                label: {
                    display: true,
                    position: 'end',
                    backgroundColor: 'rgba(34, 197, 94, 0.85)',
                    color: '#fff',
                    content: `여유 영역 (과다 계약)`,
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
        const currentContractKw = optimizationData?.current_contract_kw ?? null;
        
        // validation 데이터가 있으면 검증 차트에 계약선까지 포함해 렌더링
        if (validationData && validationData.visualization_data) {
            createValidationChart(manualKw, currentContractKw);
            return;
        }

        if (!hasSessionTimeline) {
            return;
        }

        const observedMax = Math.max(
            ...[
                ...sessionSeries.map((point) => point.power_kw),
                ...sessionPredictionSeries.map((point) => point.power_kw),
                ...shortfallDailyProjection.map((point) => point.simulated_peak_kw)
            ].filter((value) => Number.isFinite(value))
        );
        const referenceMax = Math.max(
            Number.isFinite(observedMax) ? observedMax : 0,
            manualKw ?? 0,
            currentContractKw ?? 0
        );
        const ySuggestedMax = referenceMax > 0 ? referenceMax * 1.08 : undefined;
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

        // 과다 계약 시 여유 영역 표시
        const wasteAreaDataset = hasSimulation && isManualOvershoot
            ? shortfallDailyProjection.map(point => ({
                x: new Date(point.date).getTime(),
                y: manualKw
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

        if (currentContractKw !== null) {
            annotations.currentContractLine = {
                type: 'line',
                yMin: currentContractKw,
                yMax: currentContractKw,
                borderColor: '#22c55e',
                borderWidth: 1.5,
                borderDash: [4, 4],
                label: {
                    content: `현재 계약선: ${currentContractKw}kW`,
                    display: true,
                    position: 'start',
                    backgroundColor: '#22c55e',
                    color: '#0f172a',
                    font: { size: 10, weight: 'bold' }
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
                        baseDatasets.push({
                            label: '개별 세션 피크',
                            data: chronologicalSessions,
                            borderColor: 'rgba(14, 165, 233, 0.6)',
                            backgroundColor: 'rgba(14, 165, 233, 0.6)',
                            borderWidth: 0,
                            pointRadius: 3,
                            pointHoverRadius: 4,
                            showLine: false,
                            order: 4,
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
                        baseDatasets.push({
                            label: '예측 세션 피크',
                            data: predictedSessions,
                            borderColor: 'rgba(139, 92, 246, 0.45)',
                            backgroundColor: (context: any) => {
                                const y = context.raw?.y;
                                if (manualKw !== null && Number.isFinite(y) && y > manualKw) {
                                    return 'rgba(248, 113, 113, 0.9)'; // overshoot
                                }
                                return 'rgba(59, 130, 246, 0.9)'; // within contract
                            },
                            pointRadius: 3,
                            pointHoverRadius: 4,
                            showLine: false,
                            borderWidth: 0,
                            order: manualKw !== null ? 3 : 2,
                            parsing: false,
                            spanGaps: false
                        });
                    }

                    if (hasSimulation) {
                        if (isManualOvershoot && wasteAreaDataset.length > 0) {
                            // 과다 계약 시 여유 영역 표시
                            baseDatasets.push({
                                label: '여유 영역 (과다 계약)',
                                data: wasteAreaDataset,
                                borderColor: 'rgba(34, 197, 94, 0)',
                                backgroundColor: 'rgba(34, 197, 94, 0.12)',
                                pointRadius: 0,
                                pointHoverRadius: 0,
                                tension: 0.2,
                                borderWidth: 0,
                                fill: { target: 'origin' },
                                order: -1,
                                spanGaps: false,
                                parsing: false
                            });
                        } else {
                            // 과소 계약 시 위험 영역 표시
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
                        }
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
                        suggestedMax: ySuggestedMax,
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

    function createValidationChart(manualKw: number | null, currentContractKw: number | null) {
        if (!timeSeriesCanvas || !ChartCtor || !validationData) {
            console.log('[ContractOptimizationChart] Skipping createValidationChart - missing:', {
                canvas: !!timeSeriesCanvas,
                chart: !!ChartCtor,
                data: !!validationData
            });
            return;
        }

        console.log('[ContractOptimizationChart] Creating validation chart with data:', validationData.data_split);

        const textColor = isDarkMode ? '#e2e8f0' : '#1f2937';
        const gridColor = isDarkMode ? 'rgba(148, 163, 184, 0.2)' : 'rgba(0, 0, 0, 0.08)';

        // 학습 기간 실제 데이터 (train_visualization_data 사용)
        const trainData = (validationData.train_visualization_data || []).map((item: any) => ({
            x: new Date(item.date).getTime(),
            y: item.actual_peak_kw
        }));

        // 테스트 기간 실제 데이터
        const testActualData = validationData.visualization_data.map((item: any) => ({
            x: new Date(item.date).getTime(),
            y: item.actual_peak_kw
        }));

        // 테스트 기간 예측 데이터
        const testPredictedData = validationData.visualization_data.map((item: any) => ({
            x: new Date(item.date).getTime(),
            y: item.predicted_peak_kw
        }));

        // 학습/테스트 구간 날짜
        const trainEndDate = validationData.data_split?.train_end_date || '2024-09-30';
        const testStartDate = validationData.data_split?.test_start_date || '2024-10-01';

        const datasets: any[] = [
            {
                label: `실제 피크 (${trainEndDate}까지 학습 데이터)`,
                data: trainData,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                borderWidth: 2,
                pointRadius: 2,
                pointHoverRadius: 4,
                tension: 0.2,
                fill: false,
                order: 3
            },
            {
                label: `실제 피크 (${testStartDate}부터 테스트)`,
                data: testActualData,
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                borderWidth: 2.5,
                pointRadius: 3,
                pointHoverRadius: 5,
                tension: 0.2,
                fill: false,
                order: 1,
                borderDash: []
            },
            {
                label: `예측 피크 (${testStartDate}부터)`,
                data: testPredictedData,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.15)',
                borderWidth: 2,
                pointRadius: 2,
                pointHoverRadius: 4,
                tension: 0.3,
                fill: false,
                order: 2,
                borderDash: [5, 5]
            }
        ];

        const splitLineDate = new Date(testStartDate).getTime();
        const annotations: Record<string, any> = {
            trainTestSplit: {
                type: 'line',
                xMin: splitLineDate,
                xMax: splitLineDate,
                borderColor: '#f59e0b',
                borderWidth: 2,
                borderDash: [10, 5],
                label: {
                    content: `${trainEndDate}까지 학습 → ${testStartDate}부터 예측`,
                    display: true,
                    position: 'start',
                    backgroundColor: '#f59e0b',
                    color: 'white',
                    font: { size: 11, weight: 'bold' }
                }
            }
        };

        if (manualKw !== null && manualKw !== undefined) {
            annotations.contractLine = {
                type: 'line',
                yMin: manualKw,
                yMax: manualKw,
                borderColor: '#f97316',
                borderWidth: 2,
                borderDash: [6, 4],
                label: {
                    content: `선택 계약선: ${manualKw}kW`,
                    display: true,
                    position: 'start',
                    backgroundColor: '#f97316',
                    color: '#fff',
                    font: { size: 10, weight: 'bold' }
                }
            };
        }

        if (currentContractKw !== null && currentContractKw !== undefined) {
            annotations.currentContractLine = {
                type: 'line',
                yMin: currentContractKw,
                yMax: currentContractKw,
                borderColor: '#22c55e',
                borderWidth: 1.5,
                borderDash: [4, 4],
                label: {
                    content: `현재 계약선: ${currentContractKw}kW`,
                    display: true,
                    position: 'end',
                    backgroundColor: '#22c55e',
                    color: '#0f172a',
                    font: { size: 10, weight: 'bold' }
                }
            };
        }

        const yValues = [
            ...trainData.map((p: any) => p.y),
            ...testActualData.map((p: any) => p.y),
            ...testPredictedData.map((p: any) => p.y),
            manualKw ?? null,
            currentContractKw ?? null
        ].filter((v) => Number.isFinite(v)) as number[];
        const ySuggestedMax = yValues.length ? Math.max(...yValues) * 1.08 : undefined;

        timeSeriesChartInstance = new ChartCtor(timeSeriesCanvas, {
            type: 'line',
            data: { datasets },
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
                        time: {
                            tooltipFormat: 'yyyy-MM-dd',
                            unit: 'day',
                            displayFormats: {
                                day: 'MM-dd',
                                month: 'yyyy-MM'
                            }
                        },
                        ticks: {
                            color: textColor
                        },
                        grid: {
                            color: gridColor
                        },
                        title: {
                            display: true,
                            text: '날짜 (9월 학습 → 10월 예측)',
                            color: textColor,
                            font: { size: 13, weight: 'bold' }
                        }
                    },
                    y: {
                        suggestedMax: ySuggestedMax,
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
                        display: true,
                        position: 'top',
                        labels: {
                            color: textColor,
                            usePointStyle: true,
                            padding: 15,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            title: items => items[0]?.parsed?.x ? new Date(items[0].parsed.x).toLocaleDateString('ko-KR') : '',
                            label: context => {
                                const value = context.parsed?.y;
                                if (value === null || value === undefined) return '';
                                const label = context.dataset?.label ?? '';
                                return `${label}: ${value.toFixed(1)} kW`;
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

    function showRecentTimeline() {
        if (!hasSessionTimeline) {
            return;
        }
        applyTimelineRange(defaultRecentRange);
    }

    function showFullTimeline() {
        if (!hasSessionTimeline) {
            return;
        }
        applyTimelineRange(sessionDomain);
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
        const handleChange = (e: MediaQueryListEvent | MediaQueryList) => {
            const matches = 'matches' in e ? e.matches : mediaQuery.matches;
            isDarkMode = matches;
            createChart();
            createTimeSeriesChart();
        };
        if (typeof mediaQuery.addEventListener === 'function') {
            mediaQuery.addEventListener('change', handleChange as EventListener);
        } else if (typeof mediaQuery.addListener === 'function') {
            mediaQuery.addListener(handleChange as any);
        }
        
        return () => {
            observer.disconnect();
            if (typeof mediaQuery.removeEventListener === 'function') {
                mediaQuery.removeEventListener('change', handleChange as EventListener);
            } else if (typeof mediaQuery.removeListener === 'function') {
                mediaQuery.removeListener(handleChange as any);
            }
        };
    }
    
    onMount(() => {
        isDarkMode = detectDarkMode();
        // validation 데이터 먼저 가져오기
        fetchValidationData();
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
        isManualOvershoot;
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
        validationData;
        createTimeSeriesChart();
    }
    
    $: histogram = generateHistogram(predictionDistribution);
    $: q5 = percentile(predictionDistribution, 5);
    $: q95 = percentile(predictionDistribution, 95);
    $: q90 = percentile(predictionDistribution, 90);
    $: historicalMax = safeMax(predictionDistribution);
    $: projectedPeakKw = Math.max(percentile(predictionDistribution, 99), historicalMax || 0);
    $: optimalCandidate = optimizationData?.optimal_candidate ? normalizeCandidate(optimizationData.optimal_candidate) : null;
    $: allCandidates = Array.isArray(optimizationData?.all_candidates)
        ? optimizationData.all_candidates
            .map(normalizeCandidate)
            .filter((candidate): candidate is ContractCandidateDetail => candidate !== null)
        : [];
    $: scenarioRows = buildScenarioRows(allCandidates, optimalCandidate?.contract_kw ?? null);
    $: if (allCandidates.length > 0) {
        const defaultKw = optimalCandidate?.contract_kw ?? allCandidates[0].contract_kw;
        const hasSelection = selectedContractKw !== null && allCandidates.some(candidate => candidate.contract_kw === selectedContractKw);
        if (!hasSelection) {
            selectedContractKw = defaultKw;
        }
    } else {
        selectedContractKw = null;
    }
    $: manualCandidate = selectedContractKw !== null
        ? allCandidates.find(candidate => candidate.contract_kw === selectedContractKw) || null
        : null;
    $: isManualUndershoot = (() => {
        const kw = selectedContractKw;
        const overProb = manualCandidate
            ? (manualCandidate.session_overage_probability ?? manualCandidate.overage_probability ?? 0)
            : 0;
        if (overProb > 30) return true;
        if (kw === null) return false;
        return kw < q90;
    })();
    $: isManualOvershoot = (() => {
        const kw = selectedContractKw;
        const wasteProb = manualCandidate
            ? (manualCandidate.session_waste_probability ?? manualCandidate.waste_probability ?? 0)
            : 0;
        if (wasteProb > 30) return true;
        if (kw === null) return false;
        return kw > q95;
    })();
    $: shortfallScenarios = Array.isArray(optimizationData?.contract_shortfall_simulations)
        ? optimizationData.contract_shortfall_simulations
        : [];
    $: targetContractKw = selectedContractKw ?? optimalCandidate?.contract_kw ?? null;
    $: activeShortfallScenario = findShortfallScenario(
        shortfallScenarios,
        targetContractKw
    );
    $: scenarioPredictedPeakAvg = targetContractKw !== null && activeShortfallScenario
        ? Number((targetContractKw + (activeShortfallScenario.expected_overshoot_kw ?? 0)).toFixed(2))
        : null;
    $: scenarioPredictedPeakP90 = targetContractKw !== null && activeShortfallScenario
        ? Number((targetContractKw + (activeShortfallScenario.p90_overshoot_kw ?? 0)).toFixed(2))
        : null;
    $: scenarioP50 = predictionDistribution.length
        ? Number(percentile(predictionDistribution, 50).toFixed(2))
        : null;
    $: scenarioOverageProbability = targetContractKw !== null && predictionDistribution.length
        ? Number(
            (
                (predictionDistribution.filter(value => Number.isFinite(value) && value > targetContractKw).length /
                    predictionDistribution.length) *
                100
            ).toFixed(2)
        )
        : null;
    $: shortfallDailyProjection = normalizeShortfallProjection(activeShortfallScenario?.daily_projection);
    $: overfitSignal = computeOverfitSignal(sessionSeries, shortfallDailyProjection);

    $: if (manualCandidate && isManualUndershoot) {
        lstmProjection = buildLstmUndershootProjection(manualCandidate.contract_kw);
    } else {
        lstmProjection = [];
    }

    function handleCandidateSelect(contractKw: number | string) {
        const nextKw = toNumber(contractKw);
        if (nextKw === null || selectedContractKw === nextKw) {
            return;
        }
        selectedContractKw = nextKw;
    }
</script>

<div class="optimization-chart" bind:this={chartContainer}>
    <div class="chart-sections">
        <div class="section time-series">
            <div class="section-header">
                <h4>세션 기반 순간전력 추이</h4>
                {#if hasSessionTimeline}
                    <div class="chart-actions">
                        <button
                            type="button"
                            class="reset-zoom"
                            on:click={showRecentTimeline}>최근 3개월</button
                        >
                        <button
                            type="button"
                            class="reset-zoom"
                            on:click={showFullTimeline}>전체 기간</button
                        >
                        <span class="zoom-hint">스크롤 · 터치로 확대/축소</span>
                    </div>
                {/if}
            </div>

            {#if validationLoading}
                <div class="chart-wrapper time-domain-chart">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>검증 데이터를 불러오는 중...</p>
                    </div>
                </div>
            {:else if hasSessionTimeline || validationData}
                <div class="chart-wrapper time-domain-chart">
                    <canvas bind:this={timeSeriesCanvas}></canvas>
                </div>

                {#if validationData && validationData.visualization_data}
                    <!-- 모델 검증 방식 설명 -->
                    <div class="validation-info-banner">
                        <div class="info-header">
                            <span class="info-icon">📊</span>
                            <h5>모델 검증: {validationData.data_split.train_end_date}까지 학습 → {validationData.data_split.test_start_date}부터 예측</h5>
                        </div>
                        <p class="info-description">
                            <strong class="highlight-green">녹색 실선</strong>: {validationData.data_split.train_end_date}까지의 <strong>실제 충전 피크</strong> (학습 데이터) <br/>
                            <strong class="highlight-red">빨간색 실선</strong>: {validationData.data_split.test_start_date}~{validationData.data_split.test_end_date}의 <strong>실제 충전 피크</strong> (테스트 데이터 - 실제 발생한 값) <br/>
                            <strong class="highlight-blue">파란색 점선</strong>: {validationData.data_split.train_end_date}까지 학습한 모델이 <strong>테스트 기간을 예측한 결과</strong>
                        </p>
                        <div class="validation-metrics">
                            <div class="metric-card">
                                <span class="metric-label">MAE (평균 절대 오차)</span>
                                <span class="metric-value">{validationData.validation_metrics.mae} kW</span>
                            </div>
                            <div class="metric-card">
                                <span class="metric-label">상대 오차</span>
                                <span class="metric-value">{validationData.validation_metrics.relative_error_percent.toFixed(1)}%</span>
                            </div>
                            <div class="metric-card">
                                <span class="metric-label">상관계수</span>
                                <span class="metric-value">{validationData.validation_metrics.correlation.toFixed(3)}</span>
                            </div>
                            <div class="metric-card">
                                <span class="metric-label">일관성</span>
                                <span class="metric-value consistency-{validationData.validation_metrics.consistency}">
                                    {validationData.validation_metrics.consistency}
                                </span>
                            </div>
                        </div>
                        <p class="info-note">
                            💡 <strong>용어 설명:</strong>
                            <strong>"실제 피크"</strong>는 충전소에서 실제로 측정된 일별 최대 전력이고,
                            <strong>"예측 피크"</strong>는 9월까지의 데이터로 학습한 AI 모델이 10월에 발생할 것으로 예상한 일별 최대 전력입니다.
                            빨간색과 파란색이 가까울수록 모델의 예측 정확도가 높습니다.
                        </p>
                    </div>
                {:else}
                    <p class="chart-footnote">
                        모든 충전 세션(실측 + 모델 예측)의 순간최대 전력을 시계열로
                        표현했습니다. 기본 뷰는 최근 3개월이며 확대/축소로 전체
                        기간을 탐색할 수 있습니다. 선택한 계약전력 시나리오가 있으면
                        예측 궤적이 계약선을 넘을 때 보라색 초과 영역으로 강조되어,
                        제한이 없을 경우 얼마나 초과할 수 있는지 직관적으로 확인할
                        수 있습니다.
                        {#if shortfallDailyProjection.length > 0}
                            {#if isManualOvershoot}
                                딥러닝 기반 예측 곡선(분홍색)과 여유 영역(녹색 음영)으로
                                과다 계약으로 인한 낭비 가능성을 시각화했습니다.
                            {:else}
                                딥러닝 기반 예측 곡선(분홍색)과 과소 위험 영역(붉은
                                음영)으로 계약선 초과 가능성을 강조했습니다.
                            {/if}
                        {/if}
                    </p>
                {/if}
                {#if overfitSignal.coverageDays >= 3}
                    <div
                        class="overfit-banner"
                        class:risk={overfitSignal.isRisk}
                    >
                        <div class="overfit-header">
                            <span class="status-chip"
                                >{overfitSignal.isRisk
                                    ? "과적합 의심"
                                    : "일관성 양호"}</span
                            >
                            <span class="overfit-meta">
                                MAE {overfitSignal.mae !== null
                                    ? `${overfitSignal.mae.toFixed(1)}kW`
                                    : "측정 불가"} · 비교 {overfitSignal.coverageDays}일
                                {#if overfitSignal.relativeError !== null}
                                    · 상대 오차 {(
                                        overfitSignal.relativeError * 100
                                    ).toFixed(1)}%
                                {/if}
                            </span>
                        </div>
                        <p>
                            {#if overfitSignal.isRisk}
                                최근 실측 패턴과 예측 추세가 다르게 움직여
                                과적합 가능성이 있습니다. 최신 데이터를
                                반영하거나 하이퍼파라미터를 조정해 주세요.
                            {:else}
                                예측 곡선이 실측 추세와 충분히 일치하여
                                안정적으로 일반화되고 있습니다.
                            {/if}
                        </p>
                    </div>
                {/if}
                {#if activeShortfallScenario && selectedContractKw !== null && shortfallDailyProjection.length > 0}
                    <div class="simulation-summary" class:overshoot={isManualOvershoot}>
                        <div class="summary-header">
                            <span
                                >{selectedContractKw}kW 기준 딥러닝 {isManualOvershoot ? '과다' : '과소'}
                                시뮬레이션</span
                            >
                            <span class="model-chip"
                                >{getModelLabel(
                                    activeShortfallScenario.model_source
                                )}</span
                            >
                        </div>
                        <div class="summary-grid">
                            {#if scenarioOverageProbability !== null}
                                <div class="summary-metric">
                                    <span>예측 분포 초과확률</span>
                                    <strong>{scenarioOverageProbability.toFixed(1)}%</strong>
                                </div>
                            {/if}
                            {#if scenarioP50 !== null}
                                <div class="summary-metric">
                                    <span>예측 피크 P50</span>
                                    <strong>{scenarioP50}kW</strong>
                                </div>
                            {/if}
                            {#if scenarioPredictedPeakAvg !== null}
                                <div class="summary-metric">
                                    <span>계약선 기준 예측 피크(평균)</span>
                                    <strong>{scenarioPredictedPeakAvg}kW</strong>
                                </div>
                            {/if}
                            {#if scenarioPredictedPeakP90 !== null}
                                <div class="summary-metric">
                                    <span>계약선 기준 예측 피크(P90)</span>
                                    <strong>{scenarioPredictedPeakP90}kW</strong>
                                </div>
                            {/if}
                            {#if isManualOvershoot}
                                <div class="summary-metric">
                                    <span>여유 확률 (낭비 가능성)</span>
                                    <strong
                                        >{(100 - activeShortfallScenario.overshoot_probability).toFixed(
                                            1
                                        )}%</strong
                                    >
                                </div>
                                <div class="summary-metric">
                                    <span>평균 여유 전력</span>
                                    <strong
                                        >{(selectedContractKw - (activeShortfallScenario.expected_overshoot_kw || q95)).toFixed(
                                            1
                                        )}kW</strong
                                    >
                                </div>
                                <div class="summary-metric">
                                    <span>예상 월 낭비 비용</span>
                                    <strong
                                        >{formatManwon(manualCandidate?.session_expected_waste_cost ?? 0)} 만원</strong
                                    >
                                </div>
                            {:else}
                                <div class="summary-metric">
                                    <span>과소 확률</span>
                                    <strong
                                        >{activeShortfallScenario.overshoot_probability.toFixed(
                                            1
                                        )}%</strong
                                    >
                                </div>
                                <div class="summary-metric">
                                    <span>예상 초과 폭 (평균)</span>
                                    <strong
                                        >{activeShortfallScenario.expected_overshoot_kw.toFixed(
                                            1
                                        )}kW</strong
                                    >
                                </div>
                                <div class="summary-metric">
                                    <span>P90 초과 폭</span>
                                    <strong
                                        >{activeShortfallScenario.p90_overshoot_kw.toFixed(
                                            1
                                        )}kW</strong
                                    >
                                </div>
                            {/if}
                        </div>
                    </div>
                {/if}
            {:else}
                <div class="empty-state">
                    세션 기반 피크 데이터가 부족하여 시계열 그래프를 표시할 수
                    없습니다.
                </div>
            {/if}
        </div>
    </div>

    <!-- Section 3: 비용 산정 테이블 -->
    <div class="section cost-table">
        <h4>확률 및 비용 산정 모듈</h4>
        <div class="table-info">
            <div class="info-badge">
                <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                >
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 10v5" />
                    <path d="M12 7h.01" />
                </svg>
                <span
                    >각 행을 클릭하면 선택한 계약전력 기준으로 그래프 상 선형
                    안내선이 갱신됩니다.</span
                >
            </div>
        </div>
        <div class="scenario-table-container">
            <table class="scenario-table">
                <thead>
                    <tr>
                        <th>시나리오</th>
                        <th>계약전력</th>
                        <th
                            >월 기본요금<br /><small
                                >(kW당 {BASIC_RATE_LABEL}원)</small
                            ></th
                        >
                        <th>과다계약 비용</th>
                        <th>과소계약 손실</th>
                        <th>총 손실</th>
                        <th>경제적 평가</th>
                    </tr>
                </thead>
                <tbody>
                    {#if scenarioRows.length === 0}
                        <tr>
                            <td colspan="7" class="empty-row"
                                >최적화 후보 데이터를 불러올 수 없습니다.</td
                            >
                        </tr>
                    {:else}
                        {#each scenarioRows as row}
                            <tr
                                class:optimal={row.scenario === "optimal"}
                                class:over={row.scenario === "over"}
                                class:under={row.scenario === "under"}
                                class:selected={row.contractKw ===
                                    selectedContractKw}
                                on:click={() =>
                                    handleCandidateSelect(row.contractKw)}
                            >
                                <td class="scenario-cell">
                                    <span class="scenario-tag"
                                        >{row.scenarioLabel}</span
                                    >
                                </td>
                                <td>{row.contractKw}kW</td>
                                <td>{formatManwon(row.baseMonthly)} 만원</td>
                                <td
                                    >{row.scenario === "over"
                                        ? `${formatManwon(row.overCostMonthly)} 만원`
                                        : "-"}</td
                                >
                                <td
                                    >{row.scenario === "under"
                                        ? `${formatManwon(row.shortageMonthly)} 만원`
                                        : "-"}</td
                                >
                                <td
                                    >{formatManwon(row.totalLossMonthly)} 만원</td
                                >
                                <td class="evaluation">{row.evaluation}</td>
                            </tr>
                        {/each}
                    {/if}
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
        --table-header-bg: linear-gradient(
            135deg,
            rgba(148, 163, 184, 0.28) 0%,
            rgba(129, 140, 248, 0.24) 100%
        );
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
        transition:
            transform 0.2s ease,
            box-shadow 0.2s ease,
            border-color 0.2s ease;
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
        background: linear-gradient(
            135deg,
            var(--accent-primary),
            var(--accent-secondary)
        );
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

    .simulation-summary.overshoot {
        background: rgba(34, 197, 94, 0.08);
        border-color: rgba(34, 197, 94, 0.3);
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

    .simulation-summary.overshoot .model-chip {
        background: rgba(34, 197, 94, 0.25);
        color: #16a34a;
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

    :global([data-theme="dark"]) .summary-metric {
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

    .scenario-table-container {
        margin-top: 18px;
        border: 1px solid var(--section-border);
        border-radius: 16px;
        overflow-x: auto;
        background: var(--section-bg);
        box-shadow: var(--section-shadow);
    }

    .scenario-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.95rem;
        min-width: 640px;
    }

    .scenario-table thead th {
        background: var(--table-header-bg);
        color: var(--table-header-text);
        text-transform: uppercase;
        font-size: 0.78rem;
        letter-spacing: 0.45px;
        padding: 14px 12px;
        text-align: center;
    }

    .scenario-table thead th small {
        display: block;
        font-size: 0.68rem;
        text-transform: none;
        opacity: 0.8;
        margin-top: 4px;
    }

    .scenario-table td {
        padding: 14px 12px;
        text-align: center;
        border-top: 1px solid var(--table-border);
    }

    .scenario-table tbody tr {
        background: var(--section-bg);
        transition:
            background 0.2s ease,
            color 0.2s ease,
            transform 0.2s ease,
            box-shadow 0.2s ease;
        cursor: pointer;
    }

    .scenario-table tbody tr + tr {
        border-top: 1px solid rgba(148, 163, 184, 0.2);
    }

    .scenario-table tbody tr:hover {
        transform: translateY(-1px);
        box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
    }

    .scenario-table tbody tr.optimal {
        background: var(--optimal-bg);
        color: var(--optimal-text);
        font-weight: 700;
    }

    .scenario-table tbody tr.over {
        background: rgba(14, 165, 233, 0.08);
    }

    .scenario-table tbody tr.under {
        background: rgba(249, 115, 22, 0.08);
    }

    :global([data-theme="dark"]) .scenario-table tbody tr.over {
        background: rgba(14, 165, 233, 0.2);
    }

    :global([data-theme="dark"]) .scenario-table tbody tr.under {
        background: rgba(249, 115, 22, 0.2);
    }

    .scenario-table tbody tr.selected {
        outline: 2px solid var(--accent-primary);
        outline-offset: -2px;
        box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.25);
    }

    .scenario-cell {
        text-align: left;
    }

    .scenario-tag {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        background: rgba(79, 70, 229, 0.12);
        color: var(--accent-primary);
    }

    .scenario-table tbody tr.over .scenario-tag {
        background: rgba(14, 165, 233, 0.15);
        color: #0284c7;
    }

    .scenario-table tbody tr.under .scenario-tag {
        background: rgba(249, 115, 22, 0.18);
        color: #c2410c;
    }

    .scenario-table tbody tr.optimal .scenario-tag {
        background: var(--table-total-bg);
        color: var(--table-total-text);
    }

    .scenario-table td.evaluation {
        font-weight: 700;
        color: var(--text-primary);
    }

    .scenario-table .empty-row {
        text-align: center;
        padding: 36px 12px;
        color: var(--text-secondary);
    }

    @media (max-width: 640px) {
        .scenario-table {
            min-width: 100%;
            font-size: 0.9rem;
        }

        .scenario-table td,
        .scenario-table th {
            padding: 10px 8px;
        }
    }

    /* Scenario/conclusion UI styles removed as markup no longer renders those sections */

    /* Validation Info Banner */
    .validation-info-banner {
        margin-top: 16px;
        padding: 20px;
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.05), rgba(16, 185, 129, 0.05));
        border: 2px solid rgba(59, 130, 246, 0.2);
        border-radius: 14px;
    }

    .info-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
    }

    .info-icon {
        font-size: 1.5rem;
    }

    .info-header h5 {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--text-primary);
    }

    .info-description {
        margin: 12px 0;
        font-size: 0.95rem;
        line-height: 1.8;
        color: var(--text-primary);
    }

    .highlight-green {
        color: #10b981;
        font-weight: 600;
    }

    .highlight-red {
        color: #ef4444;
        font-weight: 600;
    }

    .highlight-blue {
        color: #3b82f6;
        font-weight: 600;
    }

    .validation-metrics {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 12px;
        margin: 16px 0;
    }

    .metric-card {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 12px;
        background: rgba(255, 255, 255, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 10px;
    }

    :global([data-theme="dark"]) .metric-card {
        background: rgba(15, 23, 42, 0.6);
        border-color: rgba(148, 163, 184, 0.3);
    }

    .metric-label {
        font-size: 0.8rem;
        color: var(--text-secondary);
        font-weight: 500;
    }

    .metric-value {
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--text-primary);
    }

    .metric-value.consistency-양호 {
        color: #10b981;
    }

    .metric-value.consistency-보통 {
        color: #f59e0b;
    }

    .metric-value.consistency-개선\ 필요 {
        color: #ef4444;
    }

    .info-note {
        margin: 12px 0 0 0;
        padding: 12px;
        background: rgba(59, 130, 246, 0.1);
        border-left: 3px solid #3b82f6;
        border-radius: 6px;
        font-size: 0.9rem;
        line-height: 1.6;
        color: var(--text-primary);
    }

    /* Loading State */
    .loading-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 60px 20px;
        gap: 16px;
    }

    .loading-spinner {
        width: 48px;
        height: 48px;
        border: 4px solid rgba(79, 70, 229, 0.2);
        border-top-color: #4f46e5;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    .loading-state p {
        font-size: 1rem;
        color: var(--text-secondary);
        margin: 0;
    }

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

    @media (prefers-reduced-motion: reduce) {
        .section,
        .scenario-table tbody tr {
            transition: none;
            animation: none;
        }
    }
</style>

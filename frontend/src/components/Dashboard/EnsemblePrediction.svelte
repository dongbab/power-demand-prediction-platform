<script lang="ts">
    import { onMount } from 'svelte';
    import { apiService } from '../../services/api';
    import type { EnsemblePredictionResponse } from '../../lib/types';
    import LoadingSpinner from '../LoadingSpinner.svelte';
    import ContractOptimizationChart from './ContractOptimizationChart.svelte';

    export let stationId: string;
    export let currentContractKw: number | undefined = undefined;

    let loading = false;
    let error = '';
    let prediction: EnsemblePredictionResponse | null = null;
    let showDetails = false;
    let summaryHighlights: string[] = [];
    let riskSummary = '';

    async function loadEnsemblePrediction() {
        loading = true;
        error = '';
        
        try {
            const result = await apiService.getEnsemblePrediction(
                stationId,
                currentContractKw
            );
            
            if (result.success) {
                prediction = result;
            } else {
                error = result.error || '예측 실패';
            }
        } catch (e) {
            error = e instanceof Error ? e.message : '알 수 없는 오류';
            console.error('Ensemble prediction error:', e);
        } finally {
            loading = false;
        }
    }

    function formatCurrency(value: number): string {
        return new Intl.NumberFormat('ko-KR', {
            style: 'currency',
            currency: 'KRW',
            maximumFractionDigits: 0
        }).format(value);
    }

    function formatKw(value: number, digits = 1): string {
        if (!isFinite(value)) {
            return '-';
        }
        return value.toFixed(digits);
    }

    function formatPercent(value: number, digits = 0): string {
        if (!isFinite(value)) {
            return '-';
        }
        const percentValue = Math.abs(value) <= 1 ? value * 100 : value;
        return `${percentValue.toFixed(digits)}%`;
    }

    function getUrgencyText(level: string): string {
        switch (level) {
            case 'high':
                return '지금 즉시 계약 전력 변경을 검토하는 것이 좋아요.';
            case 'medium':
                return '빠른 시일 내에 계약 전력을 점검해 보는 것을 추천해요.';
            case 'low':
                return '현재 계약이 크게 문제되지는 않지만 주기적인 확인을 권장해요.';
            default:
                return '계약 전력 검토가 필요해 보입니다.';
        }
    }

    function getMaturityLearningCopy(level: string, sessionCount: number): string {
        const formattedCount = sessionCount.toLocaleString();
        switch (level) {
            case 'mature':
                return `${formattedCount}개의 충전 세션을 바탕으로 안정적인 패턴까지 학습했어요.`;
            case 'developing':
                return `${formattedCount}개의 충전 세션으로 주요 패턴을 학습 중이에요.`;
            case 'new':
                return `${formattedCount}개의 충전 세션 데이터라 아직 변동성이 커요. 더 많은 데이터가 들어오면 정확도가 올라가요.`;
            default:
                return `${formattedCount}개의 충전 세션 데이터를 활용해 학습했어요.`;
        }
    }

    function buildSummaryHighlights(pred: EnsemblePredictionResponse): string[] {
        const items: string[] = [];
        items.push(
            getMaturityLearningCopy(
                pred.ensemble_prediction.maturity.level,
                pred.ensemble_prediction.maturity.session_count
            )
        );

        items.push(
            `가장 높은 전력은 약 ${formatKw(pred.ensemble_prediction.final_prediction_kw)}kW로 예상돼요.`
        );

        items.push(
            `안전하게 사용하려면 ${formatKw(pred.contract_recommendation.recommended_contract_kw, 0)}kW 계약을 추천해요.`
        );

        if (pred.contract_recommendation.annual_savings_won) {
            items.push(
                `권장 계약을 따르면 연간 약 ${formatCurrency(pred.contract_recommendation.annual_savings_won)} 절감이 예상돼요.`
            );
        }

        if (pred.contract_recommendation.urgency_level) {
            items.push(getUrgencyText(pred.contract_recommendation.urgency_level));
        }

        return items;
    }

    function getRiskLabel(level: string): string {
        switch (level) {
            case 'high':
                return '높음';
            case 'medium':
                return '보통';
            case 'low':
                return '낮음';
            default:
                return level;
        }
    }

    function buildRiskSummary(risk: NonNullable<EnsemblePredictionResponse['contract_recommendation']['risk_assessment']>): string {
        const overage = formatPercent(risk.overage_probability, 1);
        const waste = formatPercent(risk.waste_probability, 1);
        const level = getRiskLabel(risk.risk_level);
        return `${level} 수준으로 예측되며 계약 전력이 부족할 확률은 ${overage}, 여유가 남을 확률은 ${waste}입니다.`;
    }

    function buildModelExplainer(
        key: 'lstm' | 'xgboost',
        summary: EnsemblePredictionResponse['ensemble_prediction']
    ): string {
        const model = summary[key];
        const baseCopy =
            key === 'lstm'
                ? '최근 충전 패턴을 학습한 시계열 모델이'
                : '많은 변수를 고려하는 의사결정 모델이';
        return `${baseCopy} ${formatKw(model.prediction_kw)}kW로 예측했고 불확실성 범위는 ±${formatKw(model.uncertainty_kw)}kW에요.`;
    }

    $: summaryHighlights = prediction ? buildSummaryHighlights(prediction) : [];

    $:
        riskSummary = prediction?.contract_recommendation.risk_assessment
            ? buildRiskSummary(prediction.contract_recommendation.risk_assessment)
            : '';
</script>

<div class="ensemble-predictor">
    <div class="ensemble-header">
        <div class="title-section">
            <div class="title-icon">🤖</div>
            <div class="title-content">
                <h2>AI 계약 전력 추천</h2>
                <span class="phase-badge">Phase 3</span>
            </div>
        </div>
        <button
            on:click={loadEnsemblePrediction}
            disabled={loading}
            class="refresh-btn"
            class:loading
        >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" class:spinning={loading}>
                <path d="M23 4v6h-6M1 20v-6h6"/>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
            {loading ? '예측 중...' : '새로고침'}
        </button>
    </div>

    {#if loading}
        <div class="loading-state">
            <LoadingSpinner />
            <div class="loading-text">
                <p class="loading-title">LSTM + XGBoost 앙상블 분석 중...</p>
                <p class="loading-subtitle">잠시만 기다려주세요</p>
            </div>
        </div>
    {:else if error}
        <div class="error-state">
            <div class="error-icon">⚠️</div>
            <p class="error-message">{error}</p>
        </div>
    {:else if prediction}
        <!-- 메인 예측 결과 -->
        <div class="prediction-cards">
            <!-- 최종 예측 -->
            <div class="prediction-card final-prediction">
                <div class="card-header">
                    <div class="card-icon">🎯</div>
                    <span class="card-label">앙상블 최종 예측</span>
                </div>
                <div class="card-value">
                    {formatKw(prediction.ensemble_prediction.final_prediction_kw)}
                    <span class="card-unit">kW</span>
                </div>
                <div class="card-meta">
                    <div class="meta-item">
                        <span class="meta-label">불확실성</span>
                        <span class="meta-value">±{formatKw(prediction.ensemble_prediction.uncertainty_kw)} kW</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">신뢰도</span>
                        <span class="meta-value confidence">
                            {formatPercent(prediction.ensemble_prediction.confidence_level, 0)}
                        </span>
                    </div>
                </div>
            </div>

            <!-- 권장 계약 -->
            <div class="prediction-card recommended-contract">
                <div class="card-header">
                    <div class="card-icon">📋</div>
                    <span class="card-label">권장 계약 전력</span>
                </div>
                <div class="card-value">
                    {formatKw(prediction.contract_recommendation.recommended_contract_kw, 0)}
                    <span class="card-unit">kW</span>
                </div>
                <div class="card-meta">
                    {#if prediction.contract_recommendation.current_contract_kw}
                        <div class="meta-item">
                            <span class="meta-label">현재 계약</span>
                            <span class="meta-value">{prediction.contract_recommendation.current_contract_kw} kW</span>
                        </div>
                    {/if}
                    <div class="urgency-badge urgency-{prediction.contract_recommendation.urgency_level}">
                        {prediction.contract_recommendation.urgency_level.toUpperCase()}
                    </div>
                    <div class="urgency-description">
                        {getUrgencyText(prediction.contract_recommendation.urgency_level)}
                    </div>
                </div>
            </div>

            <!-- 연간 절감액 -->
            {#if prediction.contract_recommendation.annual_savings_won}
                <div class="prediction-card savings-card">
                    <div class="card-header">
                        <div class="card-icon">💰</div>
                        <span class="card-label">연간 예상 절감액</span>
                    </div>
                    <div class="card-value savings-value">
                        {formatCurrency(prediction.contract_recommendation.annual_savings_won)}
                    </div>
                    <div class="card-meta">
                        {#if prediction.contract_recommendation.savings_percentage}
                            <div class="meta-item">
                                <span class="meta-label">절감률</span>
                                <span class="meta-value savings-percent">
                                    {formatPercent(prediction.contract_recommendation.savings_percentage, 1)}
                                </span>
                            </div>
                        {/if}
                        {#if prediction.contract_recommendation.monthly_savings}
                            <div class="meta-item">
                                <span class="meta-label">월 절감액</span>
                                <span class="meta-value">{formatCurrency(prediction.contract_recommendation.monthly_savings)}</span>
                            </div>
                        {/if}
                    </div>
                </div>
            {/if}
        </div>
        <div class="quick-summary">
            <h3 class="section-title">한눈에 파악하기</h3>
            <ul class="summary-list">
                {#each summaryHighlights as item}
                    <li>
                        <span class="summary-bullet">•</span>
                        <span>{item}</span>
                    </li>
                {/each}
            </ul>
        </div>
        <!-- 모델 상세 정보 (토글) -->
        <div class="details-section">
            <button
                on:click={() => showDetails = !showDetails}
                class="details-toggle"
                class:active={showDetails}
            >
                <div class="toggle-content">
                    <span class="toggle-icon">🔍</span>
                    <span class="toggle-label">모델 상세 정보</span>
                </div>
                <svg class="toggle-arrow" class:rotated={showDetails} viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M6 9l6 6 6-6"/>
                </svg>
            </button>

            {#if showDetails}
                <div class="details-content">
                    <div class="model-cards">
                        <!-- LSTM 모델 -->
                        <div class="model-card lstm-model">
                            <div class="model-header">
                                <span class="model-icon">🧠</span>
                                <h3 class="model-title">LSTM 모델</h3>
                            </div>
                            <div class="model-metrics">
                                <div class="model-metric">
                                    <span class="metric-label">예측값</span>
                                    <span class="metric-value">
                                        {prediction.ensemble_prediction.lstm.prediction_kw.toFixed(1)} kW
                                    </span>
                                </div>
                                <div class="model-metric">
                                    <span class="metric-label">불확실성</span>
                                    <span class="metric-value">
                                        ±{prediction.ensemble_prediction.lstm.uncertainty_kw.toFixed(1)} kW
                                    </span>
                                </div>
                                <div class="model-metric">
                                    <span class="metric-label">가중치</span>
                                    <span class="metric-value weight">
                                        {(prediction.ensemble_prediction.lstm.weight * 100).toFixed(0)}%
                                    </span>
                                </div>
                            </div>
                            <div class="weight-bar">
                                <div
                                    class="weight-fill"
                                    style={`width: ${(prediction.ensemble_prediction.lstm.weight * 100).toFixed(0)}%`}
                                ></div>
                            </div>
                            <p class="model-explainer">{buildModelExplainer('lstm', prediction.ensemble_prediction)}</p>
                            <div class="model-description">
                                <span class="model-note">주요 특징</span>
                                <ul class="model-points">
                                    <li>최근 충전 흐름을 학습한 시계열 기반 예측</li>
                                    <li>Monte Carlo Dropout으로 변동성을 추정해 안정성을 확보</li>
                                </ul>
                            </div>
                        </div>

                        <!-- XGBoost 모델 -->
                        <div class="model-card xgboost-model">
                            <div class="model-header">
                                <span class="model-icon">🌲</span>
                                <h3 class="model-title">XGBoost 모델</h3>
                            </div>
                            <div class="model-metrics">
                                <div class="model-metric">
                                    <span class="metric-label">예측값</span>
                                    <span class="metric-value">
                                        {prediction.ensemble_prediction.xgboost.prediction_kw.toFixed(1)} kW
                                    </span>
                                </div>
                                <div class="model-metric">
                                    <span class="metric-label">불확실성</span>
                                    <span class="metric-value">
                                        ±{prediction.ensemble_prediction.xgboost.uncertainty_kw.toFixed(1)} kW
                                    </span>
                                </div>
                                <div class="model-metric">
                                    <span class="metric-label">가중치</span>
                                    <span class="metric-value weight">
                                        {(prediction.ensemble_prediction.xgboost.weight * 100).toFixed(0)}%
                                    </span>
                                </div>
                            </div>
                            <div class="weight-bar">
                                <div
                                    class="weight-fill"
                                    style={`width: ${(prediction.ensemble_prediction.xgboost.weight * 100).toFixed(0)}%`}
                                ></div>
                            </div>
                            <p class="model-explainer">{buildModelExplainer('xgboost', prediction.ensemble_prediction)}</p>
                            <div class="model-description">
                                <span class="model-note">주요 특징</span>
                                <ul class="model-points">
                                    <li>충전소 이용 시간, 요일, 환경 정보를 함께 고려</li>
                                    <li>비선형 패턴을 학습해 갑작스런 피크에도 대비</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            {/if}
        </div>

        <!-- 10kW 단위 최적화 시각화 -->
        {#if prediction.contract_recommendation.optimization_details}
            <div class="optimization-section">
                <ContractOptimizationChart 
                    optimizationData={prediction.contract_recommendation.optimization_details}
                    predictionDistribution={prediction.contract_recommendation.optimization_details.prediction_distribution || []}
                    ensemblePrediction={prediction.ensemble_prediction}
                />
            </div>
        {/if}

        <!-- 메타데이터 -->
        <div class="metadata">
            <div class="metadata-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                </svg>
                <span>모델 버전: {prediction.metadata.model_version}</span>
            </div>
            <div class="metadata-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <rect x="3" y="3" width="18" height="18" rx="2"/>
                    <path d="M9 3v18"/>
                    <path d="M15 3v18"/>
                </svg>
                <span>충전기 타입: {prediction.metadata.charger_type}</span>
            </div>
            <div class="metadata-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12,6 12,12 16,14"/>
                </svg>
                <span>예측 시각: {new Date(prediction.timestamp).toLocaleString('ko-KR')}</span>
            </div>
        </div>
    {/if}
</div>

<style>
    /* 현대적 UI 스타일 - PeakPowerPredictor 참고 */
    .ensemble-predictor {
        display: flex;
        flex-direction: column;
        gap: 24px;
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 2px 8px var(--shadow);
        margin-bottom: clamp(24px, 4vw, 40px);
    }

    /* 헤더 */
    .ensemble-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 20px;
        border-bottom: 1px solid var(--border-color);
    }

    .title-section {
        display: flex;
        align-items: center;
        gap: 16px;
    }

    .title-icon {
        font-size: 2.5rem;
        line-height: 1;
    }

    .title-content {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .title-content h2 {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--text-primary);
    }

    .phase-badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.5px;
    }

    .refresh-btn {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 20px;
        background: var(--primary-color);
        color: white;
        border: none;
        border-radius: 10px;
        font-size: 0.9rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    .refresh-btn:hover:not(:disabled) {
        background: var(--primary-dark);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    }

    .refresh-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    .refresh-btn svg {
        width: 18px;
        height: 18px;
        stroke-width: 2.5;
    }

    .refresh-btn svg.spinning {
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }

    /* 로딩 상태 */
    .loading-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 80px 24px;
        gap: 20px;
    }

    .loading-text {
        text-align: center;
    }

    .loading-title {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .loading-subtitle {
        margin: 4px 0 0 0;
        font-size: 0.9rem;
        color: var(--text-secondary);
    }

    /* 에러 상태 */
    .error-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 60px 24px;
        gap: 16px;
        background: rgba(239, 68, 68, 0.05);
        border: 1px solid rgba(239, 68, 68, 0.2);
        border-radius: 12px;
    }

    .error-icon {
        font-size: 3rem;
    }

    .error-message {
        font-size: 1rem;
        font-weight: 500;
        color: #dc2626;
        text-align: center;
    }

    /* 예측 카드 */
    .prediction-cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;
    }

    .prediction-card {
        background: linear-gradient(135deg, var(--card-bg-from) 0%, var(--card-bg-to) 100%);
        border: 1px solid var(--card-border);
        border-radius: 14px;
        padding: 20px;
        box-shadow: 0 2px 8px var(--shadow);
        transition: all 0.3s ease;
    }

    .prediction-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 24px var(--shadow-hover);
    }

    .final-prediction {
        --card-bg-from: rgba(59, 130, 246, 0.1);
        --card-bg-to: rgba(99, 102, 241, 0.1);
        --card-border: rgba(59, 130, 246, 0.3);
    }

    .recommended-contract {
        --card-bg-from: rgba(16, 185, 129, 0.1);
        --card-bg-to: rgba(5, 150, 105, 0.1);
        --card-border: rgba(16, 185, 129, 0.3);
    }

    .savings-card {
        --card-bg-from: rgba(168, 85, 247, 0.1);
        --card-bg-to: rgba(139, 92, 246, 0.1);
        --card-border: rgba(168, 85, 247, 0.3);
    }

    :global([data-theme="dark"]) .prediction-card {
        --card-bg-from: rgba(59, 130, 246, 0.15);
        --card-bg-to: rgba(99, 102, 241, 0.15);
    }

    :global([data-theme="dark"]) .final-prediction {
        --card-bg-from: rgba(59, 130, 246, 0.15);
        --card-bg-to: rgba(99, 102, 241, 0.15);
    }

    :global([data-theme="dark"]) .recommended-contract {
        --card-bg-from: rgba(16, 185, 129, 0.15);
        --card-bg-to: rgba(5, 150, 105, 0.15);
    }

    :global([data-theme="dark"]) .savings-card {
        --card-bg-from: rgba(168, 85, 247, 0.15);
        --card-bg-to: rgba(139, 92, 246, 0.15);
    }

    .card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 16px;
    }

    .card-icon {
        font-size: 1.5rem;
    }

    .card-label {
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--text-secondary);
    }

    .card-value {
        font-size: 2.5rem;
        font-weight: 800;
        color: var(--text-primary);
        line-height: 1;
        margin-bottom: 12px;
    }

    .card-unit {
        font-size: 1.2rem;
        font-weight: 600;
        color: var(--text-secondary);
        margin-left: 4px;
    }

    .savings-value {
        font-size: 1.8rem;
    }

    .card-meta {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .urgency-description {
        font-size: 0.8rem;
        color: var(--text-secondary);
        line-height: 1.4;
    }

    .meta-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.85rem;
    }

    .meta-label {
        color: var(--text-secondary);
    }

    .meta-value {
        font-weight: 600;
        color: var(--text-primary);
    }

    .meta-value.confidence {
        color: #3b82f6;
    }

    .meta-value.savings-percent {
        color: #a855f7;
    }

    .urgency-badge {
        display: inline-flex;
        align-items: center;
        padding: 6px 12px;
        border-radius: 8px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.5px;
    }

    .urgency-high {
        background: rgba(239, 68, 68, 0.15);
        color: #dc2626;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }

    .urgency-medium {
        background: rgba(245, 158, 11, 0.15);
        color: #d97706;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }

    .urgency-low {
        background: rgba(34, 197, 94, 0.15);
        color: #16a34a;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }

    /* 성숙도 카드 */
    .quick-summary {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.05), rgba(59, 130, 246, 0.05));
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 6px var(--shadow);
        margin-top: 4px;
    }

    .section-title {
        margin: 0;
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--text-primary);
    }

    .summary-list {
        list-style: none;
        margin: 14px 0 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .summary-list li {
        display: flex;
        gap: 10px;
        font-size: 0.95rem;
        color: var(--text-primary);
        line-height: 1.5;
    }

    .summary-bullet {
        color: var(--primary-color);
        font-weight: 700;
    }

    /* 상세 정보 섹션 */
    .details-section {
        background: rgba(100, 116, 139, 0.03);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        overflow: hidden;
    }

    .details-toggle {
        width: 100%;
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 20px;
        background: transparent;
        border: none;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    .details-toggle:hover {
        background: rgba(100, 116, 139, 0.05);
    }

    .details-toggle.active {
        background: rgba(99, 102, 241, 0.05);
    }

    .toggle-content {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .toggle-icon {
        font-size: 1.2rem;
    }

    .toggle-label {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .toggle-arrow {
        width: 20px;
        height: 20px;
        stroke-width: 2.5;
        color: var(--text-secondary);
        transition: transform 0.3s ease;
    }

    .toggle-arrow.rotated {
        transform: rotate(180deg);
    }

    .details-content {
        padding: 20px;
        border-top: 1px solid var(--border-color);
        animation: slideDown 0.3s ease;
    }

    @keyframes slideDown {
        from {
            opacity: 0;
            transform: translateY(-10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* 모델 카드 */
    .model-cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 16px;
        margin-bottom: 20px;
    }

    .model-card {
        background: var(--bg-secondary);
        border: 1px solid var(--model-border);
        border-radius: 12px;
        padding: 20px;
        transition: all 0.2s ease;
    }

    .model-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px var(--shadow);
    }

    .lstm-model {
        --model-border: rgba(99, 102, 241, 0.3);
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.05), rgba(129, 140, 248, 0.05));
    }

    .xgboost-model {
        --model-border: rgba(249, 115, 22, 0.3);
        background: linear-gradient(135deg, rgba(249, 115, 22, 0.05), rgba(251, 146, 60, 0.05));
    }

    .model-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;
    }

    .model-icon {
        font-size: 1.5rem;
    }

    .model-title {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--text-primary);
    }

    .model-metrics {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin-bottom: 12px;
    }

    .model-metric {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid var(--border-color);
    }

    .model-metric:last-child {
        border-bottom: none;
    }

    .model-metric .metric-label {
        font-size: 0.9rem;
        color: var(--text-secondary);
    }

    .model-metric .metric-value {
        font-size: 0.95rem;
        font-weight: 700;
        color: var(--text-primary);
    }

    .model-metric .metric-value.weight {
        color: #6366f1;
    }

    .weight-bar {
        height: 6px;
        border-radius: 999px;
        background: rgba(99, 102, 241, 0.15);
        overflow: hidden;
        margin-bottom: 12px;
    }

    .model-card.xgboost-model .weight-bar {
        background: rgba(249, 115, 22, 0.18);
    }

    .weight-fill {
        height: 100%;
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.7), rgba(59, 130, 246, 0.9));
        transition: width 0.4s ease;
    }

    .model-card.xgboost-model .weight-fill {
        background: linear-gradient(135deg, rgba(251, 146, 60, 0.8), rgba(249, 115, 22, 0.9));
    }

    .model-explainer {
        margin: 0 0 12px 0;
        font-size: 0.9rem;
        color: var(--text-secondary);
        line-height: 1.5;
    }

    .model-description {
        padding: 12px;
        background: rgba(100, 116, 139, 0.05);
        border-radius: 10px;
        font-size: 0.85rem;
        color: var(--text-secondary);
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .model-note {
        font-weight: 700;
        color: var(--text-primary);
    }

    .model-points {
        margin: 0;
        padding-left: 18px;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .model-points li {
        line-height: 1.4;
    }

    /* 위험 평가 */
    .risk-assessment {
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.05), rgba(251, 191, 36, 0.05));
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 12px;
        padding: 20px;
    }

    .risk-title {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0 0 16px 0;
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--text-primary);
    }

    .risk-summary {
        margin: 0 0 18px 0;
        font-size: 0.95rem;
        color: var(--text-secondary);
        line-height: 1.6;
    }

    .risk-icon {
        font-size: 1.3rem;
    }

    .risk-metrics {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 16px;
    }

    .risk-metric {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .risk-label {
        font-size: 0.85rem;
        color: var(--text-secondary);
    }

    .risk-value {
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--text-primary);
    }

    .risk-value.level {
        color: #d97706;
        text-transform: none;
    }

    /* 최적화 섹션 */
    .optimization-section {
        margin-top: 8px;
    }

    /* 메타데이터 */
    .metadata {
        display: flex;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
        padding-top: 16px;
        border-top: 1px solid var(--border-color);
    }

    .metadata-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.8rem;
        color: var(--text-secondary);
    }

    .metadata-item svg {
        width: 14px;
        height: 14px;
        stroke-width: 2;
    }

    /* CSS 변수 정의 */
    :global([data-theme="light"]) .ensemble-predictor {
        --bg-secondary: #ffffff;
        --border-color: rgba(0, 0, 0, 0.1);
        --shadow: rgba(0, 0, 0, 0.05);
        --shadow-hover: rgba(0, 0, 0, 0.15);
        --text-primary: #111827;
        --text-secondary: #6b7280;
        --primary-color: #4f46e5;
        --primary-dark: #4338ca;
    }

    :global([data-theme="dark"]) .ensemble-predictor {
        --bg-secondary: #1f2937;
        --border-color: #374151;
        --shadow: rgba(0, 0, 0, 0.3);
        --shadow-hover: rgba(0, 0, 0, 0.5);
        --text-primary: #f9fafb;
        --text-secondary: #d1d5db;
        --primary-color: #6366f1;
        --primary-dark: #4f46e5;
    }

    /* 반응형 */
    @media (max-width: 768px) {
        .ensemble-predictor {
            padding: 16px;
        }

        .ensemble-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 16px;
        }

        .title-content h2 {
            font-size: 1.3rem;
        }

        .card-value {
            font-size: 2rem;
        }

        .prediction-cards {
            grid-template-columns: 1fr;
        }

        .metadata {
            flex-direction: column;
            gap: 8px;
        }

        .model-cards {
            grid-template-columns: 1fr;
        }
    }
</style>

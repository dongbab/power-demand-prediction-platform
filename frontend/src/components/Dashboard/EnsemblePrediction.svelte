<script lang="ts">
    import { onMount } from 'svelte';
    import { apiService } from '../../services/api';
    import type { EnsemblePredictionResponse } from '../../lib/types';
    import LoadingSpinner from '../LoadingSpinner.svelte';

    export let stationId: string;
    export let currentContractKw: number | undefined = undefined;

    let loading = false;
    let error = '';
    let prediction: EnsemblePredictionResponse | null = null;
    let showDetails = false;

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

    onMount(() => {
        loadEnsemblePrediction();
    });

    function getMaturityBadgeColor(level: string): string {
        switch (level) {
            case 'mature': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
            case 'developing': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
            case 'new': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
            default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
        }
    }

    function getMaturityLabel(level: string): string {
        switch (level) {
            case 'mature': return '성숙 충전소';
            case 'developing': return '발전 충전소';
            case 'new': return '신규 충전소';
            default: return '알 수 없음';
        }
    }

    function getUrgencyColor(level: string): string {
        switch (level) {
            case 'high': return 'text-red-600 dark:text-red-400';
            case 'medium': return 'text-yellow-600 dark:text-yellow-400';
            case 'low': return 'text-green-600 dark:text-green-400';
            default: return 'text-gray-600 dark:text-gray-400';
        }
    }

    function formatCurrency(value: number): string {
        return new Intl.NumberFormat('ko-KR', {
            style: 'currency',
            currency: 'KRW',
            maximumFractionDigits: 0
        }).format(value);
    }
</script>

<div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 mb-6">
    <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-bold text-gray-900 dark:text-white">
            🤖 AI 앙상블 예측 (Phase 3)
        </h2>
        <button
            on:click={loadEnsemblePrediction}
            disabled={loading}
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
            {loading ? '예측 중...' : '새로고침'}
        </button>
    </div>

    {#if loading}
        <div class="flex justify-center items-center py-12">
            <LoadingSpinner />
            <span class="ml-3 text-gray-600 dark:text-gray-400">
                LSTM + XGBoost 앙상블 분석 중...
            </span>
        </div>
    {:else if error}
        <div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <p class="text-red-800 dark:text-red-200">⚠️ {error}</p>
        </div>
    {:else if prediction}
        <!-- 메인 예측 결과 -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <!-- 최종 예측 -->
            <div class="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/30 dark:to-blue-800/30 rounded-lg p-6 border border-blue-200 dark:border-blue-700">
                <div class="text-sm font-medium text-blue-800 dark:text-blue-200 mb-2">
                    앙상블 최종 예측
                </div>
                <div class="text-4xl font-bold text-blue-900 dark:text-blue-100 mb-1">
                    {prediction.ensemble_prediction.final_prediction_kw.toFixed(1)} kW
                </div>
                <div class="text-sm text-blue-700 dark:text-blue-300">
                    불확실성: ±{prediction.ensemble_prediction.uncertainty_kw.toFixed(1)} kW
                </div>
                <div class="mt-2 text-xs text-blue-600 dark:text-blue-400">
                    신뢰도: {(prediction.ensemble_prediction.confidence_level * 100).toFixed(0)}%
                </div>
            </div>

            <!-- 권장 계약 -->
            <div class="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/30 dark:to-green-800/30 rounded-lg p-6 border border-green-200 dark:border-green-700">
                <div class="text-sm font-medium text-green-800 dark:text-green-200 mb-2">
                    권장 계약 전력
                </div>
                <div class="text-4xl font-bold text-green-900 dark:text-green-100 mb-1">
                    {prediction.contract_recommendation.recommended_contract_kw} kW
                </div>
                {#if prediction.contract_recommendation.current_contract_kw}
                    <div class="text-sm text-green-700 dark:text-green-300">
                        현재: {prediction.contract_recommendation.current_contract_kw} kW
                    </div>
                {/if}
                <div class="mt-2">
                    <span class={`text-xs font-semibold px-2 py-1 rounded ${getUrgencyColor(prediction.contract_recommendation.urgency_level)}`}>
                        {prediction.contract_recommendation.urgency_level.toUpperCase()}
                    </span>
                </div>
            </div>

            <!-- 연간 절감액 -->
            {#if prediction.contract_recommendation.annual_savings_won}
                <div class="bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/30 dark:to-purple-800/30 rounded-lg p-6 border border-purple-200 dark:border-purple-700">
                    <div class="text-sm font-medium text-purple-800 dark:text-purple-200 mb-2">
                        연간 예상 절감액
                    </div>
                    <div class="text-4xl font-bold text-purple-900 dark:text-purple-100 mb-1">
                        {formatCurrency(prediction.contract_recommendation.annual_savings_won)}
                    </div>
                    {#if prediction.contract_recommendation.savings_percentage}
                        <div class="text-sm text-purple-700 dark:text-purple-300">
                            절감률: {prediction.contract_recommendation.savings_percentage.toFixed(1)}%
                        </div>
                    {/if}
                    {#if prediction.contract_recommendation.monthly_savings}
                        <div class="mt-2 text-xs text-purple-600 dark:text-purple-400">
                            월 {formatCurrency(prediction.contract_recommendation.monthly_savings)}
                        </div>
                    {/if}
                </div>
            {/if}
        </div>

        <!-- 스테이션 성숙도 -->
        <div class="bg-gray-50 dark:bg-gray-700/30 rounded-lg p-4 mb-6">
            <div class="flex items-center justify-between">
                <div>
                    <span class="text-sm font-medium text-gray-700 dark:text-gray-300 mr-3">
                        스테이션 성숙도:
                    </span>
                    <span class={`px-3 py-1 rounded-full text-sm font-semibold ${getMaturityBadgeColor(prediction.ensemble_prediction.maturity.level)}`}>
                        {getMaturityLabel(prediction.ensemble_prediction.maturity.level)}
                    </span>
                </div>
                <div class="text-sm text-gray-600 dark:text-gray-400">
                    데이터: {prediction.ensemble_prediction.maturity.session_count.toLocaleString()}개 세션
                </div>
            </div>
            <p class="mt-2 text-sm text-gray-600 dark:text-gray-400 italic">
                {prediction.ensemble_prediction.maturity.reasoning}
            </p>
        </div>

        <!-- 모델 상세 정보 (토글) -->
        <button
            on:click={() => showDetails = !showDetails}
            class="w-full text-left mb-4 px-4 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
        >
            <div class="flex items-center justify-between">
                <span class="font-medium text-gray-900 dark:text-white">
                    🔍 모델 상세 정보
                </span>
                <span class="text-gray-500 dark:text-gray-400">
                    {showDetails ? '▲ 접기' : '▼ 펼치기'}
                </span>
            </div>
        </button>

        {#if showDetails}
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <!-- LSTM 모델 -->
                <div class="bg-indigo-50 dark:bg-indigo-900/20 rounded-lg p-4 border border-indigo-200 dark:border-indigo-800">
                    <h3 class="font-semibold text-indigo-900 dark:text-indigo-100 mb-3 flex items-center">
                        <span class="mr-2">🧠</span> LSTM 모델
                    </h3>
                    <div class="space-y-2 text-sm">
                        <div class="flex justify-between">
                            <span class="text-indigo-700 dark:text-indigo-300">예측값:</span>
                            <span class="font-semibold text-indigo-900 dark:text-indigo-100">
                                {prediction.ensemble_prediction.lstm.prediction_kw.toFixed(1)} kW
                            </span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-indigo-700 dark:text-indigo-300">불확실성:</span>
                            <span class="font-semibold text-indigo-900 dark:text-indigo-100">
                                ±{prediction.ensemble_prediction.lstm.uncertainty_kw.toFixed(1)} kW
                            </span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-indigo-700 dark:text-indigo-300">가중치:</span>
                            <span class="font-semibold text-indigo-900 dark:text-indigo-100">
                                {(prediction.ensemble_prediction.lstm.weight * 100).toFixed(0)}%
                            </span>
                        </div>
                    </div>
                    <div class="mt-3 text-xs text-indigo-600 dark:text-indigo-400">
                        💡 시계열 패턴 + Monte Carlo Dropout
                    </div>
                </div>

                <!-- XGBoost 모델 -->
                <div class="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-4 border border-orange-200 dark:border-orange-800">
                    <h3 class="font-semibold text-orange-900 dark:text-orange-100 mb-3 flex items-center">
                        <span class="mr-2">🌲</span> XGBoost 모델
                    </h3>
                    <div class="space-y-2 text-sm">
                        <div class="flex justify-between">
                            <span class="text-orange-700 dark:text-orange-300">예측값:</span>
                            <span class="font-semibold text-orange-900 dark:text-orange-100">
                                {prediction.ensemble_prediction.xgboost.prediction_kw.toFixed(1)} kW
                            </span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-orange-700 dark:text-orange-300">불확실성:</span>
                            <span class="font-semibold text-orange-900 dark:text-orange-100">
                                ±{prediction.ensemble_prediction.xgboost.uncertainty_kw.toFixed(1)} kW
                            </span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-orange-700 dark:text-orange-300">가중치:</span>
                            <span class="font-semibold text-orange-900 dark:text-orange-100">
                                {(prediction.ensemble_prediction.xgboost.weight * 100).toFixed(0)}%
                            </span>
                        </div>
                    </div>
                    <div class="mt-3 text-xs text-orange-600 dark:text-orange-400">
                        💡 내부 특징 기반 예측 (충전 패턴, 시간)
                    </div>
                </div>
            </div>

            <!-- 위험 평가 -->
            {#if prediction.contract_recommendation.risk_assessment}
                <div class="bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-4 border border-yellow-200 dark:border-yellow-800">
                    <h3 class="font-semibold text-yellow-900 dark:text-yellow-100 mb-3">
                        ⚠️ 위험 평가
                    </h3>
                    <div class="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                        <div>
                            <span class="text-yellow-700 dark:text-yellow-300">위험 수준:</span>
                            <span class="font-semibold text-yellow-900 dark:text-yellow-100 ml-2">
                                {prediction.contract_recommendation.risk_assessment.risk_level}
                            </span>
                        </div>
                        <div>
                            <span class="text-yellow-700 dark:text-yellow-300">초과 확률:</span>
                            <span class="font-semibold text-yellow-900 dark:text-yellow-100 ml-2">
                                {(prediction.contract_recommendation.risk_assessment.overage_probability * 100).toFixed(1)}%
                            </span>
                        </div>
                        <div>
                            <span class="text-yellow-700 dark:text-yellow-300">낭비 확률:</span>
                            <span class="font-semibold text-yellow-900 dark:text-yellow-100 ml-2">
                                {(prediction.contract_recommendation.risk_assessment.waste_probability * 100).toFixed(1)}%
                            </span>
                        </div>
                    </div>
                </div>
            {/if}
        {/if}

        <!-- 권고 사항 -->
        <div class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-800">
            <h3 class="font-semibold text-blue-900 dark:text-blue-100 mb-2 flex items-center">
                <span class="mr-2">💡</span> AI 권고 사항
            </h3>
            <p class="text-blue-800 dark:text-blue-200">
                {prediction.contract_recommendation.recommendation}
            </p>
        </div>

        <!-- 메타데이터 -->
        <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400 flex justify-between">
            <span>모델 버전: {prediction.metadata.model_version}</span>
            <span>충전기 타입: {prediction.metadata.charger_type}</span>
            <span>예측 시각: {new Date(prediction.timestamp).toLocaleString('ko-KR')}</span>
        </div>
    {/if}
</div>

<style>
    /* 부드러운 애니메이션 */
    div {
        transition: all 0.3s ease;
    }
</style>

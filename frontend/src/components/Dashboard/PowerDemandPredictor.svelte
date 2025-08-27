<script>
	import { onMount, onDestroy } from 'svelte';
	import MetricCard from './MetricCard.svelte';
	import DistributionChart from './DistributionChart.svelte';
	import MonthlyChart from './MonthlyChart.svelte';
	import LoadingSpinner from '../LoadingSpinner.svelte';
	
	export let stationId;
	export let monthlyContract = null;
	export let analysis = null;
	
	let isLoading = false;
	let lastUpdated = null;
	let refreshInterval;
	let demandForecast = null;
	let selectedTimeframe = '7days';
	
	const timeframes = [
		{ value: '24hours', label: '24시간' },
		{ value: '7days', label: '7일간' },
		{ value: '1month', label: '1개월' },
		{ value: '3months', label: '3개월' }
	];
	
	onMount(() => {
		// Auto-refresh demand forecast every 2 minutes
		refreshInterval = setInterval(updateDemandForecast, 2 * 60 * 1000);
		updateDemandForecast();
	});
	
	onDestroy(() => {
		if (refreshInterval) {
			clearInterval(refreshInterval);
		}
	});
	
	async function updateDemandForecast() {
		if (!stationId) return;
		
		isLoading = true;
		try {
			// Here you would make an API call to get demand forecast
			// For now, we'll simulate the forecast data
			demandForecast = {
				average_demand: analysis?.performance_analysis?.average_session_power || 45,
				peak_demand: monthlyContract?.recommended_contract_kw || 85,
				projected_growth: 12, // percentage
				seasonal_factors: {
					summer: 1.3,
					winter: 0.8,
					spring: 1.0,
					autumn: 0.9
				},
				hourly_forecast: generateHourlyForecast(),
				weekly_pattern: [85, 72, 68, 75, 88, 95, 82] // Mon-Sun
			};
			lastUpdated = new Date();
		} catch (error) {
			console.error('Failed to update demand forecast:', error);
		} finally {
			isLoading = false;
		}
	}
	
	function generateHourlyForecast() {
		// Generate realistic hourly demand pattern
		const basePattern = [
			30, 28, 25, 22, 25, 35, 45, 55, 65, 70, 75, 80,
			85, 82, 78, 75, 78, 85, 88, 85, 75, 65, 50, 38
		];
		
		return basePattern.map((value, hour) => ({
			hour,
			demand: value + (Math.random() - 0.5) * 10, // Add some variation
			confidence: 85 + Math.random() * 10
		}));
	}
	
	$: averageDemand = demandForecast?.average_demand || 0;
	$: peakDemand = demandForecast?.peak_demand || 0;
	$: projectedGrowth = demandForecast?.projected_growth || 0;
	$: recommendedContract = monthlyContract?.recommended_contract_kw || 0;
</script>

<div class="demand-predictor">
	<div class="section-header">
		<h2>📊 전력 수요 예측</h2>
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
					<span>마지막 업데이트 : {lastUpdated.toLocaleTimeString()}</span>
				{/if}
			</div>
		</div>
	</div>

	<div class="metrics-row">
		<MetricCard
			title="평균 수요"
			value={averageDemand}
			unit="kW"
			type="power"
		/>
		<MetricCard
			title="최대 수요"
			value={peakDemand}
			unit="kW"
			type="contract"
		/>
		<MetricCard
			title="예상 증가율"
			value={projectedGrowth}
			unit="%"
			type="growth"
		/>
		<MetricCard
			title="권고 계약전력"
			value={recommendedContract}
			unit="kW"
			type="contract"
		/>
	</div>

	<div class="forecast-details">
		<div class="comparison-section">
			<div class="comparison-chart">
				<h3>📊 실제 vs 예측 전력 수요 비교</h3>
				<div class="chart-wrapper">
					<div class="comparison-bars">
						<div class="comparison-item">
							<div class="bar-container">
								<div class="bar-label">실제 수요</div>
								<div class="bar-wrapper">
									<div class="bar actual" style="width: {(averageDemand / 100) * 100}%">
										<span class="bar-value">{averageDemand.toFixed(1)}kW</span>
									</div>
								</div>
							</div>
						</div>
						<div class="comparison-item">
							<div class="bar-container">
								<div class="bar-label">예측 수요</div>
								<div class="bar-wrapper">
									<div class="bar predicted" style="width: {(peakDemand / 100) * 100}%">
										<span class="bar-value">{peakDemand.toFixed(1)}kW</span>
									</div>
								</div>
							</div>
						</div>
						<div class="comparison-item">
							<div class="bar-container">
								<div class="bar-label">권고 계약전력</div>
								<div class="bar-wrapper">
									<div class="bar contract" style="width: {(recommendedContract / 100) * 100}%">
										<span class="bar-value">{recommendedContract.toFixed(1)}kW</span>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>

			<div class="comparison-metrics">
				<h3>📈 비교 분석 결과</h3>
				<div class="metrics-grid">
					<div class="metric-item accuracy">
						<div class="metric-icon">🎯</div>
						<div class="metric-content">
							<div class="metric-value">
								{#if averageDemand > 0}
									{((1 - Math.abs(peakDemand - averageDemand) / averageDemand) * 100).toFixed(1)}%
								{:else}
									-
								{/if}
							</div>
							<div class="metric-label">예측 정확도</div>
						</div>
					</div>
					<div class="metric-item difference">
						<div class="metric-icon">📊</div>
						<div class="metric-content">
							<div class="metric-value">
								{Math.abs(peakDemand - averageDemand).toFixed(1)}kW
							</div>
							<div class="metric-label">예측 오차</div>
						</div>
					</div>
					<div class="metric-item efficiency">
						<div class="metric-icon">⚡</div>
						<div class="metric-content">
							<div class="metric-value">
								{#if recommendedContract > 0}
									{((averageDemand / recommendedContract) * 100).toFixed(1)}%
								{:else}
									-
								{/if}
							</div>
							<div class="metric-label">계약 효율성</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>

</div>

<style>
	/* Mobile-first base styles */
	.demand-predictor {
		background: var(--bg-secondary);
		border-radius: 12px;
		padding: 16px;
		box-shadow: 0 2px 8px var(--shadow);
		border: 2px solid var(--border-color);
		transition: background-color 0.3s ease, border-color 0.3s ease;
	}

	.section-header {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 12px;
		margin-bottom: 20px;
		padding-bottom: 12px;
		border-bottom: 2px solid var(--border-color);
	}

	.section-header h2 {
		margin: 0;
		color: var(--primary-color);
		font-size: 1.4em;
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

	.forecast-details {
		display: grid;
		grid-template-columns: 1fr;
		gap: 16px;
		margin-bottom: 20px;
	}

	.charts-section {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.chart-container h3,
	.insights-section h3 {
		margin: 0 0 12px 0;
		color: var(--text-primary);
		font-size: 1.1em;
	}

	.insights-section {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.insight-card {
		padding: 12px;
		background: var(--neutral-light);
		border-radius: 8px;
		border-left: 3px solid var(--primary-color);
		transition: background-color 0.3s ease;
	}

	.insight-card h4 {
		margin: 0 0 8px 0;
		color: var(--primary-color);
		font-size: 0.9em;
	}

	.seasonal-factors {
		display: grid;
		grid-template-columns: 1fr;
		gap: 6px;
	}

	.season-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 4px 8px;
		background: var(--bg-secondary);
		border-radius: 4px;
		font-size: 0.8em;
		transition: background-color 0.3s ease;
	}

	.season-factor {
		font-weight: 600;
		color: var(--primary-color);
	}

	.weekly-pattern {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.day-item {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 0.8em;
	}

	.day-name {
		min-width: 16px;
		font-weight: 500;
		font-size: 0.75em;
	}

	.demand-bar {
		flex: 1;
		position: relative;
		height: 16px;
		background: var(--border-color);
		border-radius: 8px;
		overflow: hidden;
	}

	.demand-fill {
		height: 100%;
		background: var(--gradient-success);
		transition: width 0.3s ease;
	}

	.demand-value {
		position: absolute;
		right: 4px;
		top: 50%;
		transform: translateY(-50%);
		font-size: 0.7em;
		font-weight: 500;
		color: var(--text-primary);
	}

	.recommendations {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.recommendation-item {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 8px;
		background: var(--bg-secondary);
		border-radius: 6px;
		font-size: 0.8em;
		transition: background-color 0.3s ease;
	}

	.rec-icon {
		font-size: 0.9em;
		flex-shrink: 0;
	}

	.rec-text {
		color: var(--text-primary);
	}

	/* Comparison Section Styles */
	.comparison-section {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.comparison-chart {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.comparison-chart h3 {
		margin: 0;
		color: var(--text-primary);
		font-size: 1.1em;
	}

	.chart-wrapper {
		background: var(--neutral-light);
		border-radius: 12px;
		padding: 16px;
		border: 1px solid var(--border-color);
		transition: all 0.3s ease;
	}

	.comparison-bars {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.comparison-item {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.bar-container {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.bar-label {
		font-size: 0.9em;
		font-weight: 600;
		color: var(--text-primary);
	}

	.bar-wrapper {
		position: relative;
		background: var(--border-color);
		border-radius: 8px;
		height: 32px;
		overflow: hidden;
	}

	.bar {
		height: 100%;
		border-radius: 6px;
		position: relative;
		display: flex;
		align-items: center;
		justify-content: flex-end;
		padding-right: 8px;
		min-width: 20%;
		transition: width 0.5s ease;
	}

	.bar.actual {
		background: linear-gradient(135deg, #4caf50, #66bb6a);
	}

	.bar.predicted {
		background: linear-gradient(135deg, #2196f3, #42a5f5);
	}

	.bar.contract {
		background: linear-gradient(135deg, #ff9800, #ffb74d);
	}

	.bar-value {
		font-size: 0.8em;
		font-weight: 600;
		color: white;
		text-shadow: 0 1px 2px rgba(0,0,0,0.3);
	}

	.comparison-metrics {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.comparison-metrics h3 {
		margin: 0;
		color: var(--text-primary);
		font-size: 1.1em;
	}

	.metrics-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 12px;
	}

	.metric-item {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 14px;
		background: var(--neutral-light);
		border-radius: 10px;
		border: 1px solid var(--border-color);
		transition: all 0.3s ease;
	}

	.metric-item:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px var(--shadow);
	}

	.metric-item.accuracy {
		border-left: 4px solid #4caf50;
	}

	.metric-item.difference {
		border-left: 4px solid #2196f3;
	}

	.metric-item.efficiency {
		border-left: 4px solid #ff9800;
	}

	.metric-icon {
		font-size: 1.2em;
		flex-shrink: 0;
	}

	.metric-content {
		display: flex;
		flex-direction: column;
		gap: 2px;
		flex: 1;
	}

	.metric-value {
		font-size: 1.1em;
		font-weight: 700;
		color: var(--primary-color);
	}

	.metric-label {
		font-size: 0.8em;
		color: var(--text-muted);
		font-weight: 500;
	}

	/* Tablet Layout */
	@media (min-width: 768px) {
		.demand-predictor {
			padding: 20px;
			border-radius: 16px;
		}

		.section-header {
			flex-direction: row;
			justify-content: space-between;
			align-items: center;
			margin-bottom: 24px;
			padding-bottom: 16px;
		}

		.section-header h2 {
			font-size: 1.4em;
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

		.forecast-details {
			grid-template-columns: 1fr;
			gap: 20px;
			margin-bottom: 24px;
		}

		.comparison-section {
			grid-template-columns: 1.5fr 1fr;
			gap: 24px;
			display: grid;
		}

		.comparison-bars {
			gap: 18px;
		}

		.bar-wrapper {
			height: 36px;
		}

		.bar-value {
			font-size: 0.9em;
		}

		.metrics-grid {
			grid-template-columns: 1fr;
			gap: 14px;
		}

		.metric-item {
			padding: 16px;
		}

		.metric-icon {
			font-size: 1.3em;
		}

		.metric-value {
			font-size: 1.2em;
		}

		.metric-label {
			font-size: 0.85em;
		}

		.charts-section {
			gap: 20px;
		}

		.chart-container h3,
		.insights-section h3 {
			font-size: 1.1em;
			margin-bottom: 16px;
		}

		.insights-section {
			gap: 14px;
		}

		.insight-card {
			padding: 16px;
		}

		.insight-card h4 {
			font-size: 1em;
			margin-bottom: 12px;
		}

		.seasonal-factors {
			grid-template-columns: 1fr 1fr;
			gap: 8px;
		}

		.season-item {
			padding: 6px 10px;
			font-size: 0.9em;
		}

		.weekly-pattern {
			gap: 8px;
		}

		.day-item {
			font-size: 0.9em;
			gap: 12px;
		}

		.day-name {
			min-width: 20px;
			font-size: 0.9em;
		}

		.demand-bar {
			height: 18px;
		}

		.demand-value {
			right: 6px;
			font-size: 0.8em;
		}

		.recommendations {
			gap: 8px;
		}

		.recommendation-item {
			padding: 8px 12px;
			gap: 10px;
			font-size: 0.9em;
		}

		.rec-icon {
			font-size: 1em;
		}

		.action-buttons {
			flex-direction: row;
			gap: 12px;
		}

		.btn {
			width: auto;
			min-width: 140px;
		}
	}

	/* Desktop Layout */
	@media (min-width: 1024px) {
		.demand-predictor {
			padding: 24px;
		}

		.section-header h2 {
			font-size: 1.5em;
		}

		.metrics-row {
			gap: 16px;
			margin-bottom: 32px;
		}

		.forecast-details {
			grid-template-columns: 1fr;
			gap: 24px;
			margin-bottom: 28px;
		}

		.comparison-section {
			grid-template-columns: 1.8fr 1fr;
			gap: 32px;
		}

		.comparison-bars {
			gap: 20px;
		}

		.bar-wrapper {
			height: 40px;
		}

		.bar-value {
			font-size: 1em;
		}

		.metrics-grid {
			grid-template-columns: 1fr;
			gap: 16px;
		}

		.metric-item {
			padding: 18px;
		}

		.metric-icon {
			font-size: 1.4em;
		}

		.metric-value {
			font-size: 1.3em;
		}

		.metric-label {
			font-size: 0.9em;
		}

		.charts-section {
			gap: 24px;
		}

		.insights-section {
			gap: 16px;
		}

		.weekly-pattern {
			gap: 10px;
		}

		.demand-bar {
			height: 20px;
		}

		.demand-value {
			right: 8px;
			font-size: 0.8em;
		}

		.recommendations {
			gap: 10px;
		}

		.action-buttons {
			gap: 16px;
		}

		.btn {
			padding: 12px 20px;
			min-width: 160px;
		}
	}

	/* Large Desktop Layout */
	@media (min-width: 1440px) {
		.demand-predictor {
			padding: 28px;
		}

		.forecast-details {
			gap: 32px;
		}

		.comparison-section {
			gap: 40px;
		}

		.comparison-bars {
			gap: 24px;
		}

		.bar-wrapper {
			height: 44px;
		}

		.metrics-grid {
			gap: 20px;
		}

		.metric-item {
			padding: 20px;
		}
	}
</style>